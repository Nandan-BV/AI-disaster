import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List

from app.services.risk_service import (
    get_risk_level,
    calculate_severity_component,
    calculate_evidence_component,
    calculate_population_component,
    calculate_infrastructure_component,
    calculate_environment_component,
    calculate_accessibility_component,
)
from app.models.incident import Incident, IncidentEvent
from app.models.event import Event
from app.models.event_analysis import EventAIAnalysis
from app.models.evidence import IncidentInvestigation
from app.models.incident import Incident
from app.models.risk import (
    PopulationZone, EnvironmentalConditions,
    RiskAssessment, ImpactAssessment, RiskAssessmentHistory,
    RiskLevel
)
from app.models.infrastructure import Infrastructure, InfrastructureType, InfrastructureStatus, RoadStatus
from app.config import settings


# Test data
MOCK_INCIDENT_ID = uuid4()
MOCK_EVENT_ID = uuid4()
MOCK_INFRASTRUCTURE_ID = uuid4()


def create_mock_incident():
    incident = MagicMock(spec=Incident)
    incident.id = MOCK_INCIDENT_ID
    incident.centroid_latitude = 12.9716
    incident.centroid_longitude = 77.5946
    incident.incident_type = "flood"
    incident.title = "Test Flood Incident"
    incident.status = "active"
    incident.event_count = 3
    incident.start_time = datetime(2026, 9, 21, 10, 30)
    incident.last_updated = datetime(2026, 9, 21, 11, 0)
    incident.confidence = 0.85
    incident.created_at = datetime(2026, 9, 21, 10, 30)
    incident.updated_at = datetime(2026, 9, 21, 11, 0)
    return incident


def create_mock_ai_analysis():
    analysis = MagicMock(spec=EventAIAnalysis)
    analysis.disaster_type = "flood"
    analysis.disaster_type_confidence = 0.92
    analysis.severity_indicators = ["water rising rapidly", "vehicles stuck", "rescue requested"]
    analysis.location_mentions = ["MG Road", "city center"]
    analysis.damage_observed = ["vehicles submerged", "road flooded"]
    analysis.people_affected = "residents requesting rescue"
    analysis.vehicles_observed = ["stuck vehicles"]
    analysis.infrastructure_damage = ["main road flooded"]
    analysis.environmental_conditions = ["heavy rain"]
    analysis.summary = "Heavy flooding on main road near city center"
    analysis.evidence_description = "Text analysis: Social media post describing flooding"
    return analysis


def create_mock_investigation():
    investigation = MagicMock(spec=IncidentInvestigation)
    investigation.evidence_confidence = 0.78
    investigation.supporting_evidence_count = 5
    investigation.contradicting_evidence_count = 1
    investigation.neutral_evidence_count = 2
    investigation.uncertain_evidence_count = 1
    investigation.source_diversity = 0.6
    investigation.geographic_consistency = 0.9
    investigation.temporal_consistency = 0.85
    investigation.multimodal_consistency = 0.7
    investigation.assessment = "moderately_supported"
    investigation.explanation = "Supporting evidence includes..."
    investigation.limitations = "Limited source diversity..."
    investigation.model_name = "Qwen/Qwen2.5-VL-3B-Instruct"
    investigation.investigated_at = datetime(2026, 9, 21, 12, 0)
    return investigation


def create_mock_event():
    event = MagicMock(spec=Event)
    event.id = MOCK_EVENT_ID
    event.text_content = "Heavy flooding reported near MG Road"
    event.source = "social_media"
    event.event_type = "flood"
    event.latitude = 12.9716
    event.longitude = 77.5946
    event.location_name = "MG Road, Bengaluru"
    event.timestamp = datetime(2026, 9, 21, 10, 30)
    return event


def create_mock_incident_event():
    event = MagicMock(spec=IncidentEvent)
    event.id = uuid4()
    event.incident_id = MOCK_INCIDENT_ID
    event.event_id = MOCK_EVENT_ID
    event.similarity_score = 0.9
    event.geographic_distance_meters = 100.0
    event.temporal_distance_minutes = 15.0
    event.disaster_type_match = {"event_type": "flood", "incident_type": "flood", "match": True}
    event.assignment_confidence = 0.9
    event.created_at = datetime(2026, 9, 21, 10, 30)
    return event


