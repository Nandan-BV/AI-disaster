import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import UUID, uuid4
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_SetSRID, ST_MakePoint

from app.models.resource import Resource, ResourceType, ResourceStatus
from app.models.incident import Incident
from app.models.infrastructure import InfrastructureType, InfrastructureStatus
from app.services.resource_service import (
    ResourceService,
    NearbyResource,
    ResourceCountSummary,
)
<<<<<<< HEAD
from app.services.geospatial_service import GeospatialService, NearbyInfrastructure
from app.schemas.resource import ResourceCreate, ResourceResponse, ResourceStatusUpdate
=======
from app.schemas.resource import ResourceCreate, ResourceResponse
from app.schemas.resource import ResourceStatusUpdate


@pytest.fixture
async def client():
    from httpx import ASGITransport, AsyncClient
    from app.database import get_db
    from app.main import app

    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db.execute.return_value = count_result

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
>>>>>>> origin/main


# Mock data
MOCK_RESOURCE_ID = uuid4()
MOCK_INCIDENT_ID = uuid4()


def create_mock_resource():
    resource = MagicMock(spec=Resource)
    resource.id = MOCK_RESOURCE_ID
    resource.name = "Test Hospital"
    resource.resource_type = ResourceType.HOSPITAL
    resource.status = ResourceStatus.AVAILABLE
    resource.latitude = 12.9716
    resource.longitude = 77.5946
    resource.address = "Test Address"
    resource.capacity = 300
    resource.current_load = 150
    resource.capabilities = {"emergency": True, "icu": True}
    resource.organization = "Test Health Dept"
    resource.metadata = {"bed_count": 300}
    resource.created_at = datetime(2026, 9, 21, 10, 30)
    resource.updated_at = datetime(2026, 9, 21, 11, 0)
    return resource


def create_mock_incident():
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


# Shared fixtures (module scope so every test class can use them).
@pytest.fixture
def mock_resource():
    return create_mock_resource()


@pytest.fixture
def mock_incident():
    return create_mock_incident()


@pytest.fixture
def mock_db():
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    db.execute.return_value = count_result
    return db


@pytest.fixture
def mock_resource_service():
    with patch("app.api.resources.ResourceService") as mock:
        service_instance = MagicMock()
        # Endpoints `await` these service methods, so they must be async mocks.
        for name in (
            "create_resource",
            "list_resources",
            "get_resource_by_id",
            "update_resource",
            "delete_resource",
            "update_resource_status",
            "get_nearby_resources",
            "get_resources_for_incident",
            "get_resource_counts_by_type",
            "get_nearby_infrastructure",
            "get_resources_by_type",
        ):
            setattr(service_instance, name, AsyncMock())
        mock.return_value = service_instance
        yield service_instance


@pytest.fixture
async def client(mock_db):
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.database import get_db

    previous = app.dependency_overrides.get(get_db)

    async def _override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


