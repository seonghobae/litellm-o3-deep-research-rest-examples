from __future__ import annotations

import pytest

from litellm_relay.contracts import DeepResearchArguments
from litellm_relay.upstream import LiteLLMRelayGateway, UpstreamInvocationResult


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

        def __aiter__(self) -> FakeStream:
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


@pytest.mark.asyncio
async def test_invoke_deep_research_passes_text_format_json_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """text_format=json_object is forwarded as text={"format":...} (line 58)."""
    captured: dict[str, object] = {}

    def fake_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"id": "resp_fmt_1", "status": "completed", "output_text": '{"a":1}'}

    monkeypatch.setattr("litellm_relay.upstream.litellm.responses", fake_responses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="gpt-4o",
        timeout_seconds=12.0,
    )

    from litellm_relay.contracts import TextFormatJsonObject

    result = await gateway.invoke_deep_research(
        DeepResearchArguments(
            research_question="Return JSON.",
            deliverable_format="markdown_brief",
            text_format=TextFormatJsonObject(),
        )
    )

    assert captured.get("text") == {"format": {"type": "json_object"}}
    assert result.output_text == '{"a":1}'


@pytest.mark.asyncio
async def test_invoke_deep_research_passes_text_format_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """text_format=json_schema serialises the schema with correct alias."""
    captured: dict[str, object] = {}

    def fake_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"id": "resp_schema_1", "status": "completed", "output_text": '{"x":1}'}

    monkeypatch.setattr("litellm_relay.upstream.litellm.responses", fake_responses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="gpt-4o",
        timeout_seconds=12.0,
    )

    from litellm_relay.contracts import TextFormatJsonSchema

    result = await gateway.invoke_deep_research(
        DeepResearchArguments(
            research_question="Return schema-valid JSON.",
            deliverable_format="markdown_brief",
            text_format=TextFormatJsonSchema(
                name="my_schema",
                schema={
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                    "required": ["x"],
                    "additionalProperties": False,
                },
            ),
        )
    )

    text_arg = captured.get("text")
    assert isinstance(text_arg, dict)
    fmt = text_arg["format"]
    assert fmt["type"] == "json_schema"
    assert fmt["name"] == "my_schema"
    assert "schema" in fmt  # aliased from schema_
    assert result.output_text == '{"x":1}'


@pytest.mark.asyncio
async def test_stream_deep_research_passes_text_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """text_format is forwarded in stream mode too (line 130)."""
    captured: dict[str, object] = {}

    class FakeStream:
        def __init__(self, events: list[dict[str, object]]) -> None:
            self._events = events

        def __aiter__(self) -> FakeStream:
            self._iter = iter(self._events)
            return self

        async def __anext__(self) -> dict[str, object]:
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    async def fake_aresponses(**kwargs: object) -> FakeStream:
        captured.update(kwargs)
        return FakeStream([{"type": "response.output_text.delta", "delta": '{"q":1}'}])

    monkeypatch.setattr("litellm_relay.upstream.litellm.aresponses", fake_aresponses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="gpt-4o",
        timeout_seconds=12.0,
    )

    from litellm_relay.contracts import TextFormatJsonObject

    chunks = [
        chunk
        async for chunk in gateway.stream_deep_research(
            DeepResearchArguments(
                research_question="JSON stream.",
                deliverable_format="markdown_brief",
                stream=True,
                text_format=TextFormatJsonObject(),
            )
        )
    ]

    assert captured.get("text") == {"format": {"type": "json_object"}}
    assert chunks == ['{"q":1}']


@pytest.mark.asyncio
async def test_invoke_deep_research_passes_system_prompt_as_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """system_prompt is forwarded as the ``instructions`` kwarg (line 56)."""
    captured: dict[str, object] = {}

    def fake_responses(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"id": "resp_sys_1", "status": "completed", "output_text": "sys-ok"}

    monkeypatch.setattr("litellm_relay.upstream.litellm.responses", fake_responses)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    result = await gateway.invoke_deep_research(
        DeepResearchArguments(
            research_question="Test system prompt forwarding.",
            deliverable_format="markdown_brief",
            system_prompt="You are a concise assistant. Answer in one sentence.",
        )
    )

    assert (
        captured.get("instructions")
        == "You are a concise assistant. Answer in one sentence."
    )
    assert result.output_text == "sys-ok"


