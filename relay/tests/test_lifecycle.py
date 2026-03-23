from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
import pytest

from litellm_relay.app import create_app
from litellm_relay.config import RelaySettings
from litellm_relay.contracts import DeepResearchArguments, ToolInvocationRequest
from litellm_relay.service import InvocationCapacityError, RelayService
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
    assert replay_body.count("event: output_text") == 2
    assert "Hello" in replay_body
    assert "world" in replay_body
    assert "event: completed" in replay_body
    assert gateway.stream_calls == 1


def test_events_endpoint_does_not_restart_stream_for_concurrent_subscribers() -> None:
    class BlockingStreamGateway(LifecycleGateway):
        def __init__(self) -> None:
            super().__init__()
            self.release = asyncio.Event()

        async def stream_deep_research(self, args: DeepResearchArguments):
            self.stream_calls += 1
            await self.release.wait()
            yield "Hello"

    async def consume_events(service: RelayService, invocation_id: str) -> str:
        frames: list[str] = []
        async for frame in service.event_stream(invocation_id):
            frames.append(frame)
        return "".join(frames)

    gateway = BlockingStreamGateway()
    service = RelayService(gateway, 30.0)
    payload = ToolInvocationRequest.model_validate(
        {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Concurrent SSE subscribers.",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        }
    )

    async def run_scenario() -> tuple[str, str]:
        _, view = await service.create_invocation(payload)
        first = asyncio.create_task(consume_events(service, view.invocation_id))
        second = asyncio.create_task(consume_events(service, view.invocation_id))
        await asyncio.sleep(0)
        gateway.release.set()
        return await asyncio.gather(first, second)

    first_body, second_body = asyncio.run(run_scenario())

    assert gateway.stream_calls == 1
    assert "event: completed" in first_body
    assert "Hello" in first_body
    assert "event: completed" not in second_body


@pytest.mark.asyncio
async def test_create_invocation_reserves_capacity_before_awaiting_upstream() -> None:
    class BlockingGateway:
        def __init__(self) -> None:
            self.calls = 0
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            self.calls += 1
            self.started.set()
            await self.release.wait()
            return UpstreamInvocationResult(
                mode="foreground",
                status="completed",
                output_text="bounded",
                response={"output_text": "bounded"},
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

    gateway = BlockingGateway()
    service = RelayService(gateway, 30.0, max_invocations=1)
    payload = ToolInvocationRequest.model_validate(
        {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Bound relay memory.",
                "deliverable_format": "markdown_brief",
            },
        }
    )

    first_task = asyncio.create_task(service.create_invocation(payload))
    await gateway.started.wait()

    with pytest.raises(InvocationCapacityError):
        await service.create_invocation(payload)

    gateway.release.set()
    status_code, view = await first_task

    assert status_code == 200
    assert view.status == "completed"
    assert gateway.calls == 1
    assert len(service._store) == 1


@pytest.mark.asyncio
async def test_create_invocation_removes_placeholder_when_gateway_invoke_fails() -> (
    None
):
    class FailingGateway:
        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            raise RuntimeError("upstream exploded")

        async def get_response(self, response_id: str) -> dict[str, object]:
            return {}

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            return {}

        async def stream_deep_research(self, args: DeepResearchArguments):
            return
            yield  # pragma: no cover

    service = RelayService(FailingGateway(), 30.0)
    payload = ToolInvocationRequest.model_validate(
        {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Fail relay admission.",
                "deliverable_format": "markdown_brief",
            },
        }
    )

    with pytest.raises(RuntimeError, match="upstream exploded"):
        await service.create_invocation(payload)

    assert service._store == {}


@pytest.mark.parametrize(
    ("mode", "expected_status"),
    [("background", "queued"), ("foreground", "completed")],
)
def test_from_result_maps_mode_to_stored_status(
    mode: str, expected_status: str
) -> None:
    payload = ToolInvocationRequest.model_validate(
        {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Check stored status.",
                "deliverable_format": "markdown_brief",
            },
        }
    )
    result = UpstreamInvocationResult(
        mode=mode,
        status="ignored-by-helper",
        upstream_response_id="resp_123",
        output_text="done",
        response={"id": "resp_123"},
    )

    stored = RelayService._from_result(payload, result)

    assert stored.mode == mode
    assert stored.status == expected_status
    assert stored.upstream_response_id == "resp_123"
    assert stored.output_text == "done"
    assert stored.response == {"id": "resp_123"}


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
    """After a failed stream, the GET endpoint must expose only a safe error_message."""
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
    assert (
        payload["error_message"] == "deep_research stream failed. Please retry later."
    )
    assert "stream exploded" not in payload["error_message"]