class TestResourceService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def mock_resource(self):
        return create_mock_resource()

    @pytest.fixture
    def mock_incident(self):
        return create_mock_incident()

    @pytest.fixture
    def resource_service(self, mock_db):
        return ResourceService(mock_db)

    @pytest.mark.asyncio
    async def test_get_resource_by_id_success(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_resource
        mock_db.execute.return_value = mock_result

        resource = await resource_service.get_resource_by_id(MOCK_RESOURCE_ID)
        assert resource == mock_resource

    @pytest.mark.asyncio
    async def test_get_resource_by_id_not_found(self, resource_service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        resource = await resource_service.get_resource_by_id(uuid4())
        assert resource is None

    @pytest.mark.asyncio
    async def test_create_resource(self, resource_service, mock_db, mock_resource):
        resource_data = {
            'name': 'Test Hospital',
            'resource_type': ResourceType.HOSPITAL,
            'status': ResourceStatus.AVAILABLE,
            'latitude': 12.9716,
            'longitude': 77.5946,
            'address': 'Test Address',
            'capacity': 300,
            'current_load': 150,
            'capabilities': {"emergency": True, "icu": True},
            'organization': 'Test Health Dept',
            'metadata': {"bed_count": 300},
        }
        
        mock_db.add = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        
        resource = await resource_service.create_resource(resource_data)
        
        assert resource.name == "Test Hospital"
        assert resource.resource_type == ResourceType.HOSPITAL
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_resource(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_resource
        mock_db.execute.return_value = mock_result

        update_data = {'name': 'Updated Hospital', 'capacity': 350}
        
        updated_resource = await resource_service.update_resource(MOCK_RESOURCE_ID, update_data)
        
        assert updated_resource.name == "Updated Hospital"
        assert updated_resource.capacity == 350
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_resource_not_found(self, resource_service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        updated_resource = await resource_service.update_resource(uuid4(), {'name': 'New Name'})
        assert updated_resource is None

    @pytest.mark.asyncio
    async def test_update_resource_status(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_resource
        mock_db.execute.return_value = mock_result

        updated_resource = await resource_service.update_resource_status(MOCK_RESOURCE_ID, "deployed")

        assert updated_resource.status == "deployed"
        assert updated_resource.updated_at is not None
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_resource(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_resource
        mock_db.execute.return_value = mock_result

        result = await resource_service.delete_resource(MOCK_RESOURCE_ID)
        
        assert result is True
        mock_db.delete.assert_called_once_with(mock_resource)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_resource_not_found(self, resource_service, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await resource_service.delete_resource(uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_list_resources(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_resource]
        mock_db.execute.return_value = mock_result

        resources = await resource_service.list_resources(limit=10, offset=0)
        
        assert len(resources) == 1
        assert resources[0] == mock_resource

    @pytest.mark.asyncio
    async def test_list_resources_with_filters(self, resource_service, mock_db, mock_resource):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_resource]
        mock_db.execute.return_value = mock_result

        resources = await resource_service.list_resources(
            resource_type="hospital",
            status="available",
            organization="Test",
            limit=10,
            offset=0,
        )
        
        assert len(resources) == 1
        assert resources[0] == mock_resource


class TestResourceGeospatial:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def mock_resource(self):
        return create_mock_resource()

    @pytest.fixture
    def resource_service(self, mock_db):
        return ResourceService(mock_db)

    @pytest.mark.asyncio
<<<<<<< HEAD
    async def test_get_nearby_resources_no_location(self, resource_service, mock_db):
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result

=======
    async def test_get_nearby_resources_no_location(self, resource_service):
        result = MagicMock()
        result.first.return_value = None
        resource_service.db.execute.return_value = result
>>>>>>> origin/main
        with pytest.raises(ValueError, match="has no valid coordinates"):
            await resource_service.get_resources_for_incident(uuid4())

    @pytest.mark.asyncio
    async def test_get_nearby_resources_success(self, resource_service, mock_db, mock_resource):
        mock_row = MagicMock()
        mock_row.id = mock_resource.id
        mock_row.name = mock_resource.name
        mock_row.resource_type = mock_resource.resource_type
        mock_row.status = mock_resource.status
        mock_row.latitude = mock_resource.latitude
        mock_row.longitude = mock_resource.longitude
        mock_row.address = mock_resource.address
<<<<<<< HEAD
        mock_row.capacity = mock_resource.capacity
        mock_row.current_load = mock_resource.current_load
        mock_row.capabilities = mock_resource.capabilities
        mock_row.organization = mock_resource.organization
        mock_row.metadata = mock_resource.metadata
=======
>>>>>>> origin/main
        mock_row.distance_meters = 250.5

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        nearby = await resource_service.get_nearby_resources(
            latitude=12.9716,
<<<<<<< HEAD
            longitude=77.5946,
=======
            longitude=77.5946
>>>>>>> origin/main
        )

        assert len(nearby) == 1
        assert nearby[0]['id'] == MOCK_RESOURCE_ID
        assert nearby[0]['name'] == "Test Hospital"
        assert nearby[0]['distance_meters'] == 250.5

    @pytest.mark.asyncio
    async def test_get_nearby_resources_with_filters(self, resource_service, mock_db):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        nearby = await resource_service.get_nearby_resources(
            latitude=12.9716,
            longitude=77.5946,
            radius_meters=500,
            resource_type="hospital",
            status="available",
            limit=100,
        )

        assert nearby == []

    @pytest.mark.asyncio
    async def test_get_resources_by_type(self, resource_service, mock_db, mock_resource):
        mock_row = MagicMock()
        mock_row.id = mock_resource.id
        mock_row.name = mock_resource.name
        mock_row.resource_type = mock_resource.resource_type
        mock_row.status = mock_resource.status
        mock_row.latitude = mock_resource.latitude
        mock_row.longitude = mock_resource.longitude
        mock_row.address = mock_resource.address
<<<<<<< HEAD
        mock_row.capacity = mock_resource.capacity
        mock_row.current_load = mock_resource.current_load
        mock_row.capabilities = mock_resource.capabilities
        mock_row.organization = mock_resource.organization
        mock_row.metadata = mock_resource.metadata
=======
>>>>>>> origin/main
        mock_row.distance_meters = 200

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        nearby = await resource_service.get_resources_by_type(
            latitude=12.9716,
            longitude=77.5946,
            resource_type="hospital",
            radius_meters=500,
        )

        assert len(nearby) == 1
        assert nearby[0]['resource_type'] == 'hospital'

    @pytest.mark.asyncio
    async def test_get_resource_counts_by_type(self, resource_service, mock_db):
        mock_row1 = MagicMock()
        mock_row1.resource_type = ResourceType.HOSPITAL
        mock_row1.count = 2
        
        mock_row2 = MagicMock()
        mock_row2.resource_type = ResourceType.SHELTER
        mock_row2.count = 1

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row1, mock_row2]
        mock_db.execute.return_value = mock_result

        counts = await resource_service.get_resource_counts_by_type(
            latitude=12.9716,
            longitude=77.5946,
        )

        assert counts["hospital"] == 2
        assert counts["shelter"] == 1


class TestResourceAPI:
<<<<<<< HEAD
=======
    @pytest.fixture
    def mock_resource_service(self):
        with patch("app.api.resources.ResourceService") as mock:
            service_instance = MagicMock()
            for method_name in (
                "create_resource",
                "list_resources",
                "get_resource_by_id",
                "update_resource",
                "update_resource_status",
                "delete_resource",
                "get_nearby_resources",
                "get_resource_counts_by_type",
            ):
                setattr(service_instance, method_name, AsyncMock())
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def mock_resource(self):
        return create_mock_resource()

>>>>>>> origin/main
    @pytest.mark.asyncio
    async def test_create_resource(self, client, mock_resource_service):
        mock_resource = create_mock_resource()
        mock_resource.name = "New Hospital"
        mock_resource.capacity = 250
        mock_resource_service.create_resource.return_value = mock_resource

        payload = {
            "name": "New Hospital",
            "resource_type": "hospital",
            "latitude": 12.9730,
            "longitude": 77.5960,
            "address": "New Address",
            "capacity": 250,
            "status": "available",
            "road_status": "open",
        }
        
        response = await client.post("/api/v1/resources", json=payload)
        assert response.status_code == 201
        data = response.json()
        sent = mock_resource_service.create_resource.await_args.args[0]
        assert sent["name"] == "New Hospital"
        assert sent["resource_type"] == "hospital"
        assert sent["capacity"] == 250
        assert data["name"] == mock_resource.name
        assert data["resource_type"] == "hospital"
        assert data["capacity"] == mock_resource.capacity

    @pytest.mark.asyncio
    async def test_create_resource_invalid_coords(self, client):
        payload = {
            "name": "Invalid Hospital",
            "resource_type": "hospital",
            "latitude": 200,  # Invalid
            "longitude": 77.5960,
        }
        response = await client.post("/api/v1/resources", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_resource_capacity_exceeds(self, client):
        payload = {
            "name": "Hospital",
            "resource_type": "hospital",
            "latitude": 12.9730,
            "longitude": 77.5960,
            "capacity": 100,
            "current_load": 150,  # Exceeds capacity
        }
        response = await client.post("/api/v1/resources", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_resources(self, client, mock_resource_service, mock_resource):
        mock_resource_service.list_resources.return_value = [mock_resource]

        response = await client.get("/api/v1/resources")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["resources"], list)
<<<<<<< HEAD
        assert data["total"] >= 1
        assert len(data["resources"]) >= 1
=======
        assert len(data["resources"]) == 1
>>>>>>> origin/main

    @pytest.mark.asyncio
    async def test_list_resources_filter_type(self, client, mock_resource_service, mock_resource):
        mock_resource_service.list_resources.return_value = [mock_resource]

        response = await client.get("/api/v1/resources?resource_type=hospital")
        assert response.status_code == 200
        data = response.json()
        assert all(item["resource_type"] == "hospital" for item in data["resources"])

    @pytest.mark.asyncio
    async def test_list_resources_filter_status(self, client, mock_resource_service, mock_resource):
        mock_resource_service.list_resources.return_value = [mock_resource]

        response = await client.get("/api/v1/resources?status=available")
        assert response.status_code == 200
        data = response.json()
        assert all(item["status"] == "available" for item in data["resources"])

    @pytest.mark.asyncio
    async def test_get_resource(self, client, mock_resource_service, mock_resource):
        mock_resource_service.get_resource_by_id.return_value = mock_resource

        response = await client.get(f"/api/v1/resources/{mock_resource.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(mock_resource.id)

    @pytest.mark.asyncio
    async def test_get_resource_not_found(self, client, mock_resource_service):
        mock_resource_service.get_resource_by_id.return_value = None

        response = await client.get(f"/api/v1/resources/{uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_resource(self, client, mock_resource_service, mock_resource):
        mock_resource_service.update_resource.return_value = mock_resource

        response = await client.patch(f"/api/v1/resources/{mock_resource.id}", json={"name": "Updated"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_resource(self, client, mock_resource_service, mock_resource):
        mock_resource_service.delete_resource.return_value = True

        response = await client.delete(f"/api/v1/resources/{mock_resource.id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_resource_not_found(self, client, mock_resource_service):
        mock_resource_service.delete_resource.return_value = False

        response = await client.delete(f"/api/v1/resources/{uuid4()}")
        assert response.status_code == 404


class TestNearbyResourcesAPI:
<<<<<<< HEAD
    @pytest.mark.asyncio
    async def test_get_nearby_resources(self, client, mock_resource_service, mock_db, mock_incident):
        nearby = [
            NearbyResource(
                id=uuid4(),
                name="Nearby Hospital",
                resource_type="hospital",
                status="available",
                distance_meters=250.5,
                latitude=12.9720,
                longitude=77.5950,
                address="Test Address",
                capacity=300,
                current_load=100,
                capabilities={"icu": True},
                organization="Test Org",
            )
        ]
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_incident
        mock_resource_service.get_resources_for_incident.return_value = nearby

        response = await client.get(f"/api/v1/resources/incidents/{uuid4()}/nearby-resources")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["resources"][0]["name"] == "Nearby Hospital"
        assert data["resources"][0]["resource_type"] == "hospital"
        assert data["resources"][0]["current_load"] == 100
        mock_resource_service.get_resources_for_incident.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_nearby_resources_incident_not_found(self, client, mock_resource_service, mock_db):
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        response = await client.get(f"/api/v1/resources/incidents/{uuid4()}/nearby-resources")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_with_filters(self, client, mock_db, mock_incident):
        nearby = [
            NearbyInfrastructure(
                id=uuid4(),
                name="Test Hospital",
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
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_incident
        with patch("app.api.geospatial.GeospatialService") as mock_cls:
            mock_cls.return_value.get_nearby_infrastructure = AsyncMock(return_value=nearby)
            response = await client.get(
                f"/api/v1/incidents/{uuid4()}/infrastructure",
                params={
                    "infrastructure_type": "hospital",
                    "status": "operational",
                    "radius_meters": 500,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["infrastructure"][0]["infrastructure_type"] == "hospital"
        assert data["infrastructure"][0]["status"] == "operational"

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_invalid_status(self, client, mock_db, mock_incident):
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_incident

        response = await client.get(
            f"/api/v1/incidents/{uuid4()}/infrastructure",
            params={"status": "available"},
        )

        assert response.status_code == 422
=======
    @pytest.fixture
    def mock_resource_service(self):
        with patch("app.api.resources.ResourceService") as mock:
            service_instance = MagicMock()
            service_instance.get_nearby_resources = AsyncMock()
            mock.return_value = service_instance
            yield service_instance

    @pytest.fixture
    def mock_incident(self):
        incident = MagicMock()
        incident.id = uuid4()
        incident.centroid_latitude = 12.9716
        incident.centroid_longitude = 77.5946
        incident.title = "Test Incident"
        incident.incident_type = "flood"
        incident.status = "active"
        incident.event_count = 3
        incident.last_updated = datetime(2026, 9, 21, 11, 0)
        incident.created_at = datetime(2026, 9, 21, 10, 30)
        return incident

    @pytest.mark.asyncio
    async def test_get_nearby_resources(self, client, mock_resource_service, mock_incident):
        mock_resource_service.get_nearby_resources.return_value = [{
            "id": str(uuid4()),
            "name": "Nearby Hospital",
            "resource_type": "hospital",
            "status": "available",
            "distance_meters": 250.5,
            "latitude": 12.9720,
            "longitude": 77.5950,
            "capacity": 300,
            "address": "Test Address",
            "current_load": 0,
            "capabilities": {},
            "organization": "Test Health Dept",
        }]

        response = await client.get(
            "/api/v1/resources/nearby",
            params={"latitude": 12.9716, "longitude": 77.5946},
        )
        assert response.status_code == 200
        assert len(response.json()["resources"]) == 1

    @pytest.mark.asyncio
    async def test_get_nearby_infrastructure_with_filters(self, client, mock_resource_service, mock_incident):
        mock_resource_service.get_nearby_resources.return_value = []

        response = await client.get(
            "/api/v1/resources/nearby",
            params={
                "latitude": 12.9716,
                "longitude": 77.5946,
                "resource_type": "hospital",
                "status": "available",
                "radius_meters": 500,
            },
        )
        assert response.status_code == 200
        mock_resource_service.get_nearby_resources.assert_awaited_once()
>>>>>>> origin/main


class TestResourceValidation:
    def test_resource_create_valid(self):
        payload = {
            "name": "Test Hospital",
            "resource_type": "hospital",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "capacity": 100,
            "current_load": 50,
        }
        resource = ResourceCreate(**payload)
        assert resource.name == "Test Hospital"
        assert resource.resource_type == "hospital"
        assert resource.capacity == 100
        assert resource.current_load == 50

    def test_resource_create_invalid_latitude(self):
        payload = {
            "name": "Test",
            "resource_type": "hospital",
            "latitude": 200,  # Invalid
            "longitude": 77.5946,
        }
        with pytest.raises(ValueError):
            ResourceCreate(**payload)

    def test_resource_create_invalid_longitude(self):
        payload = {
            "name": "Test",
            "resource_type": "hospital",
            "latitude": 12.9716,
            "longitude": -200,  # Invalid
        }
        with pytest.raises(ValueError):
            ResourceCreate(**payload)

    def test_resource_create_invalid_type(self):
        payload = {
            "name": "Test",
            "resource_type": "invalid_type",
            "latitude": 12.9716,
            "longitude": 77.5946,
        }
        with pytest.raises(ValueError):
            ResourceCreate(**payload)

    def test_resource_create_missing_required(self):
        payload = {
            "resource_type": "hospital",
            # Missing name, latitude, longitude
        }
        with pytest.raises(ValueError):
            ResourceCreate(**payload)

    def test_resource_current_load_not_validated_at_schema_level(self):
        # Contract: ResourceCreate does NOT enforce current_load <= capacity.
        # That business rule is enforced at the API layer (HTTP 422), covered by
        # TestResourceAPI::test_create_resource_capacity_exceeds.
        payload = {
            "name": "Test",
            "resource_type": "hospital",
            "latitude": 12.9716,
            "longitude": 77.5946,
            "capacity": 100,
            "current_load": 150,  # Exceeds capacity
        }
        resource = ResourceCreate(**payload)
        assert resource.current_load == 150


class TestResourceStatusUpdate:
    def test_status_update_valid(self):
        payload = {"status": "deployed"}
        update = ResourceStatusUpdate(**payload)
        assert update.status == "deployed"

    def test_status_update_invalid(self):
        payload = {"status": "invalid_status"}
        with pytest.raises(ValueError):
            ResourceStatusUpdate(**payload)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])