@pytest.mark.asyncio
async def test_stream_deep_research_passes_system_prompt_as_instructions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """system_prompt is forwarded as the ``instructions`` kwarg in stream mode (line 124)."""
    captured: dict[str, object] = {}

    class FakeStream:
        def __init__(self, events: list[dict[str, object]]) -> None:
            self._events = events

        def __aiter__(self) -> FakeStream:
            self._iter = iter(self._events)
            return self

        async def __anext__(self) -> dict[str, object]:
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    async def fake_aresponses(**kwargs: object) -> FakeStream:
        captured.update(kwargs)
        return FakeStream(
            [{"type": "response.output_text.delta", "delta": "stream-ok"}]
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
                research_question="Test system prompt in stream mode.",
                deliverable_format="markdown_brief",
                stream=True,
                system_prompt="Answer in one English sentence only.",
            )
        )
    ]

    assert captured.get("instructions") == "Answer in one English sentence only."
    assert chunks == ["stream-ok"]


def test_to_dict_returns_dict_unchanged() -> None:
    payload = {"id": "resp_1", "status": "completed"}
    result = LiteLLMRelayGateway._to_dict(payload)
    assert result is payload


def test_to_dict_calls_model_dump_when_available() -> None:
    class FakePydanticModel:
        def model_dump(self) -> dict[str, object]:
            return {"from": "model_dump"}

    result = LiteLLMRelayGateway._to_dict(FakePydanticModel())
    assert result == {"from": "model_dump"}


def test_to_dict_falls_back_to_dict_method() -> None:
    class LegacyModel:
        def dict(self) -> dict[str, object]:
            return {"from": "dict"}

    result = LiteLLMRelayGateway._to_dict(LegacyModel())
    assert result == {"from": "dict"}


def test_to_dict_raises_type_error_for_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Unsupported payload type"):
        LiteLLMRelayGateway._to_dict(object())


def test_already_prefixed_model_is_not_double_prefixed() -> None:
    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="litellm_proxy/already-prefixed",
        timeout_seconds=12.0,
    )
    # Access the internal model name to confirm no double prefix.
    assert gateway._model == "litellm_proxy/already-prefixed"


@pytest.mark.asyncio
async def test_wait_for_response_returns_payload_when_status_is_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    call_count = 0

    async def fake_aget_responses(**kwargs: object) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        return {"id": "resp_1", "status": "completed", "output_text": "done"}

    monkeypatch.setattr(
        "litellm_relay.upstream.litellm.aget_responses", fake_aget_responses
    )

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    result = await gateway.wait_for_response("resp_1", timeout_seconds=5.0)

    assert result["status"] == "completed"
    assert call_count == 1