def test_event_stream_emits_completed_event_for_background_invocation_with_output_text() -> (
    None
):
    """event_stream() for a non-stream (background) mode with output_text must emit a
    'completed' SSE event containing the output text.  This covers service.py line 119.
    """

    class CompletedBackgroundGateway:
        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="background",
                status="queued",
                upstream_response_id="resp_bg_complete",
                response={"id": "resp_bg_complete", "status": "queued"},
            )

        async def get_response(self, response_id: str) -> dict[str, object]:
            return {
                "id": response_id,
                "status": "completed",
                "output_text": "bg answer",
            }

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            return {
                "id": response_id,
                "status": "completed",
                "output_text": "bg answer",
            }

        async def stream_deep_research(self, args: DeepResearchArguments):
            return
            yield  # pragma: no cover

    client = TestClient(
        create_app(
            service=RelayService(CompletedBackgroundGateway(), 30.0),
            settings=_DUMMY_SETTINGS,
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Background with answer",
                "deliverable_format": "markdown_brief",
                "background": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    # Polling GET triggers _apply_upstream_payload with status="completed"
    client.get(f"/api/v1/tool-invocations/{invocation_id}")

    # Now event_stream on a non-stream mode with output_text → completed event
    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as resp:
        body = "".join(resp.iter_text())

    assert resp.status_code == 200
    assert "event: completed" in body
    assert "bg answer" in body


def test_apply_upstream_payload_sets_status_to_running_for_running_status() -> None:
    """_apply_upstream_payload with status='running' must update status to 'running'.
    This covers service.py line 232."""

    class RunningGateway:
        _calls = 0

        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="background",
                status="queued",
                upstream_response_id="resp_running_1",
                response={"id": "resp_running_1", "status": "queued"},
            )

        async def get_response(self, response_id: str) -> dict[str, object]:
            return {"id": response_id, "status": "running"}

        async def wait_for_response(
            self, response_id: str, timeout_seconds: float
        ) -> dict[str, object]:
            return {}

        async def stream_deep_research(self, args: DeepResearchArguments):
            return
            yield  # pragma: no cover

    client = TestClient(
        create_app(
            service=RelayService(RunningGateway(), 30.0), settings=_DUMMY_SETTINGS
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Running question",
                "deliverable_format": "markdown_brief",
                "background": True,
            },
        },
    )
    invocation_id = create_response.json()["invocation_id"]

    get_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "running"


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
    assert "deep_research stream failed. Please retry later." in first_body
    assert "stream exploded" not in first_body
    assert gateway.stream_calls == 1

    # Second subscription replays from cached state; gateway must NOT be called again
    with client.stream("GET", f"/api/v1/tool-invocations/{invocation_id}/events") as r2:
        second_body = "".join(r2.iter_text())

    assert "event: error" in second_body
    assert "deep_research stream failed. Please retry later." in second_body
    assert "stream exploded" not in second_body
    assert gateway.stream_calls == 1  # not called a second time


def test_create_invocation_prunes_completed_entries_when_store_reaches_capacity() -> (
    None
):
    """Completed entries should be evicted before new invocations are rejected."""

    class ForegroundGateway:
        async def invoke_deep_research(
            self, args: DeepResearchArguments
        ) -> UpstreamInvocationResult:
            return UpstreamInvocationResult(
                mode="foreground",
                status="completed",
                output_text="ok",
                response={"output_text": "ok"},
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
            service=RelayService(ForegroundGateway(), 30.0, max_invocations=1),
            settings=_DUMMY_SETTINGS,
        )
    )

    first = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "first",
                "deliverable_format": "markdown_brief",
            },
        },
    )
    second = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "second",
                "deliverable_format": "markdown_brief",
            },
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        first.json()["invocation_id"] != second.json()["invocation_id"]
    )  # completed entry was pruned


def test_create_invocation_returns_503_when_active_store_is_full() -> None:
    """Active entries should not grow the process-wide store past its limit."""

    class StreamOnlyGateway(LifecycleGateway):
        pass

    client = TestClient(
        create_app(
            service=RelayService(StreamOnlyGateway(), 30.0, max_invocations=1),
            settings=_DUMMY_SETTINGS,
        )
    )

    first = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "first stream",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )
    second = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "second stream",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        },
    )

    assert first.status_code == 202
    assert second.status_code == 503
    assert "capacity" in second.json()["detail"]


def test_events_endpoint_fails_when_stream_output_exceeds_memory_limit() -> None:
    """Streaming output should stop once the per-invocation memory cap is exceeded."""

    class LargeStreamGateway(LifecycleGateway):
        async def stream_deep_research(self, args: DeepResearchArguments):
            self.stream_calls += 1
            yield "12345"
            yield "67890"

    client = TestClient(
        create_app(
            service=RelayService(LargeStreamGateway(), 30.0, max_stream_bytes=8),
            settings=_DUMMY_SETTINGS,
        )
    )

    create_response = client.post(
        "/api/v1/tool-invocations",
        json={
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Too much output",
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
    assert "12345" in body
    assert "event: error" in body
    assert "memory limit" in body

    with client.stream(
        "GET", f"/api/v1/tool-invocations/{invocation_id}/events"
    ) as replay_response:
        replay_body = "".join(replay_response.iter_text())

    assert replay_response.status_code == 200
    assert replay_body.count("event: output_text") == 1
    assert "12345" in replay_body
    assert "67890" not in replay_body
    assert "event: error" in replay_body
    assert "memory limit" in replay_body

    status_response = client.get(f"/api/v1/tool-invocations/{invocation_id}")
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert payload["output_text"] is None


def test_completed_stream_view_reuses_chunk_cache_without_duplicate_output_copy() -> (
    None
):
    service = RelayService(LifecycleGateway(), 30.0)
    payload = ToolInvocationRequest.model_validate(
        {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": "Reuse stream cache.",
                "deliverable_format": "markdown_brief",
                "stream": True,
            },
        }
    )

    async def run_scenario() -> tuple[str, object, object]:
        _, view = await service.create_invocation(payload)
        frames: list[str] = []
        async for frame in service.event_stream(view.invocation_id):
            frames.append(frame)
        stored = service._store[view.invocation_id]
        current_view = await service.get_invocation(view.invocation_id)
        return "".join(frames), stored, current_view

    body, stored, current_view = asyncio.run(run_scenario())

    assert "event: completed" in body
    assert stored.stream_chunks == ["Hello", " world"]
    assert stored.output_text is None
    assert stored.response is None
    assert current_view.output_text == "Hello world"
    assert current_view.response == {"output_text": "Hello world"}
