from __future__ import annotations

import pytest

from litellm_relay.contracts import ChatRequest
from litellm_relay.chat_orchestrator import ChatOrchestrator


@pytest.mark.asyncio
async def test_chat_no_tool_call_returns_direct_answer(monkeypatch):
    """When the model does not call deep_research, return the assistant text directly."""
    calls = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return {"id": "resp_1", "output_text": "Hello there!", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    result = await orchestrator.chat(ChatRequest(message="Hello", auto_tool_call=True))

    assert result.content == "Hello there!"
    assert result.tool_called is False
    assert result.tool_name is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_chat_with_tool_call_executes_deep_research(monkeypatch):
    """When the model calls deep_research, orchestrator runs it and completes a second turn."""
    import json as _json

    turn = 0
    calls = []

    def fake_responses(**kwargs):
        nonlocal turn
        calls.append(kwargs)
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_abc",
                        "arguments": _json.dumps(
                            {
                                "research_question": "짜장면의 역사",
                                "deliverable_format": "markdown_brief",
                            }
                        ),
                    }
                ],
            }
        else:
            return {
                "id": "resp_2",
                "output_text": "짜장면은 19세기 말 중국 산둥 지방에서 유래했습니다.",
                "output": [],
            }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )

    from litellm_relay.upstream import UpstreamInvocationResult

    async def fake_invoke(args):
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="역사 요약: 인천 차이나타운 기원",
        )

    orchestrator._invoke_deep_research = fake_invoke

    result = await orchestrator.chat(
        ChatRequest(message="짜장면의 역사를 자세히 알려줘")
    )

    assert result.tool_called is True
    assert result.tool_name == "deep_research"
    assert "짜장면" in result.content
    assert result.research_summary == "역사 요약: 인천 차이나타운 기원"
    assert turn == 2
    assert calls[1]["previous_response_id"] == "resp_1"
    assert calls[1]["input"][0]["type"] == "function_call_output"


@pytest.mark.asyncio
async def test_chat_auto_tool_call_false_skips_tools(monkeypatch):
    """When auto_tool_call=False, the orchestrator does not attach tools."""
    calls = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return {"id": "resp_1", "output_text": "No tools used.", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    result = await orchestrator.chat(ChatRequest(message="안녕", auto_tool_call=False))

    assert result.content == "No tools used."
    assert result.tool_called is False
    assert "tools" not in calls[0]


@pytest.mark.asyncio
async def test_chat_with_context_includes_context_in_first_turn(monkeypatch):
    """Context items are prepended to the user message."""
    calls = []

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return {"id": "resp_1", "output_text": "got it", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    await orchestrator.chat(ChatRequest(message="Q", context=["ctx A", "ctx B"]))

    user_content = calls[0]["input"]
    assert "ctx A" in user_content
    assert "ctx B" in user_content
    assert "Q" in user_content


@pytest.mark.asyncio
async def test_chat_extract_output_text_handles_model_dump(monkeypatch):
    """_extract_output_text handles response objects with model_dump method."""
    calls = []

    class FakeResponse:
        def model_dump(self):
            return {
                "id": "resp_1",
                "output_text": "via model_dump",
                "output": [],
            }

    def fake_responses(**kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == "via model_dump"
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_chat_extract_output_text_handles_empty_output(monkeypatch):
    """Empty output results in empty direct content."""

    def fake_responses(**kwargs):
        return {"id": "resp_1", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == ""
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_chat_tool_call_with_invalid_json_args(monkeypatch):
    """When tool call arguments are invalid JSON, falls back to request.message."""
    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_xyz",
                        "arguments": "NOT VALID JSON",
                    }
                ],
            }
        return {"id": "resp_2", "output_text": "final", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.upstream import UpstreamInvocationResult

    async def fake_invoke(args):
        # Should use request.message as research_question fallback
        assert args.research_question == "fallback question"
        return UpstreamInvocationResult(
            mode="foreground", status="completed", output_text="summary"
        )

    orchestrator._invoke_deep_research = fake_invoke

    result = await orchestrator.chat(ChatRequest(message="fallback question"))
    assert result.tool_called is True
    assert result.content == "final"


@pytest.mark.asyncio
async def test_extract_output_text_unknown_response_type(monkeypatch):
    """Unknown response shape falls back to empty content."""

    def fake_responses(**kwargs):
        return "unexpected string response"

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == ""
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_extract_output_text_item_without_model_dump(monkeypatch):
    """Non-dict output items without model_dump are ignored."""

    class FakeOutputNoModelDump:
        pass

    class FakeResponseWithOutput:
        output = [FakeOutputNoModelDump()]

    def fake_responses(**kwargs):
        return FakeResponseWithOutput()

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == ""
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_invoke_deep_research_delegates_to_gateway(monkeypatch):
    """_invoke_deep_research real method forwards to gateway.invoke_deep_research."""
    from litellm_relay.contracts import DeepResearchArguments
    from litellm_relay.upstream import UpstreamInvocationResult

    invoked_args: list[DeepResearchArguments] = []

    async def fake_gateway_invoke(
        args: DeepResearchArguments,
    ) -> UpstreamInvocationResult:
        invoked_args.append(args)
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="gateway result",
        )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    # Patch the gateway method directly to avoid real HTTP calls
    orchestrator._gateway.invoke_deep_research = fake_gateway_invoke  # type: ignore[method-assign]

    args = DeepResearchArguments(
        research_question="test question",
        deliverable_format="markdown_brief",
    )
    result = await orchestrator._invoke_deep_research(args)
    assert result.output_text == "gateway result"
    assert len(invoked_args) == 1
    assert invoked_args[0].research_question == "test question"


@pytest.mark.asyncio
async def test_research_timeout_is_separate_from_chat_timeout(monkeypatch):
    """ChatOrchestrator uses research_timeout_seconds for gateway, not chat timeout."""
    from litellm_relay.chat_orchestrator import ChatOrchestrator as CO

    orchestrator = CO(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        timeout_seconds=10.0,
        research_timeout_seconds=300.0,
    )
    # Gateway should have research timeout, not chat timeout
    assert orchestrator._gateway._timeout_seconds == 300.0
    assert orchestrator._timeout_seconds == 10.0


@pytest.mark.asyncio
async def test_chat_deep_research_error_returns_structured_response(monkeypatch):
    """When deep_research raises, returns a safe structured error instead of 500."""
    import json as _json

    def fake_responses(**kwargs):
        return {
            "id": "resp_err",
            "output": [
                {
                    "type": "function_call",
                    "name": "deep_research",
                    "call_id": "call_err",
                    "arguments": _json.dumps(
                        {
                            "research_question": "will fail",
                            "deliverable_format": "markdown_brief",
                        }
                    ),
                }
            ],
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    async def failing_invoke(args):
        raise RuntimeError("upstream timeout")

    orchestrator._invoke_deep_research = failing_invoke

    result = await orchestrator.chat(ChatRequest(message="will fail"))
    assert result.tool_called is True
    assert result.tool_name == "deep_research"
    assert result.content == "deep_research failed. Please retry later."
    assert result.research_summary == "deep_research failed. Please retry later."
    assert "upstream timeout" not in result.content
    assert "upstream timeout" not in result.research_summary


@pytest.mark.asyncio
async def test_chat_first_responses_exception_returns_safe_response(monkeypatch):
    def fake_responses(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    result = await orchestrator.chat(ChatRequest(message="will fail"))
    assert result.content == "deep_research failed. Please retry later."
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_chat_second_responses_exception_falls_back_to_research_summary(
    monkeypatch,
):
    import json as _json

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_1",
                        "arguments": _json.dumps(
                            {
                                "research_question": "q",
                                "deliverable_format": "markdown_brief",
                            }
                        ),
                    }
                ],
            }
        raise RuntimeError("second turn failed")

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.upstream import UpstreamInvocationResult

    async def fake_invoke(args):
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="research summary",
        )

    orchestrator._invoke_deep_research = fake_invoke

    result = await orchestrator.chat(ChatRequest(message="q"))
    assert result.tool_called is True
    assert result.content == "research summary"
    assert result.research_summary == "research summary"


