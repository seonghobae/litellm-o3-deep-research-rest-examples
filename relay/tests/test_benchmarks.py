"""Performance benchmarks for the relay's hot-path operations."""

from __future__ import annotations

import json

import pytest

from litellm_relay.contracts import (
    ChatRequest,
    ChatResponse,
    DeepResearchArguments,
    ToolInvocationEvent,
    ToolInvocationRequest,
    ToolInvocationView,
)
from litellm_relay.upstream import LiteLLMRelayGateway


# ---------------------------------------------------------------------------
# Fixtures: reusable payloads
# ---------------------------------------------------------------------------

TOOL_INVOCATION_PAYLOAD = {
    "tool_name": "deep_research",
    "arguments": {
        "research_question": "What changed in Azure OpenAI o3-deep-research?",
        "deliverable_format": "markdown_report",
        "context": ["Azure update notes", "OpenAI changelog"],
        "constraints": ["Focus on the last 6 months"],
        "require_citations": True,
        "background": False,
        "stream": False,
    },
}

CHAT_REQUEST_PAYLOAD = {
    "message": "Explain the history of deep research models in detail",
    "context": ["AI research timeline", "OpenAI model releases"],
    "auto_tool_call": True,
    "system_prompt": "Always answer in English only.",
    "deliverable_format": "markdown_report",
}

UPSTREAM_RESPONSE_PAYLOAD = {
    "id": "resp_abc123",
    "status": "completed",
    "output_text": "Deep research results: " + "x" * 500,
    "output": [
        {
            "content": [
                {"type": "output_text", "text": "Deep research results: " + "x" * 500}
            ]
        }
    ],
}


# ---------------------------------------------------------------------------
# Contract validation benchmarks
# ---------------------------------------------------------------------------


def test_bench_tool_invocation_request_validation(benchmark):
    """Benchmark Pydantic validation of a ToolInvocationRequest payload."""
    benchmark(ToolInvocationRequest.model_validate, TOOL_INVOCATION_PAYLOAD)


def test_bench_chat_request_validation(benchmark):
    """Benchmark Pydantic validation of a ChatRequest payload."""
    benchmark(ChatRequest.model_validate, CHAT_REQUEST_PAYLOAD)


def test_bench_chat_response_serialization(benchmark):
    """Benchmark ChatResponse construction and serialization."""
    resp = ChatResponse(
        content="Detailed answer " * 50,
        tool_called=True,
        tool_name="deep_research",
        research_summary="Summary " * 30,
    )
    benchmark(resp.model_dump_json)


def test_bench_tool_invocation_view_serialization(benchmark):
    """Benchmark ToolInvocationView serialization to JSON."""
    view = ToolInvocationView(
        invocation_id="inv-001",
        tool_name="deep_research",
        mode="foreground",
        status="completed",
        deliverable_format="markdown_report",
        upstream_response_id="resp_abc123",
        output_text="Result text " * 100,
        response=UPSTREAM_RESPONSE_PAYLOAD,
    )
    benchmark(view.model_dump_json)


def test_bench_deep_research_arguments_validation(benchmark):
    """Benchmark DeepResearchArguments validation with all fields."""
    args_payload = {
        "research_question": "Comprehensive analysis of LLM performance trends",
        "system_prompt": "You are a research analyst. Answer in Korean.",
        "deliverable_format": "json_outline",
        "context": [f"Context item {i}" for i in range(10)],
        "constraints": ["Must include citations", "Focus on 2024-2025"],
        "require_citations": True,
        "background": False,
        "stream": False,
    }
    benchmark(DeepResearchArguments.model_validate, args_payload)


# ---------------------------------------------------------------------------
# Input rendering benchmark
# ---------------------------------------------------------------------------


def test_bench_render_input(benchmark):
    """Benchmark upstream input string rendering from DeepResearchArguments."""
    args = DeepResearchArguments(
        research_question="What are the latest advances in deep research models?",
        deliverable_format="markdown_report",
        context=["AI research papers 2024", "OpenAI blog posts", "Azure updates"],
        constraints=["English only", "Include citations", "Last 12 months"],
        require_citations=True,
    )
    benchmark(LiteLLMRelayGateway._render_input, args)


# ---------------------------------------------------------------------------
# Response extraction benchmarks
# ---------------------------------------------------------------------------


def test_bench_extract_response_text_from_output_text(benchmark):
    """Benchmark text extraction when output_text is directly available."""
    benchmark(
        LiteLLMRelayGateway._extract_response_text, UPSTREAM_RESPONSE_PAYLOAD
    )


def test_bench_extract_response_text_from_output_blocks(benchmark):
    """Benchmark text extraction from nested output content blocks."""
    payload = {
        "id": "resp_nested",
        "status": "completed",
        "output": [
            {
                "content": [
                    {"type": "output_text", "text": "First block " * 50},
                    {"type": "text", "text": "Second block " * 50},
                ]
            },
            {
                "content": [
                    {"type": "output_text", "text": "Third block " * 50},
                ]
            },
        ],
    }
    benchmark(LiteLLMRelayGateway._extract_response_text, payload)


def test_bench_extract_stream_text_delta(benchmark):
    """Benchmark stream text delta extraction."""
    event = {"type": "response.output_text.delta", "delta": "chunk " * 20}
    benchmark(LiteLLMRelayGateway._extract_stream_text, event)


# ---------------------------------------------------------------------------
# SSE serialization benchmark
# ---------------------------------------------------------------------------


def test_bench_sse_serialization(benchmark):
    """Benchmark SSE frame serialization from a ToolInvocationEvent."""
    from litellm_relay.service import RelayService

    event = ToolInvocationEvent(
        invocation_id="inv-bench-001",
        type="output_text",
        status="running",
        data={"text": "Streaming text chunk " * 20},
    )
    benchmark(RelayService._to_sse, event)
