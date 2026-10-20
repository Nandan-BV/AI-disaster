import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.incident import IncidentStatus
from app.services.geospatial_service import GeospatialService


@pytest.mark.asyncio
async def test_map_data_parses_geojson_and_keeps_zero_coordinates():
    incident_id = uuid4()
    incident = SimpleNamespace(
        id=incident_id,
        centroid_latitude=0,
        centroid_longitude=0,
        title="Equatorial incident",
        incident_type="flood",
        status=IncidentStatus.ACTIVE,
        event_count=1,
    )
    analysis_area = SimpleNamespace(geometry=object(), radius_meters=1000)

    incident_result = MagicMock()
    incident_result.scalar_one_or_none.return_value = incident
    area_result = MagicMock()
    area_result.scalar.return_value = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        }
    )
    db = AsyncMock()
    db.execute.side_effect = [incident_result, area_result]

    service = GeospatialService(db)
    service.get_analysis_area = AsyncMock(return_value=analysis_area)
    service.get_nearby_infrastructure = AsyncMock(return_value=[])

    result = await service.get_incident_map_data(incident_id)

    incident_feature, area_feature = result["features"]
    assert incident_feature["geometry"]["coordinates"] == [0, 0]
    assert isinstance(area_feature["geometry"], dict)
    assert area_feature["geometry"]["type"] == "Polygon"