@pytest.mark.asyncio
async def test_wait_for_response_raises_timeout_error_when_response_stays_queued(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def always_queued(**kwargs: object) -> dict[str, object]:
        return {"id": "resp_slow", "status": "queued"}

    monkeypatch.setattr("litellm_relay.upstream.litellm.aget_responses", always_queued)

    gateway = LiteLLMRelayGateway(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        timeout_seconds=12.0,
    )

    with pytest.raises(TimeoutError, match="resp_slow"):
        await gateway.wait_for_response(
            "resp_slow",
            timeout_seconds=0.01,
            poll_interval_seconds=0.001,
        )


# --------------------------------------------------------------------------- #
# Static helper unit tests                                                     #
# --------------------------------------------------------------------------- #


def test_extract_response_text_returns_top_level_output_text_string() -> None:
    result = LiteLLMRelayGateway._extract_response_text(
        {"output_text": "top-level text"}
    )
    assert result == "top-level text"


def test_extract_response_text_returns_plain_string_text_field() -> None:
    """Cover the isinstance(text, str) branch inside output[].content[]."""
    result = LiteLLMRelayGateway._extract_response_text(
        {
            "output": [
                {"content": [{"type": "output_text", "text": "plain string text"}]}
            ]
        }
    )
    assert result == "plain string text"


def test_extract_response_text_skips_non_output_type_blocks() -> None:
    result = LiteLLMRelayGateway._extract_response_text(
        {
            "output": [
                {
                    "content": [
                        {"type": "reasoning", "text": "should be ignored"},
                        {"type": "output_text", "text": "included"},
                    ]
                }
            ]
        }
    )
    assert result == "included"


def test_extract_response_text_returns_empty_string_when_output_empty() -> None:
    assert LiteLLMRelayGateway._extract_response_text({}) == ""
    assert LiteLLMRelayGateway._extract_response_text({"output": []}) == ""


def test_extract_stream_text_returns_none_when_delta_absent() -> None:
    assert (
        LiteLLMRelayGateway._extract_stream_text({"type": "response.output_text.delta"})
        is None
    )


def test_extract_stream_text_returns_none_when_delta_is_empty_string() -> None:
    assert (
        LiteLLMRelayGateway._extract_stream_text(
            {"type": "response.output_text.delta", "delta": ""}
        )
        is None
    )


def test_extract_stream_text_returns_none_for_non_delta_event_type() -> None:
    assert (
        LiteLLMRelayGateway._extract_stream_text(
            {"type": "response.done", "delta": "ignored"}
        )
        is None
    )


def test_maybe_str_returns_none_for_none_input() -> None:
    assert LiteLLMRelayGateway._maybe_str(None) is None


def test_maybe_str_returns_none_for_empty_string() -> None:
    assert LiteLLMRelayGateway._maybe_str("") is None


def test_maybe_str_returns_none_for_non_string() -> None:
    assert LiteLLMRelayGateway._maybe_str(42) is None  # type: ignore[arg-type]


def test_maybe_str_returns_value_for_non_empty_string() -> None:
    assert LiteLLMRelayGateway._maybe_str("resp_1") == "resp_1"


def test_render_input_includes_context_and_constraints() -> None:
    args = DeepResearchArguments(
        research_question="What is relay?",
        context=["Azure Landing Zone", "LiteLLM Proxy"],
        constraints=["Use markdown", "Cite sources"],
        deliverable_format="markdown_brief",
    )
    rendered = LiteLLMRelayGateway._render_input(args)

    assert "Research question: What is relay?" in rendered
    assert "Context:" in rendered
    assert "- Azure Landing Zone" in rendered
    assert "- LiteLLM Proxy" in rendered
    assert "Constraints:" in rendered
    assert "- Use markdown" in rendered
    assert "- Cite sources" in rendered


def test_extract_response_text_skips_non_dict_output_items() -> None:
    """Cover the `continue` branch when an output[] item is not a dict (line 170)."""
    result = LiteLLMRelayGateway._extract_response_text(
        {
            "output": [
                "not a dict",  # must be skipped
                {"content": [{"type": "output_text", "text": "valid"}]},
            ]
        }
    )
    assert result == "valid"


def test_extract_response_text_skips_non_dict_content_blocks() -> None:
    """Cover the `continue` branch when a content[] block is not a dict (line 173)."""
    result = LiteLLMRelayGateway._extract_response_text(
        {
            "output": [
                {
                    "content": [
                        "not a dict",  # must be skipped
                        {"type": "output_text", "text": "valid block"},
                    ]
                }
            ]
        }
    )
    assert result == "valid block"


def test_render_input_omits_context_and_constraints_sections_when_empty() -> None:
    args = DeepResearchArguments(
        research_question="Minimal question",
        deliverable_format="markdown_brief",
    )
    rendered = LiteLLMRelayGateway._render_input(args)

    assert "Context:" not in rendered
    assert "Constraints:" not in rendered


def test_render_input_shows_no_when_require_citations_is_false() -> None:
    """Cover the ``False`` branch of ``require_citations`` in _render_input."""
    args = DeepResearchArguments(
        research_question="No citations needed",
        deliverable_format="markdown_brief",
        require_citations=False,
    )
    rendered = LiteLLMRelayGateway._render_input(args)

    assert "Require citations: no" in rendered


def test_render_input_includes_correct_deliverable_format_markdown_report() -> None:
    """Cover ``markdown_report`` deliverable format in _render_input."""
    args = DeepResearchArguments(
        research_question="Report format question",
        deliverable_format="markdown_report",
    )
    rendered = LiteLLMRelayGateway._render_input(args)

    assert "Deliverable format: markdown_report" in rendered


def test_render_input_includes_correct_deliverable_format_json_outline() -> None:
    """Cover ``json_outline`` deliverable format in _render_input."""
    args = DeepResearchArguments(
        research_question="JSON outline question",
        deliverable_format="json_outline",
    )
    rendered = LiteLLMRelayGateway._render_input(args)

    assert "Deliverable format: json_outline" in rendered
