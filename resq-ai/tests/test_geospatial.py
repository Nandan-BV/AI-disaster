import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.models.infrastructure import (
    Infrastructure, InfrastructureType, InfrastructureStatus, RoadStatus, IncidentAnalysisArea
)
from app.models.incident import Incident
from app.services.geospatial_service import (
    GeospatialService,
    NearbyInfrastructure,
    AffectedInfrastructureSummary,
)


# Mock data
MOCK_INCIDENT_ID = uuid4()
MOCK_INFRASTRUCTURE_ID = uuid4()


class TestGeospatialService:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_incident(self):
        incident = MagicMock(spec=Incident)
        incident.id = MOCK_INCIDENT_ID
        incident.centroid_latitude = 12.9716
        incident.centroid_longitude = 77.5946
        incident.title = "Test Incident"
        incident.incident_type = "flood"
        incident.status = "active"
        incident.event_count = 3
        incident.start_time = datetime(2026, 9, 21, 10, 30)
        incident.last_updated = datetime(2026, 9, 21, 11, 0)
        return incident

    @pytest.fixture
    def mock_infrastructure(self):
        infra = MagicMock(spec=Infrastructure)
        infra.id = MOCK_INFRASTRUCTURE_ID
        infra.name = "Test Hospital"
        infra.infrastructure_type = InfrastructureType.HOSPITAL
        infra.latitude = 12.9720
        infra.longitude = 77.5950
        infra.status = InfrastructureStatus.OPERATIONAL
        infra.capacity = 300
        infra.address = "Test Address"
        infra.road_status = None
        infra.metadata = {"bed_count": 300}
        return infra

    @pytest.fixture
    def geospatial_service(self, mock_db):
        return GeospatialService(mock_db)

    @pytest.mark.asyncio
    async def test_get_incident_location_success(self, geospatial_service, mock_db, mock_incident):
        mock_result = MagicMock()
        mock_result.first.return_value = (12.9716, 77.5946)
        mock_db.execute.return_value = mock_result

        location = await geospatial_service.get_incident_location(MOCK_INCIDENT_ID)
        assert location == (12.9716, 77.5946)

    @pytest.mark.asyncio
    async def test_get_incident_location_not_found(self, geospatial_service, mock_db):
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result

        location = await geospatial_service.get_incident_location(uuid4())
        assert location is None

    @pytest.mark.asyncio
    async def test_create_analysis_area(self, geospatial_service, mock_db, mock_incident):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing area
        mock_db.execute.return_value = mock_result

        area = await geospatial_service.create_analysis_area(MOCK_INCIDENT_ID, 1500.0)

        assert area.incident_id == MOCK_INCIDENT_ID
        assert area.radius_meters == 1500.0
        assert area.geometry is not None

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_no_location(self, geospatial_service):
        with patch.object(geospatial_service, 'get_incident_location', return_value=None):
            with pytest.raises(ValueError, match="has no valid coordinates"):
                await geospatial_service.get_nearby_infrastructure(uuid4())

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_success(self, geospatial_service, mock_db, mock_incident, mock_infrastructure):
        with patch.object(geospatial_service, 'get_incident_location', return_value=(12.9716, 77.5946)):
            # Mock the query result
            mock_row = MagicMock()
            mock_row.id = mock_infrastructure.id
            mock_row.name = mock_infrastructure.name
            mock_row.infrastructure_type = mock_infrastructure.infrastructure_type
            mock_row.latitude = mock_infrastructure.latitude
            mock_row.longitude = mock_infrastructure.longitude
            mock_row.status = mock_infrastructure.status
            mock_row.capacity = mock_infrastructure.capacity
            mock_row.address = mock_infrastructure.address
            mock_row.road_status = mock_infrastructure.road_status
            mock_row.metadata = mock_infrastructure.metadata
            mock_row.distance_meters = 250.5

            mock_result = MagicMock()
            mock_result.all.return_value = [mock_row]
            mock_db.execute.return_value = mock_result

            nearby = await geospatial_service.get_nearby_infrastructure(MOCK_INCIDENT_ID)

            assert len(nearby) == 1
            assert nearby[0].id == MOCK_INFRASTRUCTURE_ID
            assert nearby[0].name == "Test Hospital"
            assert nearby[0].infrastructure_type == "hospital"
            assert nearby[0].distance_meters == 250.5
            assert nearby[0].status == "operational"

    @pytest.mark.asyncio
    async def test_analyze_affected_infrastructure(self, geospatial_service, mock_db, mock_incident):
        with patch.object(geospatial_service, 'get_nearby_infrastructure') as mock_get_nearby:
            # Create mock infrastructure of different types
            mock_hospital = MagicMock()
            mock_hospital.id = uuid4()
            mock_hospital.name = "Hospital"
            mock_hospital.infrastructure_type = InfrastructureType.HOSPITAL
            mock_hospital.latitude = 12.9720
            mock_hospital.longitude = 77.5950
            mock_hospital.status = InfrastructureStatus.OPERATIONAL
            mock_hospital.capacity = 300
            mock_hospital.address = "Test"
            mock_hospital.road_status = None
            mock_hospital.metadata = {}
            mock_hospital.distance_meters = 200

            mock_shelter = MagicMock()
            mock_shelter.id = uuid4()
            mock_shelter.name = "Shelter"
            mock_shelter.infrastructure_type = InfrastructureType.SHELTER
            mock_shelter.latitude = 12.9730
            mock_shelter.longitude = 77.5960
            mock_shelter.status = InfrastructureStatus.OPERATIONAL
            mock_shelter.capacity = 500
            mock_shelter.address = "Test"
            mock_shelter.road_status = None
            mock_shelter.metadata = {}
            mock_shelter.distance_meters = 300

            mock_get_nearby.return_value = [mock_hospital, mock_shelter]

            affected = await geospatial_service.analyze_affected_infrastructure(MOCK_INCIDENT_ID)

            assert affected.total_count == 2
            assert len(affected.hospitals_nearby) == 1
            assert len(affected.shelters_nearby) == 1
            assert len(affected.fire_stations_nearby) == 0
            assert affected.hospitals_nearby[0].name == "Hospital"
            assert affected.shelters_nearby[0].name == "Shelter"

    @pytest.mark.asyncio
    async def test_get_infrastructure_count_by_type(self, geospatial_service, mock_db, mock_incident):
        with patch.object(geospatial_service, 'get_nearby_infrastructure') as mock_get_nearby:
            mock_hospital = MagicMock()
            mock_hospital.infrastructure_type = InfrastructureType.HOSPITAL
            mock_hospital.distance_meters = 200

            mock_shelter = MagicMock()
            mock_shelter.infrastructure_type = InfrastructureType.SHELTER
            mock_shelter.distance_meters = 300

            mock_get_nearby.return_value = [mock_hospital, mock_shelter, mock_shelter]

            counts = await geospatial_service.get_infrastructure_count_by_type(MOCK_INCIDENT_ID)

            assert counts["hospital"] == 1
            assert counts["shelter"] == 2


