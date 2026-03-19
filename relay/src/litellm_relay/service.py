"""도구 호출 상태 저장과 SSE 이벤트 생성을 담당한다."""

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
    """알 수 없는 호출 ID를 조회했을 때 발생한다."""


@dataclass
class _StoredInvocation:
    """메모리에 유지되는 도구 호출 상태 레코드다."""

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
    """호출 상태를 메모리에 저장하고 게이트웨이 실행을 조율한다."""

    def __init__(self, gateway: LiteLLMRelayGateway, timeout_seconds: float) -> None:
        """게이트웨이와 대기 타임아웃을 보관한다."""
        self._gateway = gateway
        self._timeout_seconds = timeout_seconds
        self._store: dict[str, _StoredInvocation] = {}

    async def create_invocation(
        self, payload: ToolInvocationRequest
    ) -> tuple[int, ToolInvocationView]:
        """새 호출을 만들고 적절한 초기 응답 상태를 반환한다."""
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
        """필요하면 업스트림 상태를 새로고침한 뒤 현재 호출 뷰를 반환한다."""
        stored = self._require(invocation_id)
        if stored.mode == "background" and stored.upstream_response_id:
            payload = await self._gateway.get_response(stored.upstream_response_id)
            self._apply_upstream_payload(stored, payload)
        return self._to_view(invocation_id, stored)

    async def wait_for_invocation(self, invocation_id: str) -> ToolInvocationView:
        """업스트림 완료까지 기다린 뒤 최종 호출 뷰를 반환한다."""
        stored = self._require(invocation_id)
        if stored.mode == "background" and stored.upstream_response_id:
            payload = await self._gateway.wait_for_response(
                stored.upstream_response_id,
                timeout_seconds=self._timeout_seconds,
            )
            self._apply_upstream_payload(stored, payload)
        return self._to_view(invocation_id, stored)

    async def event_stream(self, invocation_id: str):
        """지정한 호출에 대한 SSE 프레임을 비동기로 생성한다."""
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
        """저장소에서 호출을 조회하고 없으면 예외를 발생시킨다."""
        stored = self._store.get(invocation_id)
        if stored is None:
            raise InvocationNotFoundError(invocation_id)
        return stored

    @staticmethod
    def _from_result(
        payload: ToolInvocationRequest, result: UpstreamInvocationResult
    ) -> _StoredInvocation:
        """업스트림 결과를 내부 저장 레코드로 변환한다."""
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
        """업스트림 응답을 저장된 호출 상태에 반영한다."""
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
        """내부 저장 상태를 외부 응답 모델로 변환한다."""
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
        """이벤트 모델을 SSE 텍스트 프레임으로 직렬화한다."""
        payload = json.dumps(event.model_dump(), ensure_ascii=False)
        return f"event: {event.type}\ndata: {payload}\n\n"
