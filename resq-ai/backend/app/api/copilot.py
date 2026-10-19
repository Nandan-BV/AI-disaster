"""
Copilot API (spec 24, 25, 26).

    POST   /copilot/chat
    GET    /copilot/conversations/{session_id}
    DELETE /copilot/conversations/{session_id}
    GET    /copilot/tools

Every route is read-only with respect to operational data. The copilot cannot
approve, dispatch, or mutate anything through this surface.
"""

import logging
import json
from datetime import datetime, timezone
from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.copilot import CopilotService
from app.ai.llm import get_llm_client
from app.ai.llm.base import CopilotLLMError
from app.ai.tool_registry import tool_registry
from app.ai.tools import register_all_tools
from app.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.copilot import CopilotConversation, CopilotMessage
from app.schemas.copilot import (
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotChatStreamRequest,
    CopilotConversationResponse,
    CopilotDeleteResponse,
    CopilotMessageOut,
    CopilotToolInfo,
    CopilotToolsResponse,
    ToolTrace,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/copilot", tags=["copilot"])

SESSION_ID_HELP = "Operator session handle, e.g. 'demo-session'."


@router.post(
    "/sessions/{session_id}/chat/stream",
    summary="Stream a grounded copilot answer as server-sent events",
)
async def copilot_chat_stream(
    session_id: Annotated[str, Path(min_length=1, max_length=200)],
    payload: CopilotChatStreamRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> EventSourceResponse:
    register_all_tools()
    service = CopilotService(db)

    async def events():
        try:
            async for item in service.answer_stream(
                session_id=session_id,
                message=payload.message,
                incident_id=payload.incident_id,
            ):
                event_type = item.pop("type")
                yield {
                    "event": event_type,
                    "data": json.dumps(item, default=str),
                }
        except CopilotLLMError as exc:
            logger.warning("Copilot stream unavailable for session %s: %s", session_id, exc)
            yield {
                "event": "error",
                "data": json.dumps({"detail": str(exc)}),
            }
        except Exception:
            logger.exception("Copilot streaming request failed")
            yield {
                "event": "error",
                "data": json.dumps(
                    {"detail": "The copilot could not complete this request."}
                ),
            }

    return EventSourceResponse(events())


@router.post(
    "/chat",
    response_model=CopilotChatResponse,
    summary="Ask the emergency response copilot a question",
)
async def copilot_chat(
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> CopilotChatResponse:
    """Answer an operator question using grounded backend tools.

    The copilot reads data through a fixed toolset and cannot dispatch,
    approve, or modify any record.
    """
    register_all_tools()
    service = CopilotService(db)

    try:
        result = await service.answer(
            session_id=payload.session_id,
            message=payload.message,
            incident_id=payload.incident_id,
        )
    except CopilotLLMError as exc:
        # Controlled failure: the operator is told the copilot is unavailable
        # and is never given a fabricated answer (spec 46).
        logger.warning("Copilot unavailable for session %s: %s", payload.session_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Copilot request failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The copilot could not complete this request.",
        ) from exc

    return CopilotChatResponse(
        session_id=payload.session_id,
        incident_id=result.incident_id,
        answer=result.answer,
        sources=result.sources,
        tools_used=[ToolTrace(**entry.to_dict()) for entry in result.tools_used],
        uncertainty=result.uncertainty,
        model_name=result.model_name,
        refused_action=result.refused,
        created_at=datetime.now(timezone.utc),
    )


@router.get(
    "/conversations/{session_id}",
    response_model=CopilotConversationResponse,
    summary="Retrieve stored conversation history",
)
async def get_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> CopilotConversationResponse:
    conversation = (
        await db.execute(
            select(CopilotConversation).where(CopilotConversation.session_id == session_id)
        )
    ).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No conversation found for session {session_id!r}.",
        )

    messages: List[CopilotMessage] = (
        await db.execute(
            select(CopilotMessage)
            .where(CopilotMessage.conversation_id == conversation.id)
            .order_by(CopilotMessage.sequence.asc())
        )
    ).scalars().all()

    return CopilotConversationResponse(
        session_id=conversation.session_id,
        incident_id=conversation.incident_id,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(messages),
        messages=[CopilotMessageOut.model_validate(m) for m in messages],
    )


@router.delete(
    "/conversations/{session_id}",
    response_model=CopilotDeleteResponse,
    summary="Delete a stored conversation",
)
async def delete_conversation(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
) -> CopilotDeleteResponse:
    """Remove a conversation and its messages.

    This deletes chat history only. It does not touch any incident, resource,
    or optimization record.
    """
    conversation = (
        await db.execute(
            select(CopilotConversation).where(CopilotConversation.session_id == session_id)
        )
    ).scalar_one_or_none()

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No conversation found for session {session_id!r}.",
        )

    count = int(
        (
            await db.execute(
                select(func.count(CopilotMessage.id)).where(
                    CopilotMessage.conversation_id == conversation.id
                )
            )
        ).scalar_one()
    )

    # Messages cascade at the database level too; deleted explicitly so the
    # count is accurate on deployments where the cascade is deferred.
    await db.execute(
        delete(CopilotMessage).where(CopilotMessage.conversation_id == conversation.id)
    )
    await db.delete(conversation)
    await db.commit()

    return CopilotDeleteResponse(
        session_id=session_id, deleted=True, messages_deleted=count
    )


@router.get(
    "/tools",
    response_model=CopilotToolsResponse,
    summary="List copilot tools and their permissions",
)
async def list_tools() -> CopilotToolsResponse:
    """Expose the toolset and its permission classification.

    Note the absence of any approve, dispatch, or mutation tool: that is the
    human-in-the-loop boundary, made inspectable.
    """
    register_all_tools()

    tools = [
        CopilotToolInfo(
            name=tool.name,
            permission=tool.permission.value,
            source=tool.source,
            description=tool.definition.description,
        )
        for tool in (tool_registry.get(name) for name in tool_registry.names())
    ]

    return CopilotToolsResponse(
        provider=settings.COPILOT_PROVIDER,
        model_name=get_llm_client().model_name,
        controlled_actions_enabled=settings.COPILOT_ALLOW_CONTROLLED_ACTIONS,
        tools=tools,
    )