class TestIncidentAnalysisArea:
    def test_incident_analysis_area_creation(self):
        area = IncidentAnalysisArea(
            incident_id=uuid4(),
            geometry=WKTElement('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', srid=4326),
            radius_meters=1000.0,
        )
        assert area.radius_meters == 1000.0

    def test_incident_repr(self):
        area = IncidentAnalysisArea(
            incident_id=MOCK_INCIDENT_ID,
            geometry=WKTElement('POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))', srid=4326),
            radius_meters=1000.0,
        )
        repr_str = repr(area)
        assert str(MOCK_INCIDENT_ID) in repr_str
        assert "1000.0m" in repr_str


class TestInfrastructure:
    def test_infrastructure_creation(self):
        infra = Infrastructure(
            name="Test Hospital",
            infrastructure_type=InfrastructureType.HOSPITAL,
            latitude=12.9716,
            longitude=77.5946,
            location=ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
            capacity=300,
            status=InfrastructureStatus.OPERATIONAL,
        )
        assert infra.name == "Test Hospital"
        assert infra.infrastructure_type == InfrastructureType.HOSPITAL
        assert infra.status == InfrastructureStatus.OPERATIONAL
        assert infra.capacity == 300

    def test_infrastructure_repr(self):
        infra = Infrastructure(
            name="Test Hospital",
            infrastructure_type=InfrastructureType.HOSPITAL,
            latitude=12.9716,
            longitude=77.5946,
            location=ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326),
        )
        repr_str = repr(infra)
        assert "Test Hospital" in repr_str
        assert "hospital" in repr_str.lower()


class TestInfrastructureEnums:
    def test_infrastructure_type_values(self):
        assert InfrastructureType.HOSPITAL == "hospital"
        assert InfrastructureType.SHELTER == "shelter"
        assert InfrastructureType.FIRE_STATION == "fire_station"
        assert InfrastructureType.POLICE_STATION == "police_station"
        assert InfrastructureType.BRIDGE == "bridge"
        assert InfrastructureType.ROAD == "road"
        assert InfrastructureType.EMERGENCY_CENTER == "emergency_center"

    def test_infrastructure_status_values(self):
        assert InfrastructureStatus.OPERATIONAL == "operational"
        assert InfrastructureStatus.PARTIALLY_OPERATIONAL == "partially_operational"
        assert InfrastructureStatus.UNAVAILABLE == "unavailable"
        assert InfrastructureStatus.UNKNOWN == "unknown"

    def test_road_status_values(self):
        assert RoadStatus.OPEN == "open"
        assert RoadStatus.PARTIALLY_BLOCKED == "partially_blocked"
        assert RoadStatus.BLOCKED == "blocked"
        assert RoadStatus.UNKNOWN == "unknown"