from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DeliverableFormat = Literal["markdown_brief", "markdown_report", "json_outline"]
InvocationMode = Literal["foreground", "background", "stream"]
InvocationStatus = Literal["pending", "queued", "running", "completed", "failed"]

# ---------------------------------------------------------------------------
# Structured output / response format types
# ---------------------------------------------------------------------------


class TextFormatJsonObject(BaseModel):
    """Request JSON-object mode: the model MUST return a valid JSON object.

    Supported by: gpt-4o and most chat models via the Responses API.
    **Not** supported by o3-deep-research (raises 400 if used with that model).
    """

    type: Literal["json_object"] = "json_object"


class TextFormatJsonSchema(BaseModel):
    """Request strict JSON schema mode: the model output must validate against
    the supplied JSON Schema.

    Supported by: gpt-4o and compatible models.
    **Not** supported by o3-deep-research (raises 400 if used with that model).
    """

    type: Literal["json_schema"] = "json_schema"
    name: str
    schema_: dict[str, Any] = Field(..., alias="schema")
    strict: bool = True

    model_config = ConfigDict(populate_by_name=True)


class TextFormatText(BaseModel):
    """Explicit plain-text mode (default when omitted)."""

    type: Literal["text"] = "text"


TextFormat = TextFormatJsonObject | TextFormatJsonSchema | TextFormatText


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

    Structured output (text_format)
    --------------------------------
    ``text_format`` maps directly to the Responses API ``text.format`` object.
    Use this when you need machine-readable JSON instead of markdown prose.

    * ``{"type": "json_object"}`` — the model MUST return a valid JSON object.
      Supported by gpt-4o and similar models.  **Not** supported by
      o3-deep-research (the upstream API returns HTTP 400).
    * ``{"type": "json_schema", "name": "...", "schema": {...}, "strict": true}``
      — strict schema validation.  Same model support constraints as
      ``json_object``.
    * ``null`` (default) — plain text / markdown.

    When ``text_format`` is set the relay passes
    ``text={"format": <text_format_dict>}`` to ``litellm.responses()``.
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
    text_format: TextFormat | None = Field(
        default=None,
        description=(
            "Optional structured-output format descriptor.  Maps to the "
            "Responses API ``text.format`` field.  Supported by gpt-4o; "
            "o3-deep-research does NOT support json_schema and returns an "
            "error.  json_object is accepted by o3-deep-research at the API "
            "level but whether the model honours it is not guaranteed."
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
