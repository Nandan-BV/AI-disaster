"""
Conversation storage for the copilot (spec 23).

A conversation belongs to an operator session and may be pinned to an incident.
The pinned incident is what lets a follow-up like "what resources are nearby?"
resolve without the operator repeating the id (spec 22).

Stored rows are limited to what is needed to reconstruct the conversation. The
full system prompt is never persisted, and tool payloads are stored as the safe
trace (tool name, status, source) rather than raw database records, so the table
does not become a shadow copy of operational data (spec 23).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

import enum
import uuid

from app.database import Base


class MessageRole(str, enum.Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class CopilotConversation(Base):
    __tablename__ = "copilot_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Operator-supplied handle, e.g. "demo-session". Not an auth credential.
    session_id = Column(String(200), nullable=False, unique=True, index=True)
    # Null until an operator selects an incident; remembered for follow-ups.
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True
    )

    messages = relationship(
        "CopilotMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CopilotMessage.sequence",
    )

    __table_args__ = (
        Index("ix_copilot_conversations_session", "session_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CopilotConversation(session={self.session_id!r}, "
            f"incident={self.incident_id})>"
        )


class CopilotMessage(Base):
    __tablename__ = "copilot_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Monotonic per-conversation ordering; timestamps can tie at second precision.
    sequence = Column(Integer, nullable=False, default=0)
    role = Column(SQLEnum(MessageRole), nullable=False, index=True)
    content = Column(Text, nullable=False)
    tool_name = Column(String(100), nullable=True)
    # Safe trace only: {"arguments": ..., "status": ..., "source": ...}
    tool_input = Column(JSON, nullable=True)
    # Redacted summary of the tool result, never the raw payload.
    tool_output = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    conversation = relationship("CopilotConversation", back_populates="messages")

    __table_args__ = (
        Index("ix_copilot_messages_conversation_sequence", "conversation_id", "sequence"),
    )

    def __repr__(self) -> str:
        return f"<CopilotMessage(role={self.role}, seq={self.sequence})>"
