"""도구 호출 상태 저장과 SSE 이벤트 생성을 담당한다."""

from __future__ import annotations

import asyncio
import json
import logging
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

SAFE_STREAM_ERROR_MESSAGE = "deep_research stream failed. Please retry later."
logger = logging.getLogger(__name__)


class InvocationNotFoundError(KeyError):
    """알 수 없는 호출 ID를 조회했을 때 발생한다."""


class InvocationCapacityError(RuntimeError):
    """릴레이가 더 많은 호출 상태를 안전하게 보관할 수 없을 때 발생한다."""


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
    stream_bytes: int = 0
    stream_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RelayService:
    """호출 상태를 메모리에 저장하고 게이트웨이 실행을 조율한다."""

    def __init__(
        self,
        gateway: LiteLLMRelayGateway,
        timeout_seconds: float,
        *,
        max_invocations: int = 1024,
        max_stream_bytes: int = 1_000_000,
    ) -> None:
        """게이트웨이와 대기 타임아웃을 보관한다."""
        self._gateway = gateway
        self._timeout_seconds = timeout_seconds
        self._max_invocations = max_invocations
        self._max_stream_bytes = max_stream_bytes
        self._store: dict[str, _StoredInvocation] = {}
        self._capacity_lock = asyncio.Lock()

    async def create_invocation(
        self, payload: ToolInvocationRequest
    ) -> tuple[int, ToolInvocationView]:
        """새 호출을 만들고 적절한 초기 응답 상태를 반환한다."""
        invocation_id = str(uuid4())
        args = payload.arguments
        stored = _StoredInvocation(
            request=payload,
            mode=(
                "stream"
                if args.stream
                else ("background" if args.background else "foreground")
            ),
            status=(
                "pending"
                if args.stream
                else ("queued" if args.background else "running")
            ),
        )

        async with self._capacity_lock:
            self._ensure_capacity()
            self._store[invocation_id] = stored

        if args.stream:
            return 202, self._to_view(invocation_id, stored)

        try:
            result = await self._gateway.invoke_deep_research(args)
        except Exception:
            async with self._capacity_lock:
                self._store.pop(invocation_id, None)
            raise

        stored.mode = result.mode
        stored.status = "queued" if result.mode == "background" else "completed"
        stored.upstream_response_id = result.upstream_response_id
        stored.output_text = result.output_text
        stored.response = result.response
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
        if stored.mode == "stream":
            async with stored.stream_lock:
                should_start_stream = not stored.stream_started
                if should_start_stream:
                    stored.stream_started = True
                    stored.status = "running"
        else:
            should_start_stream = False

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

        if not should_start_stream:
            for chunk in stored.stream_chunks:
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="output_text",
                        status=(
                            "running" if stored.status == "running" else stored.status
                        ),
                        data={"text": chunk},
                    )
                )
            if stored.status == "completed":
                yield self._to_sse(
                    ToolInvocationEvent(
                        invocation_id=invocation_id,
                        type="completed",
                        status="completed",
                        data={"output_text": self._completed_stream_text(stored) or ""},
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

        try:
            async for chunk in self._gateway.stream_deep_research(
                stored.request.arguments
            ):
                chunk_bytes = len(chunk.encode("utf-8"))
                if stored.stream_bytes + chunk_bytes > self._max_stream_bytes:
                    stored.status = "failed"
                    stored.error_message = "stream output exceeded relay memory limit"
                    stored.output_text = None
                    stored.response = None
                    yield self._to_sse(
                        ToolInvocationEvent(
                            invocation_id=invocation_id,
                            type="error",
                            status="failed",
                            data={"message": stored.error_message},
                        )
                    )
                    return
                stored.stream_bytes += chunk_bytes
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
            yield self._to_sse(
                ToolInvocationEvent(
                    invocation_id=invocation_id,
                    type="completed",
                    status="completed",
                    data={"output_text": self._completed_stream_text(stored)},
                )
            )
        except Exception:
            logger.exception("Stream failed for invocation %s", invocation_id)
            stored.status = "failed"
            stored.error_message = SAFE_STREAM_ERROR_MESSAGE
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
    def _completed_stream_text(stored: _StoredInvocation) -> str | None:
        if stored.mode == "stream" and stored.status == "completed":
            return "".join(stored.stream_chunks)
        return stored.output_text

    def _ensure_capacity(self) -> None:
        while len(self._store) >= self._max_invocations:
            oldest_terminal_id = next(
                (
                    invocation_id
                    for invocation_id, stored in self._store.items()
                    if stored.status in {"completed", "failed"}
                ),
                None,
            )
            if oldest_terminal_id is None:
                raise InvocationCapacityError(
                    "relay is at invocation capacity; retry later"
                )
            self._store.pop(oldest_terminal_id)

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
        output_text = RelayService._completed_stream_text(stored)
        response = stored.response
        if stored.mode == "stream" and stored.status == "completed" and output_text:
            response = {"output_text": output_text}

        return ToolInvocationView(
            invocation_id=invocation_id,
            tool_name=stored.request.tool_name,
            mode=stored.mode,
            status=stored.status,
            deliverable_format=stored.request.arguments.deliverable_format,
            upstream_response_id=stored.upstream_response_id,
            output_text=output_text,
            response=response,
            error_message=stored.error_message,
        )

    @staticmethod
    def _to_sse(event: ToolInvocationEvent) -> str:
        """이벤트 모델을 SSE 텍스트 프레임으로 직렬화한다."""
        payload = json.dumps(event.model_dump(), ensure_ascii=False)
        return f"event: {event.type}\ndata: {payload}\n\n"