def create_mock_infrastructure():
    infra = MagicMock(spec=Infrastructure)
    infra.id = MOCK_INFRASTRUCTURE_ID
    infra.name = "Test Hospital"
    infra.infrastructure_type = InfrastructureType.HOSPITAL
    infra.latitude = 12.9720
    infra.longitude = 77.5950
    infra.status = InfrastructureStatus.OPERATIONAL
    infra.capacity = 300
    infra.address = "Test Address"
    infra.road_status = RoadStatus.OPEN
    infra.metadata = {"bed_count": 300}
    return infra


def create_mock_population_zone():
    zone = MagicMock(spec=PopulationZone)
    zone.id = uuid4()
    zone.name = "MG Road Central"
    zone.population = 12500
    zone.latitude = 12.9716
    zone.longitude = 77.5946
    zone.vulnerability_factor = 0.7
    zone.metadata = {}
    return zone


def create_mock_environmental_conditions():
    env = MagicMock(spec=EnvironmentalConditions)
    env.incident_id = uuid4()
    env.timestamp = datetime(2026, 9, 21, 10, 30)
    env.temperature = 28.5
    env.rainfall = 45.2
    env.wind_speed = 25
    env.humidity = 85
    env.water_level = 1.2
    env.visibility = 2.0
    env.weather_description = "Heavy rain with thunderstorms"
    env.metadata = {"source": "weather_station"}
    return env


class TestRiskLevel:
    def test_get_risk_level_low(self):
        assert get_risk_level(10) == RiskLevel.LOW
        assert get_risk_level(19) == RiskLevel.LOW

    def test_get_risk_level_moderate(self):
        assert get_risk_level(20) == RiskLevel.MODERATE
        assert get_risk_level(39) == RiskLevel.MODERATE

    def test_get_risk_level_elevated(self):
        assert get_risk_level(40) == RiskLevel.ELEVATED
        assert get_risk_level(59) == RiskLevel.ELEVATED

    def test_get_risk_level_high(self):
        assert get_risk_level(60) == RiskLevel.HIGH
        assert get_risk_level(79) == RiskLevel.HIGH

    def test_get_risk_level_critical(self):
        assert get_risk_level(80) == RiskLevel.CRITICAL
        assert get_risk_level(100) == RiskLevel.CRITICAL


class TestSeverityComponent:
    def test_calculate_severity_with_ai_analysis(self):
        incident = create_mock_incident()
        ai_analysis = create_mock_ai_analysis()
        events = [create_mock_event()]
        
        score, details = calculate_severity_component(incident, ai_analysis, events)
        
        assert score > 0
        assert score <= 100
        assert details["ai_analysis_available"] is True
        assert details["event_count"] == 1
        assert "water rising rapidly" in details["severity_indicators"]
        assert "vehicles submerged" in details["damage_reported"]
        assert details["people_affected"] == "residents requesting rescue"

    def test_calculate_severity_without_ai_analysis(self):
        incident = create_mock_incident()
        events = [create_mock_event()]
        
        score, details = calculate_severity_component(incident, None, events)
        
        assert score == 30.0
        assert details["ai_analysis_available"] is False
        assert "note" in details

    def test_calculate_severity_no_events(self):
        incident = create_mock_incident()
        ai_analysis = create_mock_ai_analysis()
        
        score, details = calculate_severity_component(incident, ai_analysis, [])
        
        assert score > 0
        assert details["event_count"] == 0


class TestEvidenceComponent:
    def test_calculate_evidence_with_investigation(self):
        incident_id = uuid4()
        investigation = create_mock_investigation()
        incident_events = [create_mock_incident_event()]
        
        score, details = calculate_evidence_component(incident_id, investigation, incident_events)
        
        assert score > 0
        assert score <= 100
        assert details["investigation_available"] is True
        assert details["evidence_confidence"] == 0.78
        assert details["supporting_evidence"] == 5
        assert details["contradicting_evidence"] == 1
        assert details["source_diversity"] == 0.6
        assert details["multimodal_consistency"] == 0.7

    def test_calculate_evidence_without_investigation(self):
        incident_id = uuid4()
        incident_events = [create_mock_incident_event()]
        
        score, details = calculate_evidence_component(incident_id, None, incident_events)
        
        assert score == 20.0
        assert details["investigation_available"] is False
        assert "note" in details


