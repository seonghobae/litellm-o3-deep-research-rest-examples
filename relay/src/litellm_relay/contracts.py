from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DeliverableFormat = Literal["markdown_brief", "markdown_report", "json_outline"]
InvocationMode = Literal["foreground", "background", "stream"]
InvocationStatus = Literal["pending", "queued", "running", "completed", "failed"]


class DeepResearchArguments(BaseModel):
    research_question: str
    context: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    deliverable_format: DeliverableFormat
    require_citations: bool = True
    background: bool = False
    stream: bool = False

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "DeepResearchArguments":
        if self.background and self.stream:
            raise ValueError("background and stream cannot both be true")
        return self


class ToolInvocationRequest(BaseModel):
    tool_name: Literal["deep_research"]
    arguments: DeepResearchArguments


class ToolInvocationView(BaseModel):
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
    invocation_id: str
    type: Literal["status", "output_text", "completed", "error"]
    status: InvocationStatus
    data: dict[str, Any] = Field(default_factory=dict)
