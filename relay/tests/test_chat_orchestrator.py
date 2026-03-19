from __future__ import annotations

import pytest

from litellm_relay.contracts import ChatRequest
from litellm_relay.chat_orchestrator import ChatOrchestrator


@pytest.mark.asyncio
async def test_chat_no_tool_call_returns_direct_answer(monkeypatch):
    """When the model does not call deep_research, return the assistant text directly."""
    calls = []

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "Hello there!",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": _json.dumps(
                                            {
                                                "research_question": "짜장면의 역사",
                                                "deliverable_format": "markdown_brief",
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        else:
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "짜장면은 19세기 말 중국 산둥 지방에서 유래했습니다.",
                            "tool_calls": None,
                        },
                    }
                ]
            }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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


@pytest.mark.asyncio
async def test_chat_auto_tool_call_false_skips_tools(monkeypatch):
    """When auto_tool_call=False, the orchestrator does not attach tools."""
    calls = []

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "No tools used.",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "got it",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    await orchestrator.chat(ChatRequest(message="Q", context=["ctx A", "ctx B"]))

    messages = calls[0]["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "ctx A" in user_content
    assert "ctx B" in user_content
    assert "Q" in user_content


@pytest.mark.asyncio
async def test_chat_extract_choice_handles_model_dump(monkeypatch):
    """_extract_choice handles objects with model_dump method."""
    calls = []

    class FakeChoice:
        def model_dump(self):
            return {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "via model_dump",
                    "tool_calls": None,
                },
            }

    class FakeResponse:
        choices = [FakeChoice()]

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return FakeResponse()

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == "via model_dump"
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_chat_extract_choice_handles_empty_choices(monkeypatch):
    """_extract_choice returns {} when choices is empty, resulting in empty content."""

    def fake_completions(**kwargs):
        return {"choices": []}

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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
    import json as _json

    turn = 0

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_xyz",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": "NOT VALID JSON",
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "final",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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
async def test_extract_choice_unknown_response_type(monkeypatch):
    """_extract_choice returns {} when response has no choices attribute and is not a dict."""

    def fake_completions(**kwargs):
        # Return a plain string — neither dict nor object with .choices
        return "unexpected string response"

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
    )

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
    )
    result = await orchestrator.chat(ChatRequest(message="test"))
    assert result.content == ""
    assert result.tool_called is False


@pytest.mark.asyncio
async def test_extract_choice_choice_without_model_dump(monkeypatch):
    """_extract_choice returns {} when choice is not dict and has no model_dump."""

    class FakeChoiceNoModelDump:
        """A choice-like object that has NO model_dump method."""

        pass

    class FakeResponseWithChoices:
        choices = [FakeChoiceNoModelDump()]

    def fake_completions(**kwargs):
        return FakeResponseWithChoices()

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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
    """When deep_research raises, returns ChatResponse with error detail instead of 500."""
    import json as _json

    def fake_completions(**kwargs):
        return {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_err",
                                "type": "function",
                                "function": {
                                    "name": "deep_research",
                                    "arguments": _json.dumps(
                                        {
                                            "research_question": "will fail",
                                            "deliverable_format": "markdown_brief",
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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
    assert "deep_research failed" in result.content
    assert "upstream timeout" in result.research_summary


@pytest.mark.asyncio
async def test_extract_tool_calls_handles_pydantic_objects(monkeypatch):
    """_extract_tool_calls normalises Pydantic-like tool call objects to dicts."""
    import json as _json

    class FakeFunctionCall:
        def model_dump(self):
            return {
                "name": "deep_research",
                "arguments": _json.dumps(
                    {
                        "research_question": "pydantic q",
                        "deliverable_format": "markdown_brief",
                    }
                ),
            }

    class FakeToolCall:
        type = "function"
        id = "call_pydantic"

        def model_dump(self):
            return {
                "id": self.id,
                "type": self.type,
                "function": {
                    "name": "deep_research",
                    "arguments": _json.dumps(
                        {
                            "research_question": "pydantic q",
                            "deliverable_format": "markdown_brief",
                        }
                    ),
                },
            }

    turn = 0

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            # Return a response where tool_calls contains a Pydantic-like object
            class FakeMessage:
                role = "assistant"
                content = None
                tool_calls = [FakeToolCall()]

                def get(self, key, default=None):
                    return getattr(self, key, default)

            class FakeChoice:
                finish_reason = "tool_calls"
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [FakeToolCall()],
                }

                def get(self, key, default=None):
                    return getattr(self, key, default)

            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [FakeToolCall()],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "done",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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


# ---------------------------------------------------------------------------
# New tests: system_prompt and deliverable_format passthrough
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_system_prompt_forwarded_to_deep_research(monkeypatch):
    """ChatRequest.system_prompt is passed to DeepResearchArguments when tool is called."""
    import json as _json

    turn = 0

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_sp",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": _json.dumps(
                                            {
                                                "research_question": "짜장면 역사",
                                                "deliverable_format": "markdown_brief",
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "English answer about jjajangmyeon.",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_no_sp",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": _json.dumps(
                                            {
                                                "research_question": "test",
                                                "deliverable_format": "markdown_brief",
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "answer",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            # Model does not include deliverable_format in tool args
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_fmt",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": _json.dumps(
                                            {
                                                "research_question": "짜장면",
                                                # no deliverable_format key
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "done",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    # Caller requests markdown_report as the preferred format
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

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            # Model explicitly sets json_outline
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_override",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": _json.dumps(
                                            {
                                                "research_question": "짜장면",
                                                "deliverable_format": "json_outline",
                                            }
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "done",
                        "tool_calls": None,
                    },
                }
            ]
        }

    monkeypatch.setattr(
        "litellm_relay.chat_orchestrator.litellm.completion", fake_completions
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

    # Request says markdown_report but model overrides with json_outline
    await orchestrator.chat(
        ChatRequest(message="짜장면", deliverable_format="markdown_report")
    )

    assert len(captured_args) == 1
    # Model's choice (json_outline) takes precedence over caller's (markdown_report)
    assert captured_args[0].deliverable_format == "json_outline"


@pytest.mark.asyncio
async def test_chat_request_defaults(monkeypatch):
    """ChatRequest defaults: system_prompt=None, deliverable_format='markdown_brief'."""
    req = ChatRequest(message="hello")
    assert req.system_prompt is None
    assert req.deliverable_format == "markdown_brief"
    assert req.auto_tool_call is True
    assert req.context == []