class TestPopulationComponent:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def mock_incident(self):
        incident = create_mock_incident()
        return incident

    @pytest.mark.asyncio
    async def test_calculate_population_no_coordinates(self, mock_db, mock_incident):
        mock_incident.centroid_latitude = None
        mock_incident.centroid_longitude = None
        
        score, details = await calculate_population_component(MOCK_INCIDENT_ID, mock_db, mock_incident)
        
        assert score == 0.0
        assert "note" in details

    @pytest.mark.asyncio
    async def test_calculate_population_with_zones(self, mock_db, mock_incident):
        mock_zone = create_mock_population_zone()
        mock_zone.distance_meters = 500
        
        mock_row = MagicMock()
        mock_row.id = mock_zone.id
        mock_row.name = mock_zone.name
        mock_row.population = mock_zone.population
        mock_row.vulnerability_factor = mock_zone.vulnerability_factor
        mock_row.latitude = mock_zone.latitude
        mock_row.longitude = mock_zone.longitude
        mock_row.distance_meters = 500

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        score, details = await calculate_population_component(uuid4(), mock_db, create_mock_incident())
        
        assert score > 0
        assert score <= 100
        assert details["population_potentially_exposed"] == 12500
        assert details["population_zones_count"] == 1
        assert len(details["zones_affected"]) == 1

    @pytest.mark.asyncio
    async def test_calculate_population_no_zones(self, mock_db):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        score, details = await calculate_population_component(uuid4(), mock_db, create_mock_incident())
        
        assert score == 0.0
        assert "note" in details


class TestInfrastructureComponent:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_calculate_infrastructure_no_coordinates(self, mock_db):
        incident = create_mock_incident()
        incident.centroid_latitude = None
        incident.centroid_longitude = None
        
        score, details = await calculate_infrastructure_component(uuid4(), mock_db, incident)
        
        assert score == 0.0
        assert "note" in details

    @pytest.mark.asyncio
    async def test_calculate_infrastructure_with_hospitals(self, mock_db):
        mock_hospital = create_mock_infrastructure()
        mock_hospital.infrastructure_type = InfrastructureType.HOSPITAL
        mock_hospital.distance_meters = 200
        
        mock_row = MagicMock()
        mock_row.id = mock_hospital.id
        mock_row.name = mock_hospital.name
        mock_row.infrastructure_type = mock_hospital.infrastructure_type
        mock_row.status = mock_hospital.status
        mock_row.capacity = mock_hospital.capacity
        mock_row.distance_meters = 200

        mock_result = MagicMock()
        mock_result.all.return_value = [mock_row]
        mock_db.execute.return_value = mock_result

        score, details = await calculate_infrastructure_component(uuid4(), mock_db, create_mock_incident())
        
        assert score > 0
        assert details["infrastructure_count"] == 1
        assert details["by_type"]["hospital"] == 1
        assert len(details["critical_infrastructure"]) == 1

    @pytest.mark.asyncio
    async def test_calculate_infrastructure_no_items(self, mock_db):
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute.return_value = mock_result

        score, details = await calculate_infrastructure_component(uuid4(), mock_db, create_mock_incident())
        
        assert score == 0.0
        assert "note" in details


