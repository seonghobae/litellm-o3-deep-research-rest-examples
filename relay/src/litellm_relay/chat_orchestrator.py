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

    Timeout split
    -------------
    ``timeout_seconds`` governs Chat Completions turns (fast, typically <30 s).
    ``research_timeout_seconds`` governs the deep_research invocation
    (slow — ``o3-deep-research`` regularly takes 2–10 minutes).  The default
    for ``research_timeout_seconds`` is 300 s but can be raised via
    ``RELAY_RESEARCH_TIMEOUT_SECONDS``.

    Error handling
    --------------
    Upstream errors during research are caught and returned as a
    :class:`~litellm_relay.contracts.ChatResponse` with ``tool_called=True``
    and an ``error_detail`` payload in ``research_summary`` so callers receive
    a structured response rather than a bare HTTP 500.

    system_prompt and deliverable_format passthrough
    ------------------------------------------------
    ``ChatRequest.system_prompt`` is forwarded to ``DeepResearchArguments``
    when the model triggers the deep_research tool call.  It maps to the
    Responses API ``instructions`` field so the research step can be given
    a persona, output language, or format constraint.

    ``ChatRequest.deliverable_format`` is used as the *fallback* when the
    Chat Completions model does not specify a format in its tool-call
    arguments.  The model's chosen format always takes precedence.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str = "litellm_proxy/gpt-4o",
        research_model: str = "litellm_proxy/o3-deep-research",
        timeout_seconds: float = 30.0,
        research_timeout_seconds: float = 300.0,
    ) -> None:
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

        tool_calls = self._extract_tool_calls(first_message)
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
        except Exception as exc:  # noqa: BLE001
            # Surface as structured error rather than HTTP 500
            error_detail = f"deep_research failed: {exc}"
            return ChatResponse(
                content=error_detail,
                tool_called=True,
                tool_name="deep_research",
                research_summary=error_detail,
            )

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
    def _extract_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]]:
        """Normalise tool_calls from a message dict into a list of plain dicts.

        The LiteLLM SDK may return ``tool_calls`` as:
        - ``None`` / missing
        - a list of plain dicts
        - a list of Pydantic-like objects with ``model_dump()``
        """
        raw = message.get("tool_calls")
        if not raw:
            return []
        result: list[dict[str, Any]] = []
        for tc in raw:
            if isinstance(tc, dict):
                result.append(tc)
            elif hasattr(tc, "model_dump"):
                dumped = tc.model_dump()
                if isinstance(dumped, dict):
                    result.append(dumped)
        return result

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