@pytest.mark.asyncio
async def test_extract_function_call_handles_pydantic_objects(monkeypatch):
    """_extract_function_call normalises Pydantic-like response output items."""
    import json as _json

    class FakeOutputItem:
        def model_dump(self):
            return {
                "type": "function_call",
                "name": "deep_research",
                "call_id": "call_pydantic",
                "arguments": _json.dumps(
                    {
                        "research_question": "pydantic q",
                        "deliverable_format": "markdown_brief",
                    }
                ),
            }

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:

            class FakeResponse:
                output = [FakeOutputItem()]
                id = "resp_1"

            return FakeResponse()
        return {"id": "resp_2", "output_text": "done", "output": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.upstream import UpstreamInvocationResult

    async def fake_invoke(args):
        assert args.research_question == "pydantic q"
        return UpstreamInvocationResult(
            mode="foreground", status="completed", output_text="pydantic summary"
        )

    orchestrator._invoke_deep_research = fake_invoke

    result = await orchestrator.chat(ChatRequest(message="pydantic test"))
    assert result.tool_called is True
    assert result.research_summary == "pydantic summary"


def test_extract_function_call_skips_non_matching_items():
    result = ChatOrchestrator._extract_function_call(
        {
            "output": [
                {"type": "message", "name": "deep_research"},
                {"type": "function_call", "name": "other_tool", "call_id": "x"},
            ]
        }
    )

    assert result is None


def test_extract_output_text_reads_nested_blocks_and_invalid_model_dump():
    class FakeBadResponse:
        def model_dump(self):
            return "invalid"

    assert ChatOrchestrator._extract_output_text(FakeBadResponse()) == ""

    payload = {
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "hello"},
                    {"type": "text", "text": {"value": " world"}},
                ]
            }
        ]
    }
    assert ChatOrchestrator._extract_output_text(payload) == "hello world"

    noisy_payload = {
        "output": [
            {"content": "not-a-list"},
            {"content": ["not-a-dict", {"type": "reasoning", "text": "skip"}]},
        ]
    }
    assert ChatOrchestrator._extract_output_text(noisy_payload) == ""


