"""LiteLLM 릴레이의 요청·응답 계약 모델을 정의한다."""

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
    """유효한 JSON 객체 응답을 요구하는 출력 형식이다."""

    type: Literal["json_object"] = "json_object"


class TextFormatJsonSchema(BaseModel):
    """지정된 JSON 스키마를 강제하는 구조화 출력 형식이다."""

    type: Literal["json_schema"] = "json_schema"
    name: str
    schema_: dict[str, Any] = Field(..., alias="schema")
    strict: bool = True

    model_config = ConfigDict(populate_by_name=True)


class TextFormatText(BaseModel):
    """명시적인 일반 텍스트 출력 형식이다."""

    type: Literal["text"] = "text"


TextFormat = TextFormatJsonObject | TextFormatJsonSchema | TextFormatText


class DeepResearchArguments(BaseModel):
    """deep_research 도구 호출에 사용되는 구조화 인자다."""

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
        """background와 stream이 동시에 켜지지 않았는지 검증한다."""
        if self.background and self.stream:
            raise ValueError("background and stream cannot both be true")
        return self


class ToolInvocationRequest(BaseModel):
    """``POST /api/v1/tool-invocations`` 요청 본문이다."""

    tool_name: Literal["deep_research"]
    arguments: DeepResearchArguments


class ToolInvocationView(BaseModel):
    """도구 호출 관련 모든 응답 엔드포인트의 공통 응답 모델이다."""

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
    """도구 호출 이벤트 스트림에서 방출되는 단일 SSE 프레임이다."""

    invocation_id: str
    type: Literal["status", "output_text", "completed", "error"]
    status: InvocationStatus
    data: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Inbound payload for ``POST /api/v1/chat``.

    The relay uses the ``message`` as the first Responses API user turn with a
    ``deep_research`` function tool attached. When the model decides the
    question warrants deep research it returns a ``function_call`` output item;
    the relay executes the research and performs a second Responses API turn
    with ``function_call_output`` to produce the final natural-language answer.
    """

    message: str
    context: list[str] = Field(default_factory=list)
    auto_tool_call: bool = True
    system_prompt: str | None = Field(
        default=None,
        description=(
            "Optional system-level instructions forwarded to the deep_research "
            "invocation (Responses API ``instructions`` field). Use to set "
            "persona, output language, or format constraints."
        ),
    )
    deliverable_format: DeliverableFormat = Field(
        default="markdown_brief",
        description=(
            "Deliverable format for the deep_research invocation "
            "(default: ``markdown_brief``). Used as fallback when the model "
            "does not specify a format in its tool-call arguments."
        ),
    )


class ChatResponse(BaseModel):
    """``POST /api/v1/chat`` 응답 본문이다."""

    content: str
    tool_called: bool
    tool_name: str | None = None
    research_summary: str | None = None
