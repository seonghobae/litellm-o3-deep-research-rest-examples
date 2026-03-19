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


def test_get_invocation_returns_view_for_foreground_mode_without_calling_gateway() -> (
    None
):
    """GET on a foreground invocation must not call the gateway (mode != background)."""

    class ForegroundOnlyGateway:
        called = False

        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="foreground",
                status="completed",
                output_text="foreground answer",
                response={"output_text": "foreground answer"},
            )

        async def get_response(self, response_id: str) -> dict[str, object]:
            ForegroundOnlyGateway.called = True
            raise AssertionError(
                "get_response must not be called for foreground invocations"
            )

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            raise AssertionError(
                "wait_for_response must not be called for foreground invocations"
            )

        async def stream_deep_research(self, args: DeepResearchArguments):
            raise AssertionError(
                "stream_deep_research must not be called for foreground invocations"
            )
            yield  # pragma: no cover

    client = TestClient(
        create_app(
            service=RelayService(ForegroundOnlyGateway(), 30.0),
            settings=_DUMMY_SETTINGS,
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Foreground question",
                "deliverable_format": "markdown_brief",
            },
        },
    )
    assert create_response.status_code == 200

    invocation_id = create_response.json()["invocation_id"]
    get_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")

    assert get_response.status_code == 200
    payload = get_response.json()
    assert payload["mode"] == "foreground"
    assert payload["status"] == "completed"
    assert payload["output_text"] == "foreground answer"
    assert not ForegroundOnlyGateway.called


def test_event_stream_for_foreground_invocation_with_no_output_text_terminates_cleanly() -> (
    None
):
    """event_stream() on a foreground result without output_text must not hang.

    The generator should emit only the initial ``status`` event and return
    without emitting a ``completed`` event (since there is no output text to
    report).
    """

    class EmptyForegroundGateway:
        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="foreground",
                status="completed",
                output_text=None,
                response={"status": "completed"},
            )

        async def get_response(self, response_id: str) -> dict[str, object]:
            return {}

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            return {}

        async def stream_deep_research(self, args: DeepResearchArguments):
            return
            yield  # pragma: no cover

    client = TestClient(
        create_app(
            service=RelayService(EmptyForegroundGateway(), 30.0),
            settings=_DUMMY_SETTINGS,
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Empty foreground question",
                "deliverable_format": "markdown_brief",
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "event: status" in body
    # No output_text → no completed event should be emitted
    assert "event: completed" not in body


def test_apply_upstream_payload_sets_status_to_failed_for_unknown_status() -> None:
    """Upstream payloads with unexpected status strings should map to 'failed'."""

    class CancelledGateway:
        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="background",
                status="queued",
                upstream_response_id="resp_cancelled",
                response={"id": "resp_cancelled", "status": "queued"},
            )

        async def get_response(self, response_id: str) -> dict[str, object]:
            return {"id": response_id, "status": "cancelled", "error": "user cancelled"}

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            return {"id": response_id, "status": "cancelled", "error": "user cancelled"}

        async def stream_deep_research(self, args: DeepResearchArguments):
            return
            yield  # pragma: no cover

    client = TestClient(
        create_app(
            service=RelayService(CancelledGateway(), 30.0), settings=_DUMMY_SETTINGS
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Will be cancelled",
                "deliverable_format": "markdown_brief",
                "background": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    # GET should apply the upstream payload and map "cancelled" → "failed"
    get_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "failed"


def test_to_view_includes_error_message_when_stream_fails() -> None:
    """After a failed stream, the GET endpoint must expose the error_message field."""
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
                "research_question": "Will fail",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    # Drive the stream to consume the error
    with client.stream("GET", f"/api/v1/tool-invocations/{invocation_id}/events") as r:
        "".join(r.iter_text())

    # Now GET the invocation and assert error_message is populated
    get_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")
    payload = get_response.json()
    assert payload["status"] == "failed"
    assert payload["error_message"] is not None
    assert "stream exploded" in payload["error_message"]


def test_event_stream_replays_error_event_on_re_subscription_to_failed_stream() -> None:
    """Re-subscribing to a failed stream must replay the error event."""
    gateway = FailingLifecycleGateway()
    client = TestClient(
        create_app(service=RelayService(gateway, 30.0), settings=_DUMMY_SETTINGS)
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Will fail",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    # First subscription drives the stream and captures the failure
    with client.stream("GET", f"/api/v1/tool-invocations/{invocation_id}/events") as r1:
        first_body = "".join(r1.iter_text())

    assert "event: error" in first_body
    assert gateway.stream_calls == 1

    # Second subscription replays from cached state; gateway must NOT be called again
    with client.stream("GET", f"/api/v1/tool-invocations/{invocation_id}/events") as r2:
        second_body = "".join(r2.iter_text())

    assert "event: error" in second_body
    assert gateway.stream_calls == 1  # not called a second time
