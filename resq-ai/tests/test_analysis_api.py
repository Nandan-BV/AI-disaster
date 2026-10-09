import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db, Base
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.schemas.analysis import DisasterAnalysis
from ai.services.multimodal_analyzer import EventAnalyzer


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


@pytest.fixture(scope="session")
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
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_event(db_session):
    event = Event(
        source="test_source",
        text_content="Heavy flooding reported near city center",
        event_type="flood",
        latitude=12.9716,
        longitude=77.5946,
        location_name="Bengaluru",
        timestamp=datetime(2026, 9, 21, 10, 30),
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


@pytest.fixture
def mock_analyzer():
    mock_analysis = DisasterAnalysis(
        disaster_type="flood",
        disaster_type_confidence=0.92,
        severity_indicators=["water rising rapidly", "vehicles stuck"],
        location_mentions=["city center"],
        damage_observed=["vehicles submerged"],
        summary="Test flood analysis",
        evidence_description="Multimodal analysis (text): Text analysis"
    )

    with patch("ai.services.multimodal_analyzer.EventAnalyzer.analyze_event") as mock:
        mock.return_value = mock_analysis
        yield mock


class TestAnalyzeEventAPI:
    @pytest.mark.asyncio
    async def test_analyze_event_success(self, client, sample_event, mock_analyzer):
        response = await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["event_id"] == str(sample_event.id)
        assert data["analysis"]["disaster_type"] == "flood"
        assert data["analysis"]["disaster_type_confidence"] == 0.92
        assert "water rising rapidly" in data["analysis"]["severity_indicators"]
        mock_analyzer.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_event_with_override_content(self, client, sample_event, mock_analyzer):
        response = await client.post(
            f"/api/v1/events/{sample_event.id}/analyze",
            json={"text": "Override text", "image_path": "/custom/image.jpg"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["analysis"]["disaster_type"] == "flood"

    @pytest.mark.asyncio
    async def test_analyze_nonexistent_event(self, client, mock_analyzer):
        fake_id = uuid4()
        response = await client.post(f"/api/v1/events/{fake_id}/analyze", json={})
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_analyze_event_no_content(self, client, db_session, mock_analyzer):
        event = Event(
            source="test",
            latitude=12.9716,
            longitude=77.5946,
            timestamp=datetime(2026, 9, 21, 10, 30),
        )
        db_session.add(event)
        db_session.commit()
        db_session.refresh(event)

        response = await client.post(f"/api/v1/events/{event.id}/analyze", json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "no analyzable content" in response.json()["detail"].lower()


class TestGetEventAnalysisAPI:
    @pytest.mark.asyncio
    async def test_get_analysis_success(self, client, sample_event, db_session, mock_analyzer):
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})

        response = await client.get(f"/api/v1/events/{sample_event.id}/analysis")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["event_id"] == str(sample_event.id)
        assert data["analysis"]["disaster_type"] == "flood"

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, client, sample_event):
        response = await client.get(f"/api/v1/events/{sample_event.id}/analysis")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "no analysis found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_analysis_nonexistent_event(self, client):
        fake_id = uuid4()
        response = await client.get(f"/api/v1/events/{fake_id}/analysis")
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestAnalysisPersistence:
    @pytest.mark.asyncio
    async def test_analysis_stored_in_database(self, client, sample_event, db_session, mock_analyzer):
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})

        result = await db_session.execute(
            select(EventAIAnalysis).where(EventAIAnalysis.event_id == sample_event.id)
        )
        analysis = result.scalar_one_or_none()
        assert analysis is not None
        assert analysis.event_id == sample_event.id
        assert analysis.disaster_type == "flood"
        assert analysis.disaster_type_confidence == 0.92
        assert analysis.modality == "text"

    @pytest.mark.asyncio
    async def test_multiple_analyses_stored(self, client, sample_event, db_session, mock_analyzer):
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})

        result = await db_session.execute(
            select(EventAIAnalysis).where(EventAIAnalysis.event_id == sample_event.id)
        )
        analyses = list(result.scalars().all())
        assert len(analyses) == 2

    @pytest.mark.asyncio
    async def test_get_latest_analysis(self, client, sample_event, db_session, mock_analyzer):
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})
        await client.post(f"/api/v1/events/{sample_event.id}/analyze", json={})

        response = await client.get(f"/api/v1/events/{sample_event.id}/analysis")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["analysis"]["disaster_type"] == "flood"