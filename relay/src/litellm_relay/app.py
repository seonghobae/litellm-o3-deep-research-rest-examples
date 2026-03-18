from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from .config import RelaySettings, load_settings
from .contracts import ToolInvocationRequest, ToolInvocationView
from .service import InvocationNotFoundError, RelayService
from .upstream import LiteLLMRelayGateway


def create_app(
    service: RelayService | None = None,
    settings: RelaySettings | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    service = service or RelayService(
        LiteLLMRelayGateway(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.model,
            timeout_seconds=settings.timeout_seconds,
        ),
        timeout_seconds=settings.timeout_seconds,
    )

    app = FastAPI(title="LiteLLM relay example")

    @app.post("/api/v1/tool-invocations")
    async def create_tool_invocation(payload: ToolInvocationRequest):
        status_code, result = await service.create_invocation(payload)
        if status_code == 200:
            return result
        return JSONResponse(status_code=status_code, content=result.model_dump())

    @app.get(
        "/api/v1/tool-invocations/{invocation_id}", response_model=ToolInvocationView
    )
    async def get_tool_invocation(invocation_id: str) -> ToolInvocationView:
        try:
            return await service.get_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc

    @app.get(
        "/api/v1/tool-invocations/{invocation_id}/wait",
        response_model=ToolInvocationView,
    )
    async def wait_for_tool_invocation(invocation_id: str) -> ToolInvocationView:
        try:
            return await service.wait_for_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc

    @app.get("/api/v1/tool-invocations/{invocation_id}/events")
    async def stream_tool_invocation_events(invocation_id: str) -> StreamingResponse:
        try:
            await service.get_invocation(invocation_id)
        except InvocationNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Invocation not found") from exc
        return StreamingResponse(
            service.event_stream(invocation_id),
            media_type="text/event-stream",
        )

    return app