class TestEnvironmentComponent:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_calculate_environment_with_conditions(self, mock_db):
        mock_env = create_mock_environmental_conditions()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_env
        mock_db.execute.return_value = mock_result

        score, details = await calculate_environment_component(uuid4(), mock_db, create_mock_incident())
        
        assert score > 0
        assert details["conditions_available"] is True
        assert details["rainfall_mm"] == 45.2
        assert details["wind_speed_kmh"] == 25

    @pytest.mark.asyncio
    async def test_calculate_environment_no_conditions(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        score, details = await calculate_environment_component(uuid4(), mock_db, create_mock_incident())
        
        assert score == 10.0
        assert details["conditions_available"] is False
        assert "note" in details

    @pytest.mark.asyncio
    async def test_calculate_environment_extreme_rainfall(self, mock_db):
        mock_env = create_mock_environmental_conditions()
        mock_env.rainfall = 65.8
        mock_env.wind_speed = 35
        mock_env.water_level = 2.5
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_env
        mock_db.execute.return_value = mock_result

        score, details = await calculate_environment_component(uuid4(), mock_db, create_mock_incident())
        
        assert score > 50  # Should be high due to extreme conditions


class TestAccessibilityComponent:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_calculate_accessibility_no_coordinates(self, mock_db):
        incident = create_mock_incident()
        incident.centroid_latitude = None
        incident.centroid_longitude = None
        
        score, details = await calculate_accessibility_component(uuid4(), mock_db, incident)
        
        assert score == 50.0
        assert "note" in details

    @pytest.mark.asyncio
    async def test_calculate_accessibility_open_roads(self, mock_db):
        incident = create_mock_incident()
        
        # Mock roads
        mock_road = MagicMock()
        mock_road.id = uuid4()
        mock_road.name = "Test Road"
        mock_road.road_status = RoadStatus.OPEN
        mock_road.distance_meters = 300
        
        mock_roads_result = MagicMock()
        mock_roads_result.all.return_value = [mock_road]
        
        # Mock bridges
        mock_bridges_result = MagicMock()
        mock_bridges_result.all.return_value = []
        
        # Mock db.execute to return different results for roads and bridges
        mock_db.execute.side_effect = [mock_roads_result, mock_bridges_result]

        score, details = await calculate_accessibility_component(uuid4(), mock_db, create_mock_incident())
        
        assert score > 50  # Good accessibility = lower risk
        assert details["open_roads"] == 1
        assert details["blocked_roads"] == 0

    @pytest.mark.asyncio
    async def test_calculate_accessibility_blocked_roads(self, mock_db):
        # Mock blocked roads
        mock_road = MagicMock()
        mock_road.id = uuid4()
        mock_road.name = "Blocked Road"
        mock_road.road_status = RoadStatus.BLOCKED
        mock_road.distance_meters = 200
        
        mock_roads_result = MagicMock()
        mock_roads_result.all.return_value = [mock_road]
        
        # Mock bridges
        mock_bridge = MagicMock()
        mock_bridge.id = uuid4()
        mock_bridge.name = "Blocked Bridge"
        mock_bridge.road_status = RoadStatus.BLOCKED
        mock_bridge.distance_meters = 100
        
        mock_bridges_result = MagicMock()
        mock_bridges_result.all.return_value = [mock_bridge]
        
        mock_db.execute.side_effect = [mock_roads_result, mock_bridges_result]

        score, details = await calculate_accessibility_component(uuid4(), mock_db, create_mock_incident())
        
        assert score < 30  # Poor accessibility = high risk
        assert details["blocked_roads"] == 1
        assert details["blocked_bridges"] == 1


class TestRiskLevelThresholds:
    def test_risk_level_thresholds(self):
        # Test that thresholds are properly configured
        assert settings.RISK_LEVEL_LOW_MAX == 19
        assert settings.RISK_LEVEL_MODERATE_MAX == 39
        assert settings.RISK_LEVEL_ELEVATED_MAX == 59
        assert settings.RISK_LEVEL_HIGH_MAX == 79

    def test_weights_sum_to_one(self):
        total = (
            settings.RISK_WEIGHT_SEVERITY +
            settings.RISK_WEIGHT_EVIDENCE +
            settings.RISK_WEIGHT_POPULATION +
            settings.RISK_WEIGHT_INFRASTRUCTURE +
            settings.RISK_WEIGHT_ENVIRONMENT +
            settings.RISK_WEIGHT_ACCESSIBILITY
        )
        assert abs(total - 1.0) < 0.001


class TestInfraWeights:
    def test_infra_weights_positive(self):
        assert settings.INFRA_WEIGHT_HOSPITAL > 0
        assert settings.INFRA_WEIGHT_SHELTER > 0
        assert settings.INFRA_WEIGHT_FIRE_STATION > 0
        assert settings.INFRA_WEIGHT_POLICE_STATION > 0
        assert settings.INFRA_WEIGHT_BRIDGE > 0
        assert settings.INFRA_WEIGHT_ROAD > 0
        assert settings.INFRA_WEIGHT_EMERGENCY_CENTER > 0
        assert settings.INFRA_WEIGHT_POWER_STATION > 0
        assert settings.INFRA_WEIGHT_WATER_FACILITY > 0
        assert settings.INFRA_WEIGHT_SCHOOL > 0