"""
API schemas for the copilot (spec 24, 26).

The response intentionally carries only a *safe* tool trace: tool name, status,
source, and a short note. No SQL, no database credentials, no internal prompt,
and no raw tool payloads are exposed (spec 26).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CopilotChatRequest(BaseModel):
    """Body for ``POST /copilot/chat``."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        min_length=1,
        max_length=200,
        description="Operator session handle, e.g. 'demo-session'.",
    )
    incident_id: Optional[UUID] = Field(
        default=None,
        description="Incident to focus on. Pinned to the conversation for follow-ups.",
    )
    message: str = Field(min_length=1, max_length=4000)


class CopilotChatStreamRequest(BaseModel):
    """Body for ``POST /copilot/sessions/{session_id}/chat/stream``."""

    model_config = ConfigDict(extra="forbid")

    incident_id: Optional[UUID] = None
    message: str = Field(min_length=1, max_length=4000)


class ToolTrace(BaseModel):
    """One entry in the safe tool trace."""

    model_config = ConfigDict(extra="forbid")

    tool: str
    status: str = Field(description="success | unavailable | error | denied | invalid")
    source: Optional[str] = None
    note: Optional[str] = None


class CopilotChatResponse(BaseModel):
    """Body returned by ``POST /copilot/chat``."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    incident_id: Optional[UUID] = None
    answer: str
    sources: List[str] = Field(default_factory=list)
    tools_used: List[ToolTrace] = Field(default_factory=list)
    # Items the operator should treat as open questions.
    uncertainty: List[str] = Field(default_factory=list)
    model_name: Optional[str] = None
    # True when the request asked for an action the copilot will not perform.
    refused_action: bool = False
    created_at: datetime


class CopilotMessageOut(BaseModel):
    """A stored conversation message."""

    model_config = ConfigDict(from_attributes=True)

    role: str
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[Dict[str, Any]] = None
    created_at: datetime


class CopilotConversationResponse(BaseModel):
    """Body returned by ``GET /copilot/conversations/{session_id}``."""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    incident_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    messages: List[CopilotMessageOut] = Field(default_factory=list)


class CopilotToolInfo(BaseModel):
    """A tool's metadata, for the operator-facing permissions view."""

    model_config = ConfigDict(extra="forbid")

    name: str
    permission: str = Field(description="read_only | controlled_action")
    source: str
    description: str


class CopilotToolsResponse(BaseModel):
    """Body returned by ``GET /copilot/tools``."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    model_name: str
    controlled_actions_enabled: bool
    tools: List[CopilotToolInfo]


class CopilotDeleteResponse(BaseModel):
    """Body returned by ``DELETE /copilot/conversations/{session_id}``."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    deleted: bool
    messages_deleted: int
