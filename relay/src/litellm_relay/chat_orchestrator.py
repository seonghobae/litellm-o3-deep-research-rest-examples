from __future__ import annotations

import asyncio
import json
from typing import Any

import litellm

from .contracts import ChatRequest, ChatResponse, DeepResearchArguments
from .upstream import LiteLLMRelayGateway, UpstreamInvocationResult

DEEP_RESEARCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
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
    },
}


class ChatOrchestrator:
    """Relay-side orchestration for automatic deep_research tool calling.

    Flow
    ----
    1. Build a Chat Completions request with the ``deep_research`` function
       tool attached (when ``request.auto_tool_call`` is True).
    2. If the model responds with ``finish_reason == "tool_calls"`` for
       ``deep_research``, execute the research via the upstream relay gateway.
    3. Append the tool result to the conversation and send a second Chat
       Completions request to obtain the final natural-language answer.
    4. Return a :class:`~litellm_relay.contracts.ChatResponse` capturing
       whether a tool was called and, if so, the research summary.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str = "litellm_proxy/gpt-4o",
        research_model: str = "litellm_proxy/o3-deep-research",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._chat_model = chat_model
        self._timeout_seconds = timeout_seconds
        self._gateway = LiteLLMRelayGateway(
            base_url=base_url,
            api_key=api_key,
            model=research_model.removeprefix("litellm_proxy/"),
            timeout_seconds=timeout_seconds,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Perform an orchestrated chat turn, optionally invoking deep_research."""
        user_content = self._build_user_content(request)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        if request.auto_tool_call:
            kwargs["tools"] = [DEEP_RESEARCH_TOOL_SCHEMA]

        first_response = await asyncio.to_thread(litellm.completion, **kwargs)
        first_choice = self._extract_choice(first_response)
        first_message = first_choice.get("message", {})

        tool_calls = first_message.get("tool_calls") or []
        deep_research_call = next(
            (
                tc
                for tc in tool_calls
                if isinstance(tc, dict)
                and tc.get("type") == "function"
                and (tc.get("function") or {}).get("name") == "deep_research"
            ),
            None,
        )

        if deep_research_call is None:
            content = first_message.get("content") or ""
            return ChatResponse(content=content, tool_called=False)

        raw_args = (deep_research_call.get("function") or {}).get("arguments", "{}")
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            tool_args = {}

        research_question = tool_args.get("research_question", request.message)
        deliverable_format = tool_args.get("deliverable_format", "markdown_brief")

        research_result = await self._invoke_deep_research(
            DeepResearchArguments(
                research_question=research_question,
                deliverable_format=deliverable_format,
            )
        )
        research_summary = research_result.output_text or ""

        tool_call_id = deep_research_call.get("id", "call_0")
        messages_with_result: list[dict[str, Any]] = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": None, "tool_calls": [deep_research_call]},
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": research_summary,
            },
        ]

        second_kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages_with_result,
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        second_response = await asyncio.to_thread(litellm.completion, **second_kwargs)
        second_choice = self._extract_choice(second_response)
        final_content = (second_choice.get("message") or {}).get("content") or ""

        return ChatResponse(
            content=final_content,
            tool_called=True,
            tool_name="deep_research",
            research_summary=research_summary,
        )

    async def _invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        return await self._gateway.invoke_deep_research(args)

    @staticmethod
    def _build_user_content(request: ChatRequest) -> str:
        if not request.context:
            return request.message
        context_block = "\n".join(f"- {item}" for item in request.context)
        return f"Context:\n{context_block}\n\n{request.message}"

    @staticmethod
    def _extract_choice(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            choices = response.get("choices") or []
        elif hasattr(response, "choices"):
            choices = response.choices or []
        else:
            choices = []
        if not choices:
            return {}
        first = choices[0]
        if isinstance(first, dict):
            return first
        if hasattr(first, "model_dump"):
            result = first.model_dump()
            return result if isinstance(result, dict) else {}
        return {}
