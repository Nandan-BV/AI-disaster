import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.config import settings


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def test_engine():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(test_engine):
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(test_engine):
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def sample_event_data(**overrides):
    data = {
        "source": "test_source",
        "text_content": "Test disaster event",
        "event_type": "flood",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "location_name": "Test Location",
        "timestamp": "2026-09-21T10:30:00",
        "image_url": None,
        "video_url": None,
        "metadata": {"test": True},
    }
    data.update(overrides)
    return data


class TestCreateEvent:
    @pytest.mark.asyncio
    async def test_create_event_success(self, client):
        response = await client.post("/api/v1/events", json=sample_event_data())
        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "test_source"
        assert data["text_content"] == "Test disaster event"
        assert data["latitude"] == 12.9716
        assert data["longitude"] == 77.5946
        assert "id" in data
        assert UUID(data["id"])

    @pytest.mark.asyncio
    async def test_create_event_without_text_but_with_image(self, client):
        data = sample_event_data(text_content=None, image_url="https://example.com/image.jpg")
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_event_invalid_latitude(self, client):
        data = sample_event_data(latitude=200)
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("latitude" in str(e).lower() for e in errors)

    @pytest.mark.asyncio
    async def test_create_event_invalid_longitude(self, client):
        data = sample_event_data(longitude=-300)
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("longitude" in str(e).lower() for e in errors)

    @pytest.mark.asyncio
    async def test_create_event_empty_source(self, client):
        data = sample_event_data(source="")
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_event_missing_required_fields(self, client):
        data = {"source": "test"}
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_event_invalid_timestamp(self, client):
        data = sample_event_data(timestamp="invalid-timestamp")
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_event_malformed_url(self, client):
        data = sample_event_data(image_url="not-a-url")
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_event_no_content_or_media(self, client):
        data = sample_event_data(text_content=None, image_url=None, video_url=None)
        response = await client.post("/api/v1/events", json=data)
        assert response.status_code == 422


class TestGetEvents:
    @pytest.mark.asyncio
    async def test_get_events_empty(self, client):
        response = await client.get("/api/v1/events")
        assert response.status_code == 200
        data = response.json()
        assert data["events"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_events_with_data(self, client):
        await client.post("/api/v1/events", json=sample_event_data())
        await client.post("/api/v1/events", json=sample_event_data(source="another_source"))
        
        response = await client.get("/api/v1/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_events_filter_by_source(self, client):
        await client.post("/api/v1/events", json=sample_event_data(source="source_a"))
        await client.post("/api/v1/events", json=sample_event_data(source="source_b"))
        
        response = await client.get("/api/v1/events", params={"source": "source_a"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["source"] == "source_a"

    @pytest.mark.asyncio
    async def test_get_events_pagination(self, client):
        for i in range(5):
            await client.post("/api/v1/events", json=sample_event_data(source=f"source_{i}"))
        
        response = await client.get("/api/v1/events", params={"limit": 2, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 2
        assert data["limit"] == 2
        assert data["offset"] == 0


class TestGetEventById:
    @pytest.mark.asyncio
    async def test_get_event_by_id_success(self, client):
        create_response = await client.post("/api/v1/events", json=sample_event_data())
        event_id = create_response.json()["id"]
        
        response = await client.get(f"/api/v1/events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == event_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_event(self, client):
        fake_id = uuid4()
        response = await client.get(f"/api/v1/events/{fake_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteEvent:
    @pytest.mark.asyncio
    async def test_delete_event_success(self, client):
        create_response = await client.post("/api/v1/events", json=sample_event_data())
        event_id = create_response.json()["id"]
        
        response = await client.delete(f"/api/v1/events/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == event_id
        assert "deleted" in data["message"].lower()
        
        get_response = await client.get(f"/api/v1/events/{event_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_event(self, client):
        fake_id = uuid4()
        response = await client.delete(f"/api/v1/events/{fake_id}")
        assert response.status_code == 404


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["project"] == "RESQ-AI"