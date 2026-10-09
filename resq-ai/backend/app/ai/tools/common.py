"""
Shared plumbing for copilot tools.

Everything a tool returns is shaped by :class:`ToolResult` so the copilot layer
can build an honest, attributable answer without inspecting tool internals:

* ``source`` names the phase the data came from, surfaced to the operator as
  source attribution (spec 21).
* ``retrieved_at`` / ``data_timestamp`` let the copilot state data freshness and
  never imply real-time accuracy (spec 34).
* ``available`` distinguishes "no data" from "zero", so missing rows are reported
  as unavailable rather than silently becoming a count of zero (spec 33).
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from contextlib import contextmanager
from contextvars import ContextVar

from pydantic import BaseModel, ConfigDict, Field

from app.ai.tool_registry import ToolError


# Tools receive only their validated arguments, so the request-scoped session is
# carried in a ContextVar instead of being threaded through every handler. This
# keeps one pooled connection per chat request rather than one per tool call.
_current_session: ContextVar[Any] = ContextVar("copilot_tool_session", default=None)


@contextmanager
def use_session(session: Any):
    """Bind a session for the duration of a copilot tool loop."""
    token = _current_session.set(session)
    try:
        yield session
    finally:
        _current_session.reset(token)


def current_session() -> Any:
    """Return the active session or raise if no copilot request is in flight."""
    session = _current_session.get()
    if session is None:
        raise ToolError(
            "No database session is bound to this copilot tool call."
        )
    return session


class IncidentRefInput(BaseModel):
    """Input for a tool scoped to a single incident."""

    model_config = ConfigDict(extra="forbid")

    # Incident primary keys are UUIDs in this schema, not the integers used in
    # the Phase 9 spec examples. Validated as UUID so a bad id is rejected
    # before any database access.
    incident_id: UUID = Field(description="Incident UUID.")


def incident_uuid(incident_id: UUID) -> UUID:
    if not isinstance(incident_id, UUID):
        raise ToolError("incident_id must be a UUID.")
    return incident_id


class ToolResult(BaseModel):
    """Uniform envelope returned by every tool."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    available: bool = True
    source: str = "backend"
    data: Dict[str, Any] = Field(default_factory=dict)
    # When the underlying record was written; drives freshness statements.
    data_timestamp: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None

    def unavailable(self, reason: str, source: Optional[str] = None) -> "ToolResult":
        """Report absent data explicitly instead of returning empty values."""
        return ToolResult(
            available=False,
            source=source or self.source,
            data={},
            notes=reason,
        )


def enum_value(value: Any) -> Optional[str]:
    """Return the plain string for a SQLAlchemy enum, or None."""
    if value is None:
        return None
    return getattr(value, "value", value)


def as_dict(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    return None


def jsonable(value: Any) -> Any:
    """Coerce a value into something JSON-serialisable for the model payload."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    return getattr(value, "value", str(value))


def age_description(timestamp: Optional[datetime], now: Optional[datetime] = None) -> Optional[str]:
    """Describe how old a record is, e.g. "8 minutes ago" (spec 34)."""
    if timestamp is None:
        return None
    reference = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    seconds = (reference - timestamp).total_seconds()
    if seconds < 0:
        return "timestamped in the future"
    if seconds < 60:
        return f"{int(seconds)} seconds ago"
    if seconds < 3600:
        return f"{int(seconds // 60)} minutes ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} hours ago"
    return f"{int(seconds // 86400)} days ago"