def test_extract_response_id_missing_raises_value_error():
    with pytest.raises(ValueError):
        ChatOrchestrator._extract_response_id({})


def test_extract_response_id_from_model_dump_object():
    class FakeResponse:
        def model_dump(self):
            return {"id": "resp_model_dump"}

    assert ChatOrchestrator._extract_response_id(FakeResponse()) == "resp_model_dump"


# ---------------------------------------------------------------------------
# system_prompt and deliverable_format passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_system_prompt_forwarded_to_deep_research(monkeypatch):
    """ChatRequest.system_prompt is passed to DeepResearchArguments when tool is called."""
    import json as _json

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_sp",
                        "arguments": _json.dumps(
                            {
                                "research_question": "짜장면 역사",
                                "deliverable_format": "markdown_brief",
                            }
                        ),
                    }
                ],
            }
        return {
            "id": "resp_2",
            "output_text": "English answer about jjajangmyeon.",
            "output": [],
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.contracts import DeepResearchArguments
    from litellm_relay.upstream import UpstreamInvocationResult

    captured_args: list[DeepResearchArguments] = []

    async def capturing_invoke(args: DeepResearchArguments) -> UpstreamInvocationResult:
        captured_args.append(args)
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="summary",
        )

    orchestrator._invoke_deep_research = capturing_invoke

    await orchestrator.chat(
        ChatRequest(
            message="짜장면 역사",
            system_prompt="Always answer in English only.",
        )
    )

    assert len(captured_args) == 1
    assert captured_args[0].system_prompt == "Always answer in English only."


@pytest.mark.asyncio
async def test_chat_system_prompt_none_when_not_provided(monkeypatch):
    """When system_prompt is omitted from ChatRequest, DeepResearchArguments gets None."""
    import json as _json

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_no_sp",
                        "arguments": _json.dumps(
                            {
                                "research_question": "test",
                                "deliverable_format": "markdown_brief",
                            }
                        ),
                    }
                ],
            }
        return {
            "id": "resp_2",
            "output_text": "answer",
            "output": [],
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.contracts import DeepResearchArguments
    from litellm_relay.upstream import UpstreamInvocationResult

    captured_args: list[DeepResearchArguments] = []

    async def capturing_invoke(args: DeepResearchArguments) -> UpstreamInvocationResult:
        captured_args.append(args)
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="summary",
        )

    orchestrator._invoke_deep_research = capturing_invoke

    await orchestrator.chat(ChatRequest(message="test"))

    assert len(captured_args) == 1
    assert captured_args[0].system_prompt is None


@pytest.mark.asyncio
async def test_chat_deliverable_format_used_as_fallback(monkeypatch):
    """ChatRequest.deliverable_format is used when model does not specify format."""
    import json as _json

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_fmt",
                        "arguments": _json.dumps({"research_question": "짜장면"}),
                    }
                ],
            }
        return {
            "id": "resp_2",
            "output_text": "done",
            "output": [],
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.contracts import DeepResearchArguments
    from litellm_relay.upstream import UpstreamInvocationResult

    captured_args: list[DeepResearchArguments] = []

    async def capturing_invoke(args: DeepResearchArguments) -> UpstreamInvocationResult:
        captured_args.append(args)
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="summary",
        )

    orchestrator._invoke_deep_research = capturing_invoke

    await orchestrator.chat(
        ChatRequest(message="짜장면", deliverable_format="markdown_report")
    )

    assert len(captured_args) == 1
    assert captured_args[0].deliverable_format == "markdown_report"


@pytest.mark.asyncio
async def test_chat_model_format_overrides_request_format(monkeypatch):
    """When model specifies deliverable_format in tool args, it takes precedence."""
    import json as _json

    turn = 0

    def fake_responses(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "id": "resp_1",
                "output": [
                    {
                        "type": "function_call",
                        "name": "deep_research",
                        "call_id": "call_override",
                        "arguments": _json.dumps(
                            {
                                "research_question": "짜장면",
                                "deliverable_format": "json_outline",
                            }
                        ),
                    }
                ],
            }
        return {
            "id": "resp_2",
            "output_text": "done",
            "output": [],
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.responses", fake_responses
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )

    from litellm_relay.contracts import DeepResearchArguments
    from litellm_relay.upstream import UpstreamInvocationResult

    captured_args: list[DeepResearchArguments] = []

    async def capturing_invoke(args: DeepResearchArguments) -> UpstreamInvocationResult:
        captured_args.append(args)
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="summary",
        )

    orchestrator._invoke_deep_research = capturing_invoke

    await orchestrator.chat(
        ChatRequest(message="짜장면", deliverable_format="markdown_report")
    )

    assert len(captured_args) == 1
    assert captured_args[0].deliverable_format == "json_outline"


@pytest.mark.asyncio
async def test_chat_request_defaults(monkeypatch):
    """ChatRequest defaults: system_prompt=None, deliverable_format='markdown_brief'."""
    req = ChatRequest(message="hello")
    assert req.system_prompt is None
    assert req.deliverable_format == "markdown_brief"
    assert req.auto_tool_call is True
    assert req.context == []
