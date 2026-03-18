from __future__ import annotations

from fastapi.testclient import TestClient

from litellm_relay.app import create_app
from litellm_relay.contracts import DeepResearchArguments
from litellm_relay.service import RelayService
from litellm_relay.upstream import UpstreamInvocationResult


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


def test_post_tool_invocations_returns_completed_result() -> None:
    client = TestClient(create_app(service=RelayService(FakeGateway(), 30.0)))

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
    client = TestClient(create_app(service=RelayService(FakeGateway(), 30.0)))

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
    client = TestClient(create_app(service=RelayService(FakeGateway(), 30.0)))

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
    client = TestClient(create_app(service=RelayService(FakeGateway(), 30.0)))

    response = client.get("/api/v1/tool-invocations/missing/events")

    assert response.status_code == 404
