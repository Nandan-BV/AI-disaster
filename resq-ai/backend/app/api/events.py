from datetime import datetime
from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_role
from app.database import get_db
from app.live_events import event_connections
from app.models.user import UserRole
from app.schemas.event import EventCreate, EventResponse, EventListResponse, EventDeleteResponse
from app.services.external_ingestion import poll_external_feeds
from app.services.event_service import EventService


router = APIRouter(prefix="/events", tags=["events"])
websocket_router = APIRouter()


@websocket_router.websocket("/ws/events")
async def live_events(websocket: WebSocket):
    await event_connections.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        event_connections.disconnect(websocket)


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event_data: EventCreate,
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(get_current_user),
):
    service = EventService(db)
    event = await service.create_event(event_data)
    response = EventResponse.model_validate(event)
    await event_connections.broadcast(
        {"type": "event.created", "event": response.model_dump(mode="json")}
    )
    return response


@router.get("", response_model=EventListResponse)
async def list_events(
    source: Optional[str] = Query(None, description="Filter by source"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of events to return"),
    offset: int = Query(0, ge=0, description="Number of events to skip"),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    events, total = await service.get_events(
        source=source,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(events=events, total=total, limit=limit, offset=offset)


@router.post("/sync-external", response_model=dict)
async def sync_external_events(
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(
        require_role([UserRole.DISPATCHER, UserRole.COMMANDER, UserRole.ADMIN])
    ),
):
    """Poll configured external disaster feeds and cluster any newly stored events."""
    return await poll_external_feeds(db)


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    event = await service.get_event_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found"
        )
    return event


@router.delete("/{event_id}", response_model=EventDeleteResponse)
async def delete_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    deleted = await service.delete_event(event_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with id {event_id} not found"
        )
    return EventDeleteResponse(message="Event deleted successfully", event_id=event_id)