"""LiteLLM 릴레이용 FastAPI 애플리케이션을 구성한다."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from .chat_orchestrator import ChatOrchestrator
from .config import RelaySettings, load_settings
from .contracts import (
    ChatRequest,
    ChatResponse,
    ToolInvocationRequest,
    ToolInvocationView,
)
from .service import InvocationCapacityError, InvocationNotFoundError, RelayService
from .upstream import LiteLLMRelayGateway


def create_app(
    service: RelayService | None = None,
    settings: RelaySettings | None = None,
) -> FastAPI:
    """LiteLLM 릴레이 예제용 FastAPI 애플리케이션을 생성한다."""
    settings = settings or load_settings()
    service = service or RelayService(
        LiteLLMRelayGateway(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
        ),
        timeout_seconds=settings.timeout_seconds,
        max_invocations=settings.max_invocations,
        max_stream_bytes=settings.max_stream_bytes,
    )

    orchestrator_instance = ChatOrchestrator(
        base_url=settings.base_url,
        api_key=settings.api_key,
        chat_model=f"litellm_proxy/{settings.chat_model}",
        research_model=f"litellm_proxy/{settings.model}",
        timeout_seconds=settings.timeout_seconds,
        research_timeout_seconds=settings.research_timeout_seconds,
    )

    app = FastAPI(title="LiteLLM relay example")

    @app.post("/api/v1/tool-invocations", response_model=ToolInvocationView)
    async def create_tool_invocation(
        payload: ToolInvocationRequest,
    ) -> JSONResponse | ToolInvocationView:
        """도구 호출을 생성하고 즉시 반환 가능한 상태를 응답한다."""
        try:
            status_code, result = await service.create_invocation(payload)
        except InvocationCapacityError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if status_code == 200:
            return result
        return JSONResponse(status_code=status_code, content=result.model_dump())

    @app.get(
        "/api/v1/tool-invocations/{invocation_id}", response_model=ToolInvocationView
    )
    async def get_tool_invocation(invocation_id: str) -> ToolInvocationView:
        """현재 도구 호출 상태를 조회한다."""
        try:
            return await service.get_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc

    @app.get(
        "/api/v1/tool-invocations/{invocation_id}/wait",
        response_model=ToolInvocationView,
    )
    async def wait_for_tool_invocation(invocation_id: str) -> ToolInvocationView:
        """도구 호출이 끝날 때까지 기다린 뒤 최종 상태를 반환한다."""
        try:
            return await service.wait_for_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc

    @app.get("/api/v1/tool-invocations/{invocation_id}/events")
    async def stream_tool_invocation_events(invocation_id: str) -> StreamingResponse:
        """도구 호출의 SSE 이벤트 스트림을 연다."""
        try:
            await service.get_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc
        return StreamingResponse(
            service.event_stream(invocation_id),
            media_type="text/event-stream",
        )

    @app.post("/api/v1/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest) -> ChatResponse:
        """자동 도구 호출을 포함한 채팅 요청을 처리한다."""
        return await orchestrator_instance.chat(payload)

    return app
