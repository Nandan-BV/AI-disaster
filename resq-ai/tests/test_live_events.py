from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import events
from app.core.security import get_current_user
from app.database import get_db
from app.live_events import EventConnectionManager
from app.main import app


@pytest.mark.asyncio
async def test_broadcast_sends_event_to_connected_clients():
    manager = EventConnectionManager()
    client = AsyncMock()
    message = {"type": "event.created", "event": {"id": "new-event"}}

    await manager.connect(client)
    await manager.broadcast(message)

    client.accept.assert_awaited_once()
    client.send_json.assert_awaited_once_with(message)


def test_event_ingestion_broadcasts_to_websocket_clients():
    timestamp = datetime.now(timezone.utc)
    event = SimpleNamespace(
        id=uuid4(),
        source="emergency_services",
        text_content="Flooding reported",
        event_type="flood",
        latitude=12.9716,
        longitude=77.5946,
        location_name="MG Road",
        timestamp=timestamp,
        image_url=None,
        video_url=None,
        metadata={},
        created_at=timestamp,
        updated_at=timestamp,
    )

    async def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: object()
    try:
        with TestClient(app) as client:
            with client.websocket_connect("/ws/events") as websocket:
                with pytest.MonkeyPatch.context() as monkeypatch:
                    service = AsyncMock()
                    service.create_event.return_value = event
                    monkeypatch.setattr(events, "EventService", lambda _db: service)
                    response = client.post(
                        "/api/v1/events",
                        json={
                            "source": "emergency_services",
                            "text_content": "Flooding reported",
                            "event_type": "flood",
                            "latitude": 12.9716,
                            "longitude": 77.5946,
                            "location_name": "MG Road",
                            "timestamp": timestamp.isoformat(),
                        },
                    )

                assert response.status_code == 201
                message = websocket.receive_json()
                assert message["type"] == "event.created"
                assert message["event"]["id"] == str(event.id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
