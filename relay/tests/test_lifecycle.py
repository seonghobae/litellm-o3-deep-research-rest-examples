from __future__ import annotations

from fastapi.testclient import TestClient

from litellm_relay.app import create_app
from litellm_relay.config import RelaySettings
from litellm_relay.contracts import DeepResearchArguments
from litellm_relay.service import RelayService
from litellm_relay.upstream import UpstreamInvocationResult

_DUMMY_SETTINGS = RelaySettings(base_url="https://dummy.test", api_key="sk-dummy")


class LifecycleGateway:
    def __init__(self) -> None:
        self.stream_calls = 0

    async def invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        if args.stream:
            return UpstreamInvocationResult(
                mode="stream",
                status="pending",
                response={"status": "pending"},
            )
        return UpstreamInvocationResult(
            mode="background",
            status="queued",
            upstream_response_id="resp_lifecycle_1",
            response={"id": "resp_lifecycle_1", "status": "queued"},
        )

    async def get_response(self, response_id: str) -> dict[str, object]:
        return {"id": response_id, "status": "queued"}

    async def wait_for_response(
        self, response_id: str, timeout_seconds: float
    ) -> dict[str, object]:
        return {
            "id": response_id,
            "status": "completed",
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": {"value": "relay wait result"}}
                    ]
                }
            ],
        }

    async def stream_deep_research(self, args: DeepResearchArguments):
        self.stream_calls += 1
        yield "Hello"
        yield " world"


class FailingLifecycleGateway(LifecycleGateway):
    async def stream_deep_research(self, args: DeepResearchArguments):
        self.stream_calls += 1
        raise RuntimeError("stream exploded")
        yield  # pragma: no cover


def test_wait_endpoint_polls_upstream_until_completed() -> None:
    client = TestClient(
        create_app(
            service=RelayService(LifecycleGateway(), 30.0), settings=_DUMMY_SETTINGS
        )
    )

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
    wait_response = client.get(f"/api/v1/tool-invocations/{invocation_id}/wait")

    assert wait_response.status_code == 200
    payload = wait_response.json()
    assert payload["status"] == "completed"
    assert payload["output_text"] == "relay wait result"


def test_events_endpoint_relays_text_deltas_as_sse() -> None:
    gateway = LifecycleGateway()
    client = TestClient(
        create_app(service=RelayService(gateway, 30.0), settings=_DUMMY_SETTINGS)
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Stream relay architecture.",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )

    invocation_id = create_response.json()["invocation_id"]

    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: output_text" in body
    assert "Hello" in body
    assert "world" in body
    assert "event: completed" in body
    assert gateway.stream_calls == 1

    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as replay_response:
        replay_body = "".join(replay_response.iter_text())

    assert replay_response.status_code == 200
    assert "Hello" in replay_body
    assert "world" in replay_body
    assert "event: completed" in replay_body
    assert gateway.stream_calls == 1


def test_events_endpoint_marks_failed_streams() -> None:
    client = TestClient(
        create_app(
            service=RelayService(FailingLifecycleGateway(), 30.0),
            settings=_DUMMY_SETTINGS,
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Break relay architecture.",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: error" in body

    status_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")
    assert status_response.json()["status"] == "failed"
