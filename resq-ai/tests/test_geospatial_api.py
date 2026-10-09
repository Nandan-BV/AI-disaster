import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import status
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.main import app
from app.database import get_db, Base
from app.models.incident import Incident
from app.models.infrastructure import Infrastructure, InfrastructureType, InfrastructureStatus, RoadStatus, IncidentAnalysisArea


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
def sample_incident(db_session):
    incident = Incident(
        incident_type="flood",
        title="Test Flood Incident",
        centroid_latitude=12.9716,
        centroid_longitude=77.5946,
        start_time=datetime(2026, 9, 21, 10, 30),
        last_updated=datetime(2026, 9, 21, 11, 0),
        event_count=3,
        status="active",
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


@pytest.fixture
def sample_infrastructure(db_session):
    infra = Infrastructure(
        name="Test Hospital",
        infrastructure_type=InfrastructureType.HOSPITAL,
        latitude=12.9720,
        longitude=77.5950,
        location=ST_SetSRID(ST_MakePoint(77.5950, 12.9720), 4326),
        address="Test Address",
        capacity=300,
        status=InfrastructureStatus.OPERATIONAL,
        road_status=RoadStatus.OPEN,
    )
    db_session.add(infra)
    db_session.commit()
    db_session.refresh(infra)
    return infra


@pytest.fixture
def mock_geospatial_service():
    with patch("app.api.geospatial.GeospatialService") as mock:
        service_instance = MagicMock()
        mock.return_value = service_instance
        yield service_instance


class TestInfrastructureCRUD:
    @pytest.mark.asyncio
    async def test_create_infrastructure(self, client, db_session):
        payload = {
            "name": "New Hospital",
            "infrastructure_type": "hospital",
            "latitude": 12.9730,
            "longitude": 77.5960,
            "address": "New Address",
            "capacity": 250,
            "status": "operational",
            "road_status": "open",
        }
        response = await client.post("/api/v1/incidents/infrastructure", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "New Hospital"
        assert data["infrastructure_type"] == "hospital"
        assert data["capacity"] == 250

    @pytest.mark.asyncio
    async def test_create_infrastructure_invalid_coords(self, client):
        payload = {
            "name": "Invalid Hospital",
            "infrastructure_type": "hospital",
            "latitude": 200,  # Invalid
            "longitude": 77.5960,
        }
        response = await client.post("/api/v1/incidents/infrastructure", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_list_infrastructure(self, client, sample_infrastructure):
        response = await client.get("/api/v1/incidents/infrastructure")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_infrastructure_filter_type(self, client, sample_infrastructure):
        response = await client.get("/api/v1/incidents/infrastructure?type=hospital")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data:
            assert item["infrastructure_type"] == "hospital"

    @pytest.mark.asyncio
    async def test_list_infrastructure_filter_status(self, client, sample_infrastructure):
        response = await client.get("/api/v1/incidents/infrastructure?status=operational")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for item in data:
            assert item["status"] == "operational"

    @pytest.mark.asyncio
    async def test_get_infrastructure(self, client, sample_infrastructure):
        response = await client.get(f"/api/v1/incidents/infrastructure/{sample_infrastructure.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == str(sample_infrastructure.id)
        assert data["name"] == "Test Hospital"

    @pytest.mark.asyncio
    async def test_get_infrastructure_not_found(self, client):
        fake_id = uuid4()
        response = await client.get(f"/api/v1/incidents/infrastructure/{fake_id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_infrastructure(self, client, sample_infrastructure, db_session):
        response = await client.delete(f"/api/v1/incidents/infrastructure/{sample_infrastructure.id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify deleted
        result = await db_session.execute(
            select(Infrastructure).where(Infrastructure.id == sample_infrastructure.id)
        )
        assert result.scalar_one_or_none() is None


class TestIncidentGeospatialEndpoints:
    @pytest.mark.asyncio
    async def test_get_incident_location(self, client, sample_incident):
        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/location")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["incident_id"] == str(sample_incident.id)
        assert data["latitude"] == 12.9716
        assert data["longitude"] == 77.5946

    @pytest.mark.asyncio
    async def test_get_incident_location_not_found(self, client):
        fake_id = uuid4()
        response = await client.get(f"/api/v1/incidents/{fake_id}/location")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_incident_area_not_exists(self, client, sample_incident, mock_geospatial_service):
        mock_geospatial_service.get_analysis_area.return_value = None

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/area")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["incident_id"] == str(sample_incident.id)
        assert data["geometry"] is None

    @pytest.mark.asyncio
    async def test_create_incident_area(self, client, sample_incident, mock_geospatial_service):
        mock_area = MagicMock()
        mock_area.incident_id = sample_incident.id
        mock_area.radius_meters = 1500.0
        mock_area.geometry = None
        mock_area.created_at = datetime.utcnow()
        mock_geospatial_service.create_analysis_area.return_value = mock_area

        response = await client.post(f"/api/v1/incidents/{sample_incident.id}/area?radius_meters=1500")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["radius_meters"] == 1500.0

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure(self, client, sample_incident, mock_geospatial_service):
        mock_nearby = [
            MagicMock(
                id=uuid4(),
                name="Nearby Hospital",
                infrastructure_type=InfrastructureType.HOSPITAL,
                distance_meters=250.5,
                latitude=12.9720,
                longitude=77.5950,
                status=InfrastructureStatus.OPERATIONAL,
                capacity=300,
                address="Test Address",
                road_status=None,
                metadata={},
            )
        ]
        mock_geospatial_service.get_nearby_infrastructure.return_value = mock_nearby

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/infrastructure")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["infrastructure"]) == 1
        assert data["infrastructure"][0]["name"] == "Nearby Hospital"
        assert data["infrastructure"][0]["distance_meters"] == 250.5

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_with_filters(self, client, sample_incident, mock_geospatial_service):
        mock_geospatial_service.get_nearby_infrastructure.return_value = []

        response = await client.get(
            f"/api/v1/incidents/{sample_incident.id}/infrastructure",
            params={"type": "hospital", "status": "operational", "radius_meters": 500}
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    async def test_get_infrastructure_by_type(self, client, sample_incident, mock_geospatial_service):
        mock_nearby = [
            MagicMock(
                id=uuid4(),
                name="Hospital 1",
                infrastructure_type=InfrastructureType.HOSPITAL,
                distance_meters=200,
                latitude=12.9720,
                longitude=77.5950,
                status=InfrastructureStatus.OPERATIONAL,
                capacity=300,
                address=None,
                road_status=None,
                metadata={},
            )
        ]
        mock_geospatial_service.get_nearby_by_type.return_value = mock_nearby

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/infrastructure/hospital")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["infrastructure"]) == 1

    @pytest.mark.asyncio
    async def test_get_affected_infrastructure(self, client, sample_incident, mock_geospatial_service):
        mock_affected = MagicMock()
        mock_affected.hospitals_nearby = []
        mock_affected.shelters_nearby = []
        mock_affected.fire_stations_nearby = []
        mock_affected.police_stations_nearby = []
        mock_affected.schools_nearby = []
        mock_affected.bridges_nearby = []
        mock_affected.roads_nearby = []
        mock_affected.emergency_centers_nearby = []
        mock_affected.power_stations_nearby = []
        mock_affected.water_facilities_nearby = []
        mock_affected.total_count = 0
        mock_geospatial_service.analyze_affected_infrastructure.return_value = mock_affected

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/affected")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 0

    @pytest.mark.asyncio
    async def test_get_map_data(self, client, sample_incident, mock_geospatial_service):
        mock_geospatial_service.get_incident_map_data.return_value = {
            "type": "FeatureCollection",
            "features": []
        }

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/map-data")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["type"] == "FeatureCollection"

    @pytest.mark.asyncio
    async def test_get_infrastructure_counts(self, client, sample_incident, mock_geospatial_service):
        mock_geospatial_service.get_infrastructure_count_by_type.return_value = {
            "hospital": 2,
            "shelter": 1,
        }

        response = await client.get(f"/api/v1/incidents/{sample_incident.id}/infrastructure-counts")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["counts"]["hospital"] == 2
        assert data["counts"]["shelter"] == 1


class TestInfrastructureValidation:
    @pytest.mark.asyncio
    async def test_create_infrastructure_invalid_type(self, client):
        payload = {
            "name": "Invalid Type",
            "infrastructure_type": "invalid_type",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        response = await client.post("/api/v1/incidents/infrastructure", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_infrastructure_invalid_type_filter(self, client, sample_incident):
        response = await client.get(
            f"/api/v1/incidents/{sample_incident.id}/infrastructure/invalid_type"
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_infrastructure_missing_required(self, client):
        payload = {
            "infrastructure_type": "hospital",
            # Missing name, latitude, longitude
        }
        response = await client.post("/api/v1/incidents/infrastructure", json=payload)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY