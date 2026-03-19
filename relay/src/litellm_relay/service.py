from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .contracts import (
    InvocationMode,
    InvocationStatus,
    ToolInvocationEvent,
    ToolInvocationRequest,
    ToolInvocationView,
)
from .upstream import LiteLLMRelayGateway, UpstreamInvocationResult


class InvocationNotFoundError(KeyError):
    """Raised when an invocation id is unknown."""


@dataclass
class _StoredInvocation:
    request: ToolInvocationRequest
    mode: InvocationMode
    status: InvocationStatus
    upstream_response_id: str | None = None
    output_text: str | None = None
    response: dict[str, Any] | None = None
    error_message: str | None = None
    stream_started: bool = False
    stream_chunks: list[str] = field(default_factory=list)


class RelayService:
    def __init__(self, gateway: LiteLLMRelayGateway, timeout_seconds: float) -> None:
        self._gateway = gateway
        self._timeout_seconds = timeout_seconds
        self._store: dict[str, _StoredInvocation] = {}

    async def create_invocation(
        self, payload: ToolInvocationRequest
    ) -> tuple[int, ToolInvocationView]:
        invocation_id = str(uuid4())
        args = payload.arguments

        if args.stream:
            stored = _StoredInvocation(
                request=payload,
                mode="stream",
                status="pending",
            )
            self._store[invocation_id] = stored
            return 202, self._to_view(invocation_id, stored)

        result = await self._gateway.invoke_deep_research(args)
        stored = self._from_result(payload, result)
        self._store[invocation_id] = stored
        status_code = 202 if stored.mode == "background" else 200
        return status_code, self._to_view(invocation_id, stored)

    async def get_invocation(self, invocation_id: str) -> ToolInvocationView:
        stored = self._require(invocation_id)
        if stored.mode == "background" and stored.upstream_response_id:
            payload = await self._gateway.get_response(stored.upstream_response_id)
            self._apply_upstream_payload(stored, payload)
        return self._to_view(invocation_id, stored)

    async def wait_for_invocation(self, invocation_id: str) -> ToolInvocationView:
        stored = self._require(invocation_id)
        if stored.mode == "background" and stored.upstream_response_id:
            payload = await self._gateway.wait_for_response(
                stored.upstream_response_id,
                timeout_seconds=self._timeout_seconds,
            )
            self._apply_upstream_payload(stored, payload)
        return self._to_view(invocation_id, stored)

    async def event_stream(self, invocation_id: str):
        stored = self._require(invocation_id)
        yield self._to_sse(
            ToolInvocationEvent(
                invocation_id=invocation_id,
                type="status",
                status=stored.status,
                data={"mode": stored.mode},
            )
        )

        if stored.mode != "stream":
            if stored.output_text:
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="completed",
                        status=stored.status,
                        data={"output_text": stored.output_text},
                    )
                )
            return

        if stored.stream_started:
            for chunk in stored.stream_chunks:
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="output_text",
                        status="running"
                        if stored.status == "running"
                        else stored.status,
                        data={"text": chunk},
                    )
                )
            if stored.status == "completed":
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="completed",
                        status="completed",
                        data={"output_text": stored.output_text or ""},
                    )
                )
            elif stored.status == "failed":
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="error",
                        status="failed",
                        data={"message": stored.error_message or "stream failed"},
                    )
                )
            return

        stored.stream_started = True
        stored.status = "running"
        try:
            async for chunk in self._gateway.stream_deep_research(
                stored.request.arguments
            ):
                stored.stream_chunks.append(chunk)
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="output_text",
                        status="running",
                        data={"text": chunk},
                    )
                )
            stored.status = "completed"
            stored.output_text = "".join(stored.stream_chunks)
            stored.response = {"output_text": stored.output_text}
            yield self._to_sse(
                ToolInvocationEvent(
                    invocation_id=invocation_id,
                    type="completed",
                    status="completed",
                    data={"output_text": stored.output_text},
                )
            )
        except Exception as exc:
            stored.status = "failed"
            stored.error_message = str(exc)
            yield self._to_sse(
                ToolInvocationEvent(
                    invocation_id=invocation_id,
                    type="error",
                    status="failed",
                    data={"message": stored.error_message},
                )
            )

    def _require(self, invocation_id: str) -> _StoredInvocation:
        stored = self._store.get(invocation_id)
        if stored is None:
            raise InvocationNotFoundError(invocation_id)
        return stored

    @staticmethod
    def _from_result(
        payload: ToolInvocationRequest, result: UpstreamInvocationResult
    ) -> _StoredInvocation:
        status: InvocationStatus = (
            "queued" if result.mode == "background" else "completed"
        )
        return _StoredInvocation(
            request=payload,
            mode=result.mode,
            status=status,
            upstream_response_id=result.upstream_response_id,
            output_text=result.output_text,
            response=result.response,
        )

    @staticmethod
    def _apply_upstream_payload(
        stored: _StoredInvocation, payload: dict[str, Any]
    ) -> None:
        status = str(payload.get("status", stored.status))
        if status == "completed":
            stored.status = "completed"
            output_text = LiteLLMRelayGateway._extract_response_text(payload)
            if output_text:
                stored.output_text = output_text
        elif status in {"queued", "running", "pending"}:
            stored.status = status  # type: ignore[assignment]
        else:
            stored.status = "failed"
            stored.error_message = status
        stored.response = payload

    @staticmethod
    def _to_view(invocation_id: str, stored: _StoredInvocation) -> ToolInvocationView:
        return ToolInvocationView(
            invocation_id=invocation_id,
            tool_name=stored.request.tool_name,
            mode=stored.mode,
            status=stored.status,
            deliverable_format=stored.request.arguments.deliverable_format,
            upstream_response_id=stored.upstream_response_id,
            output_text=stored.output_text,
            response=stored.response,
            error_message=stored.error_message,
        )

    @staticmethod
    def _to_sse(event: ToolInvocationEvent) -> str:
        payload = json.dumps(event.model_dump(), ensure_ascii=False)
        return f"event: {event.type}\ndata: {payload}\n\n"
