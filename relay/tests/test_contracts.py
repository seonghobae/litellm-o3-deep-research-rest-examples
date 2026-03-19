from __future__ import annotations

import pytest
from pydantic import ValidationError

from litellm_relay.contracts import ToolInvocationRequest


def test_valid_deep_research_invocation_parses_correctly() -> None:
    payload = {
        "tool_name": "deep_research",
        "arguments": {
            "research_question": "What changed in Azure OpenAI o3-deep-research?",
            "deliverable_format": "markdown_brief",
        },
    }

    model = ToolInvocationRequest.model_validate(payload)

    assert model.tool_name == "deep_research"
    assert model.arguments.research_question.startswith("What changed")
    assert model.arguments.deliverable_format == "markdown_brief"


def test_unknown_tool_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ToolInvocationRequest.model_validate(
            {
                "tool_name": "not-supported",
                "arguments": {
                    "research_question": "Hello",
                    "deliverable_format": "markdown_brief",
                },
            }
        )


def test_stream_and_background_cannot_both_be_true() -> None:
    with pytest.raises(ValidationError, match="background"):
        ToolInvocationRequest.model_validate(
            {
                "tool_name": "deep_research",
                "arguments": {
                    "research_question": "Hello",
                    "deliverable_format": "markdown_brief",
                    "background": True,
                    "stream": True,
                },
            }
        )
