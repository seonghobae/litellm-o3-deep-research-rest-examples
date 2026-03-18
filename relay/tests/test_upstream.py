from __future__ import annotations

import pytest

from litellm_relay.contracts import DeepResearchArguments
from litellm_relay.upstream import LiteLLMRelayGateway


@pytest.mark.asyncio
async def test_builds_foreground_responses_request_from_tool_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "id": "resp_foreground_1",
            "status": "completed",
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": {"value": "relay answer"}}
                    ]
                }
            ],
        }

    monkeypatch.setattr("litellm_relay.upstream.litellm.responses", fake_responses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    result = await gateway.invoke_deep_research(
        DeepResearchArguments(
            research_question="Summarize relay architecture.",
            context=["Azure Landing Zone"],
            constraints=["Use markdown"],
            deliverable_format="markdown_brief",
        )
    )

    assert captured["api_base"] == "https://proxy.example/v1"
    assert captured["api_key"] == "sk-relay"
    assert captured["model"] == "litellm_proxy/o3-deep-research"
    assert "Research question:" in str(captured["input"])
    assert result.mode == "foreground"
    assert result.output_text == "relay answer"


@pytest.mark.asyncio
async def test_builds_background_responses_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "id": "resp_background_1",
            "status": "queued",
            "background": True,
        }

    monkeypatch.setattr("litellm_relay.upstream.litellm.responses", fake_responses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    result = await gateway.invoke_deep_research(
        DeepResearchArguments(
            research_question="Queue the relay run.",
            deliverable_format="markdown_brief",
            background=True,
        )
    )

    assert captured["background"] is True
    assert result.mode == "background"
    assert result.upstream_response_id == "resp_background_1"
    assert result.response["status"] == "queued"


@pytest.mark.asyncio
async def test_get_response_by_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_aget_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "id": kwargs["response_id"],
            "status": "completed",
            "output_text": "done",
        }

    monkeypatch.setattr(
        "litellm_relay.upstream.litellm.aget_responses", fake_aget_responses
    )

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    payload = await gateway.get_response("resp_123")

    assert captured["response_id"] == "resp_123"
    assert payload["status"] == "completed"
    assert payload["output_text"] == "done"


@pytest.mark.asyncio
async def test_builds_streaming_responses_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeStream:
        def __init__(self, events: list[dict[str, object]]) -> None:
            self._events = iter(events)

        def __aiter__(self) -> "FakeStream":
            return self

        async def __anext__(self) -> dict[str, object]:
            try:
                return next(self._events)
            except StopIteration as exc:  # pragma: no cover - iterator protocol
                raise StopAsyncIteration from exc

    async def fake_aresponses(**kwargs: object) -> FakeStream:
        captured.update(kwargs)
        return FakeStream(
            [
                {"type": "response.output_text.delta", "delta": "Hello"},
                {"type": "response.output_text.delta", "delta": " world"},
            ]
        )

    monkeypatch.setattr("litellm_relay.upstream.litellm.aresponses", fake_aresponses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    chunks = [
        chunk
        async for chunk in gateway.stream_deep_research(
            DeepResearchArguments(
                research_question="Stream the relay answer.",
                deliverable_format="markdown_brief",
                stream=True,
            )
        )
    ]

    assert captured["stream"] is True
    assert chunks == ["Hello", " world"]
