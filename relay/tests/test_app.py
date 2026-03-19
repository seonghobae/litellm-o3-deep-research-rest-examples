from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from litellm_relay.app import create_app
from litellm_relay.config import RelaySettings
from litellm_relay.contracts import ChatResponse, DeepResearchArguments
from litellm_relay.service import RelayService
from litellm_relay.upstream import UpstreamInvocationResult

# Settings object used to prevent create_app() from calling load_settings()
# which requires LITELLM_BASE_URL/LITELLM_API_KEY environment variables.
_DUMMY_SETTINGS = RelaySettings(
    base_url="https://dummy.test",
    api_key="sk-dummy",
    research_timeout_seconds=300.0,
)


class FakeGateway:
    async def invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        if args.background:
            return UpstreamInvocationResult(
                mode="background",
                status="queued",
                upstream_response_id="resp_background_42",
                response={"id": "resp_background_42", "status": "queued"},
            )

        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="relay completed text",
            response={
                "id": "resp_foreground_42",
                "output_text": "relay completed text",
            },
        )

    async def get_response(self, response_id: str) -> dict[str, object]:
        return {"id": response_id, "status": "completed", "output_text": "done"}

    async def wait_for_response(
        self, response_id: str, timeout_seconds: float
    ) -> dict[str, object]:
        return {"id": response_id, "status": "completed", "output_text": "done"}

    async def stream_deep_research(self, args: DeepResearchArguments):
        yield "ignored"


def _client() -> TestClient:
    """Create a TestClient with a fake service and dummy settings so that
    create_app() never calls load_settings() and thus never needs live env vars."""
    return TestClient(
        create_app(service=RelayService(FakeGateway(), 30.0), settings=_DUMMY_SETTINGS)
    )


def test_post_tool_invocations_returns_completed_result() -> None:
    client = _client()

    response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Summarize relay architecture.",
                "deliverable_format": "markdown_brief",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "foreground"
    assert payload["status"] == "completed"
    assert payload["output_text"] == "relay completed text"


def test_post_tool_invocations_returns_background_metadata() -> None:
    client = _client()

    response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Queue relay architecture.",
                "deliverable_format": "markdown_brief",
                "background": True,
            },
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["mode"] == "background"
    assert payload["status"] == "queued"
    assert payload["upstream_response_id"] == "resp_background_42"


def test_get_tool_invocations_by_id_returns_latest_status() -> None:
    client = _client()

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Queue relay architecture.",
                "deliverable_format": "markdown_brief",
                "background": True,
            },
        },
    )

    invocation_id = create_response.json()["invocation_id"]
    fetch_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")

    assert fetch_response.status_code == 200
    payload = fetch_response.json()
    assert payload["invocation_id"] == invocation_id
    assert payload["status"] == "completed"
    assert payload["output_text"] == "done"


def test_events_endpoint_returns_404_for_unknown_invocation() -> None:
    client = _client()

    response = client.get("/api/v1/tool-invocations/missing/events")

    assert response.status_code == 404


def test_get_invocation_returns_404_for_unknown_id() -> None:
    """GET /api/v1/tool-invocations/{id} must return 404 for an unknown id."""
    client = _client()
    response = client.get("/api/v1/tool-invocations/does-not-exist")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_wait_invocation_returns_404_for_unknown_id() -> None:
    """GET /api/v1/tool-invocations/{id}/wait must return 404 for an unknown id."""
    client = _client()
    response = client.get("/api/v1/tool-invocations/does-not-exist/wait")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.fixture()
def client() -> TestClient:
    """Pytest fixture variant of _client() for use with new chat tests."""
    return _client()


def test_post_chat_returns_direct_answer(client: TestClient) -> None:
    """POST /api/v1/chat with auto_tool_call=False returns plain assistant answer."""
    with patch(
        "litellm_relay.app.ChatOrchestrator.chat",
        new_callable=AsyncMock,
        return_value=ChatResponse(content="hello", tool_called=False),
    ):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "안녕", "auto_tool_call": False},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "hello"
    assert data["tool_called"] is False


def test_post_chat_returns_tool_called_response(client: TestClient) -> None:
    """POST /api/v1/chat that triggers deep_research returns tool metadata."""
    with patch(
        "litellm_relay.app.ChatOrchestrator.chat",
        new_callable=AsyncMock,
        return_value=ChatResponse(
            content="짜장면의 역사는...",
            tool_called=True,
            tool_name="deep_research",
            research_summary="인천 차이나타운 기원",
        ),
    ):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "짜장면의 역사를 알려줘"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_called"] is True
    assert data["tool_name"] == "deep_research"
    assert data["research_summary"] == "인천 차이나타운 기원"
