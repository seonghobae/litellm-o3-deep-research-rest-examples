"""채팅과 deep_research 도구 호출 흐름을 조율한다."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import litellm

from .contracts import ChatRequest, ChatResponse, DeepResearchArguments
from .upstream import LiteLLMRelayGateway, UpstreamInvocationResult

DEEP_RESEARCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "deep_research",
    "description": (
        "Conduct in-depth research on a topic and return a detailed report. "
        "Use this when the user asks for detailed factual information, history, "
        "analysis, or comprehensive explanations that require research beyond "
        "general knowledge."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "research_question": {
                "type": "string",
                "description": "The specific research question or topic to investigate",
            },
            "deliverable_format": {
                "type": "string",
                "enum": ["markdown_brief", "markdown_report", "json_outline"],
                "description": "Format of the research output",
            },
        },
        "required": ["research_question", "deliverable_format"],
    },
}

SAFE_CHAT_ERROR_MESSAGE = "deep_research failed. Please retry later."


class ChatOrchestrator:
    """자동 ``deep_research`` 도구 호출이 포함된 채팅 흐름을 조율한다."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str = "litellm_proxy/gpt-4o",
        research_model: str = "litellm_proxy/o3-deep-research",
        timeout_seconds: float = 30.0,
        research_timeout_seconds: float = 300.0,
    ) -> None:
        """채팅 모델과 연구 모델에 필요한 연결 정보를 초기화한다."""
        self._base_url = base_url
        self._api_key = api_key
        self._chat_model = chat_model
        self._timeout_seconds = timeout_seconds
        self._research_timeout_seconds = research_timeout_seconds
        self._gateway = LiteLLMRelayGateway(
            base_url=base_url,
            api_key=api_key,
            model=research_model.removeprefix("litellm_proxy/"),
            timeout_seconds=research_timeout_seconds,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """필요하면 ``deep_research``를 호출하는 채팅 턴을 수행한다."""
        user_content = self._build_user_content(request)
        kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "input": user_content,
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        if request.auto_tool_call:
            kwargs["tools"] = [DEEP_RESEARCH_TOOL_SCHEMA]

        try:
            first_response = await asyncio.to_thread(litellm.responses, **kwargs)
        except Exception:  # noqa: BLE001
            return ChatResponse(content=SAFE_CHAT_ERROR_MESSAGE, tool_called=False)

        deep_research_call = self._extract_function_call(first_response)

        if deep_research_call is None:
            content = self._extract_output_text(first_response)
            return ChatResponse(content=content, tool_called=False)

        raw_args = str(deep_research_call.get("arguments") or "{}")
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            tool_args = {}

        research_question = tool_args.get("research_question", request.message)
        # Use the model-chosen format, falling back to the caller's preferred format.
        deliverable_format = tool_args.get(
            "deliverable_format", request.deliverable_format
        )

        try:
            research_result = await self._invoke_deep_research(
                DeepResearchArguments(
                    research_question=research_question,
                    deliverable_format=deliverable_format,
                    system_prompt=request.system_prompt,
                )
            )
            research_summary = research_result.output_text or ""
        except Exception:  # noqa: BLE001
            # Surface as structured error rather than HTTP 500
            error_detail = SAFE_CHAT_ERROR_MESSAGE
            return ChatResponse(
                content=error_detail,
                tool_called=True,
                tool_name="deep_research",
                research_summary=error_detail,
            )

        response_id = self._extract_response_id(first_response)
        call_id = str(deep_research_call.get("call_id") or "call_0")

        second_kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "previous_response_id": response_id,
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": research_summary,
                }
            ],
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        try:
            second_response = await asyncio.to_thread(
                litellm.responses, **second_kwargs
            )
            final_content = (
                self._extract_output_text(second_response) or research_summary
            )
        except Exception:  # noqa: BLE001
            final_content = research_summary

        return ChatResponse(
            content=final_content,
            tool_called=True,
            tool_name="deep_research",
            research_summary=research_summary,
        )

    async def _invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        """게이트웨이를 통해 deep_research 실행을 위임한다."""
        return await self._gateway.invoke_deep_research(args)

    @staticmethod
    def _build_user_content(request: ChatRequest) -> str:
        """문맥 목록을 포함한 최종 사용자 메시지 문자열을 만든다."""
        if not request.context:
            return request.message
        context_block = "\n".join(f"- {item}" for item in request.context)
        return f"Context:\n{context_block}\n\n{request.message}"

    @staticmethod
    def _extract_function_call(response: Any) -> dict[str, Any] | None:
        output = ChatOrchestrator._extract_output_items(response)
        for item in output:
            if item.get("type") != "function_call":
                continue
            if item.get("name") != "deep_research":
                continue
            return item
        return None

    @staticmethod
    def _extract_output_items(response: Any) -> list[dict[str, Any]]:
        if isinstance(response, dict):
            output = response.get("output") or []
        elif hasattr(response, "output"):
            output = response.output or []
        else:
            output = []
        result: list[dict[str, Any]] = []
        for item in output:
            if isinstance(item, dict):
                result.append(item)
            elif hasattr(item, "model_dump"):
                dumped = item.model_dump()
                if isinstance(dumped, dict):
                    result.append(dumped)
        return result

    @staticmethod
    def _extract_output_text(response: Any) -> str:
        if isinstance(response, dict):
            payload = response
        elif hasattr(response, "model_dump"):
            payload = response.model_dump()
        else:
            payload = {
                "output_text": getattr(response, "output_text", None),
                "output": getattr(response, "output", []),
            }
        if not isinstance(payload, dict):
            return ""
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text
        parts: list[str] = []
        for item in ChatOrchestrator._extract_output_items(payload):
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") not in {"output_text", "text"}:
                    continue
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
                elif isinstance(text, dict):
                    value = text.get("value")
                    if isinstance(value, str) and value:
                        parts.append(value)
        return "".join(parts)

    @staticmethod
    def _extract_response_id(response: Any) -> str:
        if isinstance(response, dict):
            payload = response
        elif hasattr(response, "model_dump"):
            payload = response.model_dump()
        else:
            payload = {"id": getattr(response, "id", None)}
        if isinstance(payload, dict):
            response_id = payload.get("id")
            if isinstance(response_id, str) and response_id:
                return response_id
        raise ValueError("response id missing")
