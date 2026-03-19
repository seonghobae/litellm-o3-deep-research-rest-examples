from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DeliverableFormat = Literal["markdown_brief", "markdown_report", "json_outline"]
InvocationMode = Literal["foreground", "background", "stream"]
InvocationStatus = Literal["pending", "queued", "running", "completed", "failed"]


class DeepResearchArguments(BaseModel):
    """Structured arguments for a deep-research tool invocation.

    These fields form the public contract exposed by the relay.  The relay
    translates them into a LiteLLM Responses API request internally so that
    callers never need to know the upstream ``input`` string format.

    Prompt construction
    -------------------
    The relay uses the Responses API, which separates model-level instructions
    from the user-facing question:

    * **system_prompt** maps to the Responses API ``instructions`` field (the
      system / developer layer that shapes model behaviour, e.g. persona,
      output language, answer format).  When omitted the relay sends no
      ``instructions`` and the model uses its default behaviour.

    * **research_question** (+ ``context``, ``constraints``,
      ``deliverable_format``, ``require_citations``) are rendered into the
      ``input`` string, which is the user turn passed to the model.

    This separation is semantically equivalent to the ``system`` / ``user``
    split in the Chat Completions API and the ``developer`` / ``user`` roles
    in the Responses API message-array format.
    """

    research_question: str
    system_prompt: str | None = Field(
        default=None,
        description=(
            "Optional model-level instructions (maps to the Responses API "
            "``instructions`` field / system prompt).  Use this to set a "
            "persona, output language, or answer format without polluting the "
            "research question."
        ),
    )
    context: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverable_format: DeliverableFormat
    require_citations: bool = True
    background: bool = False
    stream: bool = False

    @model_validator(mode="after")
    def validate_execution_mode(self) -> DeepResearchArguments:
        if self.background and self.stream:
            raise ValueError("background and stream cannot both be true")
        return self


class ToolInvocationRequest(BaseModel):
    """Inbound request payload for ``POST /api/v1/tool-invocations``."""

    tool_name: Literal["deep_research"]
    arguments: DeepResearchArguments


class ToolInvocationView(BaseModel):
    """Outbound response shape for all tool-invocation endpoints."""

    model_config = ConfigDict(extra="ignore")

    invocation_id: str
    tool_name: Literal["deep_research"]
    mode: InvocationMode
    status: InvocationStatus
    deliverable_format: DeliverableFormat
    upstream_response_id: str | None = None
    output_text: str | None = None
    response: dict[str, Any] | None = None
    error_message: str | None = None


class ToolInvocationEvent(BaseModel):
    """A single SSE frame emitted by ``GET /api/v1/tool-invocations/{id}/events``."""

    invocation_id: str
    type: Literal["status", "output_text", "completed", "error"]
    status: InvocationStatus
    data: dict[str, Any] = Field(default_factory=dict)
