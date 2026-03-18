from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import litellm

from .contracts import DeepResearchArguments, InvocationMode


@dataclass(frozen=True)
class UpstreamInvocationResult:
    mode: InvocationMode
    status: str
    upstream_response_id: str | None = None
    output_text: str | None = None
    response: dict[str, Any] | None = None


class LiteLLMRelayGateway:
    """Translate the relay contract into LiteLLM SDK calls."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "o3-deep-research",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._model = (
            model if model.startswith("litellm_proxy/") else f"litellm_proxy/{model}"
        )
        self._timeout_seconds = timeout_seconds

    async def invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        payload = await asyncio.to_thread(
            litellm.responses,
            model=self._model,
            input=self._render_input(args),
            api_base=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            background=args.background,
        )
        response = self._to_dict(payload)

        if args.background:
            return UpstreamInvocationResult(
                mode="background",
                status=str(response.get("status", "queued")),
                upstream_response_id=self._maybe_str(response.get("id")),
                response=response,
            )

        return UpstreamInvocationResult(
            mode="foreground",
            status=str(response.get("status", "completed")),
            upstream_response_id=self._maybe_str(response.get("id")),
            output_text=self._extract_response_text(response),
            response=response,
        )

    async def get_response(self, response_id: str) -> dict[str, Any]:
        payload = await litellm.aget_responses(
            response_id=response_id,
            api_base=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
        )
        return self._to_dict(payload)

    async def wait_for_response(
        self,
        response_id: str,
        timeout_seconds: float,
        poll_interval_seconds: float = 0.05,
    ) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            payload = await self.get_response(response_id)
            status = str(payload.get("status", "completed"))
            if status in {"completed", "failed", "cancelled"}:
                return payload
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(
                    f"Timed out while waiting for upstream response {response_id}."
                )
            await asyncio.sleep(poll_interval_seconds)

    async def stream_deep_research(
        self, args: DeepResearchArguments
    ) -> AsyncIterator[str]:
        response = await litellm.aresponses(
            model=self._model,
            input=self._render_input(args),
            api_base=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            stream=True,
        )

        async for event in response:
            text = self._extract_stream_text(self._to_dict(event))
            if text:
                yield text

    @staticmethod
    def _render_input(args: DeepResearchArguments) -> str:
        lines = [
            "Tool: deep_research",
            f"Research question: {args.research_question}",
            f"Deliverable format: {args.deliverable_format}",
            f"Require citations: {'yes' if args.require_citations else 'no'}",
        ]
        if args.context:
            lines.append("Context:")
            lines.extend(f"- {item}" for item in args.context)
        if args.constraints:
            lines.append("Constraints:")
            lines.extend(f"- {item}" for item in args.constraints)
        return "\n".join(lines)

    @staticmethod
    def _to_dict(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        if hasattr(payload, "model_dump"):
            data = payload.model_dump()
            if isinstance(data, dict):
                return data
        if hasattr(payload, "dict"):
            data = payload.dict()
            if isinstance(data, dict):
                return data
        raise TypeError(f"Unsupported payload type from LiteLLM: {type(payload)!r}")

    @staticmethod
    def _maybe_str(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None

    @classmethod
    def _extract_response_text(cls, payload: dict[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        parts: list[str] = []
        for item in payload.get("output") or []:
            if not isinstance(item, dict):
                continue
            for block in item.get("content") or []:
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

    @classmethod
    def _extract_stream_text(cls, payload: dict[str, Any]) -> str | None:
        if payload.get("type") == "response.output_text.delta":
            delta = payload.get("delta")
            if isinstance(delta, str) and delta:
                return delta
        return None
