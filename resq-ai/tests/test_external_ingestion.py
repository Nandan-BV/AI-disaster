from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import events as events_api
from app.core.security import get_current_user
from app.database import get_db
from app.main import app
from app.models.user import UserRole
from app.schemas.event import EventCreate
from app.services.external_ingestion import (
    ExternalIngestionService,
    _gdacs_geojson_events,
    _gdacs_rss_events,
    _parse_datetime,
    _usgs_event,
)


def test_usgs_feature_maps_to_event_with_stable_external_id():
    event = _usgs_event(
        {
            "id": "us7000abcd",
            "properties": {
                "time": 1791648000000,
                "mag": 6.1,
                "place": "Near Example Island",
                "url": "https://earthquake.usgs.gov/example",
            },
            "geometry": {"coordinates": [142.1, 35.2, 20.0]},
        }
    )

    assert event is not None
    assert event.source == "usgs"
    assert event.external_id == "us7000abcd"
    assert event.event_type == "earthquake"
    assert event.longitude == 142.1
    assert event.latitude == 35.2
    assert event.metadata["depth_km"] == 20.0


def test_gdacs_rss_maps_flood_cyclone_and_wildfire_entries():
    document = b"""<?xml version="1.0"?>
    <rss xmlns:gdacs="urn:gdacs" xmlns:geo="http://www.w3.org/2003/01/geo/wgs84_pos#">
      <channel>
        <item>
          <title>River flood in Example</title><guid>FL-1</guid>
          <gdacs:eventtype>FL</gdacs:eventtype><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate>
          <geo:lat>10.5</geo:lat><geo:long>20.5</geo:long>
        </item>
        <item>
          <title>Cyclone Example</title><guid>TC-2</guid>
          <gdacs:eventtype>TC</gdacs:eventtype><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate>
          <geo:Point><geo:lat>-12.5</geo:lat><geo:long>45.5</geo:long></geo:Point>
        </item>
        <item>
          <title>Wildfire Example</title><guid>WF-3</guid>
          <gdacs:eventtype>WF</gdacs:eventtype><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate>
          <geo:lat>30</geo:lat><geo:long>-110</geo:long>
        </item>
        <item>
          <title>Earthquake Example</title><guid>EQ-4</guid>
          <gdacs:eventtype>EQ</gdacs:eventtype><pubDate>Sat, 10 Oct 2026 10:00:00 GMT</pubDate>
          <geo:lat>1</geo:lat><geo:long>2</geo:long>
        </item>
      </channel>
    </rss>"""

    events = _gdacs_rss_events(document)

    assert [event.event_type for event in events] == ["flood", "cyclone", "wildfire"]
    assert [event.external_id for event in events] == ["FL-1", "TC-2", "WF-3"]
    assert events[1].latitude == -12.5
    assert events[1].longitude == 45.5


def test_gdacs_geojson_uses_polygon_center_and_ignores_unknown_alert_types():
    events = _gdacs_geojson_events(
        {
            "features": [
                {
                    "id": "gdacs-flood-1",
                    "properties": {
                        "eventtype": "FL",
                        "fromdate": "2026-10-10T10:00:00Z",
                        "eventname": "Example flood",
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
                    },
                },
                {
                    "id": "gdacs-earthquake-2",
                    "properties": {"eventtype": "EQ"},
                    "geometry": {"type": "Point", "coordinates": [5, 6]},
                },
            ]
        }
    )

    assert len(events) == 1
    assert events[0].event_type == "flood"
    assert events[0].latitude == 0.8
    assert events[0].longitude == 0.8


def test_datetime_parser_handles_usgs_milliseconds_and_weather_seconds():
    expected = datetime(2026, 10, 10, 16, 0)
    assert _parse_datetime(1791648000000) == expected
    assert _parse_datetime(1791648000) == expected


class FakeResult:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDatabase:
    def __init__(self):
        self.execute = AsyncMock(return_value=FakeResult())
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.added = []

    def add(self, instance):
        instance.id = uuid4()
        instance.created_at = datetime(2026, 10, 10, 12)
        instance.updated_at = datetime(2026, 10, 10, 12)
        self.added.append(instance)


@pytest.mark.asyncio
async def test_new_feed_event_is_persisted_clustered_and_broadcast(monkeypatch):
    database = FakeDatabase()
    cluster = AsyncMock(return_value={"incident_id": str(uuid4())})
    broadcast = AsyncMock()
    monkeypatch.setattr("app.services.external_ingestion.process_new_event", cluster)
    monkeypatch.setattr(
        "app.services.external_ingestion.event_connections.broadcast",
        broadcast,
    )
    event_data = EventCreate(
        source="usgs",
        external_id="us7000-unique",
        event_type="earthquake",
        text_content="Significant earthquake",
        latitude=10,
        longitude=20,
        timestamp=datetime(2026, 10, 10, 12),
    )
    result = {"cluster_errors": []}

    created = await ExternalIngestionService(database)._store_and_cluster(
        event_data,
        result,
    )

    assert created is True
    assert len(database.added) == 1
    assert database.added[0].external_id == "us7000-unique"
    cluster.assert_awaited_once_with(database.added[0].id, database)
    broadcast.assert_awaited_once()
    assert result["cluster_errors"] == []


@pytest.mark.asyncio
async def test_known_external_id_is_skipped_as_duplicate():
    existing = SimpleNamespace(id=uuid4())
    database = FakeDatabase()
    database.execute.return_value = FakeResult(existing)
    event_data = EventCreate(
        source="usgs",
        external_id="us7000-already-stored",
        event_type="earthquake",
        text_content="Previously ingested event",
        latitude=10,
        longitude=20,
        timestamp=datetime(2026, 10, 10, 12),
    )

    result = {"cluster_errors": []}
    created = await ExternalIngestionService(database)._store_and_cluster(
        event_data,
        result,
    )

    assert created is False
    assert database.added == []


@pytest.mark.asyncio
async def test_manual_external_poll_endpoint_calls_ingestion(monkeypatch):
    async def override_db():
        yield object()

    async def override_user():
        return SimpleNamespace(role=UserRole.ADMIN)

    poll = AsyncMock(
        return_value={
            "inserted": 1,
            "duplicates": 0,
            "cluster_errors": [],
            "sources": {"usgs": {"status": "ok", "inserted": 1, "duplicates": 0}},
        }
    )
    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    monkeypatch.setattr(events_api, "poll_external_feeds", poll)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/v1/events/sync-external")
        assert response.status_code == 200
        assert response.json()["inserted"] == 1
        poll.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
