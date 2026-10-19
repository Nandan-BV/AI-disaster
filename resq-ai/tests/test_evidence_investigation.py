import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List

from ai.services.evidence_collector import (
    extract_text_evidence,
    extract_image_evidence,
    extract_video_evidence,
    extract_geographic_evidence,
    extract_temporal_evidence,
    extract_multimodal_consistency,
    extract_source_diversity,
    determine_text_role,
    calculate_text_quality,
    determine_visual_role,
    calculate_visual_quality,
    IncidentEvidenceCollection,
    CollectedEvidence,
)
from ai.services.evidence_investigator import fallback_investigation
from ai.schemas.analysis import DisasterAnalysis
from app.models.evidence import Evidence, EvidenceType, EvidenceRole, InvestigationAssessment


# Mock data
SAMPLE_AI_ANALYSIS = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.9,
    severity_indicators=["water rising rapidly", "vehicles stuck"],
    location_mentions=["MG Road", "city center"],
    damage_observed=["vehicles submerged", "road flooded"],
    people_affected="residents requesting rescue",
    vehicles_observed=["stuck vehicles"],
    infrastructure_damage=["main road flooded"],
    environmental_conditions=["heavy rain"],
    summary="Heavy flooding on main road near city center",
    evidence_description="Text analysis: Social media post describing flooding"
)

SAMPLE_AI_ANALYSIS_IMAGE = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.85,
    severity_indicators=["water covering road"],
    location_mentions=["street view"],
    damage_observed=["flooded street"],
    people_affected=None,
    vehicles_observed=["partially submerged cars"],
    infrastructure_damage=["road flooded"],
    environmental_conditions=["overcast"],
    summary="Street-level view showing flood water",
    evidence_description="Image analysis showing flooded street"
)

SAMPLE_AI_ANALYSIS_UNCERTAIN = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.4,
    severity_indicators=[],
    location_mentions=[],
    damage_observed=[],
    people_affected=None,
    vehicles_observed=[],
    infrastructure_damage=[],
    environmental_conditions=[],
    summary="Uncertain",
    evidence_description="Text analysis: Uncertain report"
)


def create_mock_event(text=None, source="social_media", disaster_type="flood", ai_analysis=None, location=(12.9716, 77.5946), timestamp=None):
    """Create a mock event for testing."""
    event = MagicMock()
    event.id = uuid4()
    event.text_content = text
    event.source = source
    event.event_type = disaster_type
    event.latitude = location[0]
    event.longitude = location[1]
    event.location_name = "MG Road, Bengaluru"
    event.timestamp = timestamp or datetime(2026, 9, 21, 10, 30)
    event.metadata = {}
    return event


def create_collected_evidence(event, ai_analysis=None):
    """Create CollectedEvidence for testing."""
    return CollectedEvidence(
        event_id=event.id,
        incident_id=uuid4(),
        event_text=event.text_content,
        event_source=event.source,
        event_timestamp=event.timestamp,
        event_location=(event.latitude, event.longitude),
        event_location_name=event.location_name,
        ai_analysis=ai_analysis,
        incident_event=None,
    )


class TestTextEvidenceExtraction:
    def test_extract_text_evidence_supporting(self):
        event = create_mock_event(text="Heavy flooding reported near MG Road, water covering the main road")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS)
        items = extract_text_evidence(collected)

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.TEXT
        assert items[0].evidence_role == EvidenceRole.SUPPORTING
        assert items[0].confidence > 0
        assert items[0].evidence_quality > 0

    def test_extract_text_evidence_uncertain(self):
        event = create_mock_event(text="Someone said there might be flooding near MG Road")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS)
        items = extract_text_evidence(collected)

        assert len(items) == 1
        assert items[0].evidence_role == EvidenceRole.UNCERTAIN

    def test_extract_text_evidence_contradicting(self):
        event = create_mock_event(text="The road is not flooded, conditions are normal")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS)
        items = extract_text_evidence(collected)

        assert len(items) == 1
        assert items[0].evidence_role == EvidenceRole.CONTRADICTING

    def test_extract_text_evidence_empty(self):
        event = create_mock_event(text="")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS)
        items = extract_text_evidence(collected)

        assert len(items) == 0

    def test_calculate_text_quality(self):
        # High quality: detailed, specific, high AI confidence
        quality = calculate_text_quality(
            "Heavy flooding has covered the main road near the city center on MG Road",
            SAMPLE_AI_ANALYSIS
        )
        assert quality > 0.5

        # Low quality: short, vague, low AI confidence
        quality = calculate_text_quality(
            "Flood",
            DisasterAnalysis(disaster_type="flood", disaster_type_confidence=0.3)
        )
        assert quality < 0.5


class TestImageVideoEvidenceExtraction:
    def test_extract_image_evidence_with_analysis(self):
        event = create_mock_event(text="Flood photo")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS_IMAGE)
        items = extract_image_evidence(collected)

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.IMAGE
        assert items[0].evidence_role == EvidenceRole.SUPPORTING
        assert items[0].confidence > 0

    def test_extract_image_evidence_no_analysis(self):
        event = create_mock_event(text="Photo")
        collected = create_collected_evidence(event, None)
        items = extract_image_evidence(collected)

        assert len(items) == 0

    def test_extract_video_evidence_with_analysis(self):
        event = create_mock_event(text="Flood video")
        collected = create_collected_evidence(event, SAMPLE_AI_ANALYSIS_IMAGE)
        items = extract_video_evidence(collected)

        # Will not extract because evidence_description says "Image analysis" not "video"
        assert len(items) == 0

    def test_determine_visual_role_high_confidence(self):
        role = determine_visual_role(SAMPLE_AI_ANALYSIS_IMAGE)
        assert role == EvidenceRole.SUPPORTING

    def test_determine_visual_role_low_confidence(self):
        role = determine_visual_role(SAMPLE_AI_ANALYSIS_UNCERTAIN)
        assert role == EvidenceRole.UNCERTAIN

    def test_calculate_visual_quality(self):
        quality = calculate_visual_quality(SAMPLE_AI_ANALYSIS_IMAGE)
        assert quality > 0.5

        quality = calculate_visual_quality(SAMPLE_AI_ANALYSIS_UNCERTAIN)
        assert quality == pytest.approx(0.62)


class TestGeographicTemporalConsistency:
    def test_extract_geographic_evidence_close(self):
        events = [
            create_collected_evidence(create_mock_event(location=(12.9716, 77.5946))),
            create_collected_evidence(create_mock_event(location=(12.9718, 77.5948))),
            create_collected_evidence(create_mock_event(location=(12.9715, 77.5945))),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
<<<<<<< HEAD
            geographic_bounds={
                "min_lat": 12.9715, "max_lat": 12.9718,
                "min_lon": 77.5945, "max_lon": 77.5948,
                "centroid_lat": 12.97163, "centroid_lon": 77.59463,
            },
=======
            total_events=len(events),
            geographic_bounds={"min_lat": 12.9715, "max_lat": 12.9718, "min_lon": 77.5945, "max_lon": 78.0},
>>>>>>> origin/main
        )
        items = extract_geographic_evidence(collection, incident_center=(12.9716, 77.5946))

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.GEOGRAPHIC
        assert items[0].evidence_role == EvidenceRole.SUPPORTING
        assert "avg distance" in items[0].description

    def test_extract_geographic_evidence_far(self):
        events = [
            create_collected_evidence(create_mock_event(location=(12.9716, 77.5946))),
            create_collected_evidence(create_mock_event(location=(13.5, 78.0))),  # Far away
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
<<<<<<< HEAD
            geographic_bounds={
                "min_lat": 12.9716, "max_lat": 13.5,
                "min_lon": 77.5946, "max_lon": 78.0,
                "centroid_lat": 13.2358, "centroid_lon": 77.7973,
            },
=======
            total_events=len(events),
            geographic_bounds={"min_lat": 12.9716, "max_lat": 13.5, "min_lon": 77.5946, "max_lon": 78.0},
>>>>>>> origin/main
        )
        items = extract_geographic_evidence(collection, incident_center=(12.9716, 77.5946))

        assert len(items) == 1
        assert items[0].evidence_role in [EvidenceRole.SUPPORTING, EvidenceRole.NEUTRAL]

    def test_extract_temporal_evidence_tight(self):
        base = datetime(2026, 9, 21, 10, 30)
        events = [
            create_collected_evidence(create_mock_event(timestamp=base)),
            create_collected_evidence(create_mock_event(timestamp=base + timedelta(minutes=15))),
            create_collected_evidence(create_mock_event(timestamp=base + timedelta(minutes=30))),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
            total_events=len(events),
            time_range=(base, base + timedelta(minutes=30)),
        )
        items = extract_temporal_evidence(collection)

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.TEMPORAL
        assert items[0].evidence_role == EvidenceRole.SUPPORTING

    def test_extract_temporal_evidence_wide(self):
        base = datetime(2026, 9, 15, 10, 30)
        events = [
            create_collected_evidence(create_mock_event(timestamp=base)),
            create_collected_evidence(create_mock_event(timestamp=base + timedelta(days=7))),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
            total_events=len(events),
            time_range=(base, base + timedelta(days=7)),
        )
        items = extract_temporal_evidence(collection)

        assert len(items) == 1
        assert items[0].evidence_role in [EvidenceRole.NEUTRAL, EvidenceRole.CONTRADICTING]

    def test_extract_temporal_evidence_single_event(self):
        base = datetime(2026, 9, 21, 10, 30)
        events = [create_collected_evidence(create_mock_event(timestamp=base))]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
            total_events=len(events),
            time_range=(base, base),
        )
        items = extract_temporal_evidence(collection)

        assert len(items) == 1
        assert items[0].evidence_role == EvidenceRole.NEUTRAL


class TestMultimodalSourceDiversity:
    def test_extract_multimodal_consistency_strong(self):
        ai_analysis1 = DisasterAnalysis(
            disaster_type="flood", disaster_type_confidence=0.9,
            evidence_description="Text and image analysis"
        )
        ai_analysis2 = DisasterAnalysis(
            disaster_type="flood", disaster_type_confidence=0.85,
            evidence_description="Video analysis"
        )
        events = [
            create_collected_evidence(create_mock_event(), ai_analysis1),
            create_collected_evidence(create_mock_event(), ai_analysis2),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
        )
        items = extract_multimodal_consistency(collection)

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.MULTIMODAL
        assert items[0].evidence_role == EvidenceRole.SUPPORTING

    def test_extract_multimodal_consistency_weak(self):
        ai_analysis1 = DisasterAnalysis(
            disaster_type="flood", disaster_type_confidence=0.9,
            evidence_description="Text analysis"
        )
        ai_analysis2 = DisasterAnalysis(
            disaster_type="wildfire", disaster_type_confidence=0.85,
            evidence_description="Image analysis"
        )
        events = [
            create_collected_evidence(create_mock_event(), ai_analysis1),
            create_collected_evidence(create_mock_event(), ai_analysis2),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
        )
        items = extract_multimodal_consistency(collection)

        assert len(items) == 1
        assert items[0].evidence_role in [EvidenceRole.NEUTRAL, EvidenceRole.CONTRADICTING]

    def test_extract_source_diversity_high(self):
        events = [
            create_collected_evidence(create_mock_event(source="social_media")),
            create_collected_evidence(create_mock_event(source="news")),
            create_collected_evidence(create_mock_event(source="satellite")),
            create_collected_evidence(create_mock_event(source="weather_service")),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
            unique_sources=["social_media", "news", "satellite", "weather_service"],
        )
        items = extract_source_diversity(collection)

        assert len(items) == 1
        assert items[0].evidence_type == EvidenceType.SOURCE_DIVERSITY
        assert items[0].evidence_role == EvidenceRole.SUPPORTING

    def test_extract_source_diversity_single(self):
        events = [
            create_collected_evidence(create_mock_event(source="social_media")),
            create_collected_evidence(create_mock_event(source="social_media")),
        ]
        collection = IncidentEvidenceCollection(
            incident_id=uuid4(),
            incident=MagicMock(),
            events=events,
            unique_sources=["social_media"],
        )
        items = extract_source_diversity(collection)

        assert len(items) == 1
        assert items[0].evidence_role == EvidenceRole.NEUTRAL


class TestFallbackInvestigation:
    def test_fallback_strongly_supported(self):
        supporting = [Evidence(
            incident_id=uuid4(),
            event_id=uuid4(),
            evidence_type=EvidenceType.TEXT,
            evidence_role=EvidenceRole.SUPPORTING,
            description="Test supporting",
            confidence=0.9,
            evidence_quality=0.8,
        ) for _ in range(4)]
        contradicting = []
        uncertain = []
        neutral = []

        result = fallback_investigation(
            supporting + contradicting + uncertain + neutral,
            source_diversity=0.8,
            geographic_consistency=0.9,
            temporal_consistency=0.9,
            multimodal_consistency=0.8,
        )

        assert result["assessment"] == "strongly_supported"
        assert result["evidence_confidence_score"] > 0.7

    def test_fallback_conflicting(self):
        supporting = [Evidence(
            incident_id=uuid4(), event_id=uuid4(),
            evidence_type=EvidenceType.TEXT, evidence_role=EvidenceRole.SUPPORTING,
            description="Test", confidence=0.7, evidence_quality=0.6,
        ) for _ in range(2)]
        contradicting = [Evidence(
            incident_id=uuid4(), event_id=uuid4(),
            evidence_type=EvidenceType.TEXT, evidence_role=EvidenceRole.CONTRADICTING,
            description="Contradicting", confidence=0.8, evidence_quality=0.8,
        ) for _ in range(2)]
        uncertain = []
        neutral = []

        result = fallback_investigation(
            supporting + contradicting + uncertain + neutral,
            source_diversity=0.5,
            geographic_consistency=0.5,
            temporal_consistency=0.5,
            multimodal_consistency=0.5,
        )

        assert result["assessment"] == "conflicting"

    def test_fallback_insufficient_evidence(self):
        result = fallback_investigation(
            [],  # No evidence
            source_diversity=0.2,
            geographic_consistency=0.2,
            temporal_consistency=0.2,
            multimodal_consistency=0.2,
        )

        assert result["assessment"] == "insufficient_evidence"
        assert result["evidence_confidence_score"] == 0.0

    def test_fallback_single_weak_item_is_insufficient(self):
        supporting = [Evidence(
            incident_id=uuid4(), event_id=uuid4(),
            evidence_type=EvidenceType.TEXT, evidence_role=EvidenceRole.SUPPORTING,
            description="Test", confidence=0.5, evidence_quality=0.4,
        )]
        result = fallback_investigation(
            supporting,
            source_diversity=0.3,
            geographic_consistency=0.3,
            temporal_consistency=0.3,
            multimodal_consistency=0.3,
        )

<<<<<<< HEAD
        # A single weak item cannot establish support: the deterministic rubric
        # falls through to insufficient_evidence (total_evidence <= 2).
        assert result["assessment"] == "insufficient_evidence"

    def test_fallback_inconclusive(self):
        neutral = [
            Evidence(
                incident_id=uuid4(), event_id=uuid4(),
                evidence_type=EvidenceType.TEXT, evidence_role=EvidenceRole.NEUTRAL,
                description="Test", confidence=0.3, evidence_quality=0.3,
            )
            for _ in range(3)
        ]
        result = fallback_investigation(
            neutral,
            source_diversity=0.3,
            geographic_consistency=0.3,
            temporal_consistency=0.3,
            multimodal_consistency=0.3,
        )

        assert result["assessment"] == "inconclusive"
=======
        assert result["assessment"] == "insufficient_evidence"
>>>>>>> origin/main


class TestEvidenceInvestigationAPI:
    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_investigate_incident_already_exists(self, mock_db):
        incident_id = uuid4()
        existing_inv = MagicMock()
        existing_inv.incident_id = incident_id
        existing_inv.assessment = InvestigationAssessment.MODERATELY_SUPPORTED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_inv
        mock_db.execute.return_value = mock_result

        from ai.services.evidence_investigator import get_incident_investigation
        result = await get_incident_investigation(incident_id, mock_db)

        assert result == existing_inv

    @pytest.mark.asyncio
    async def test_investigate_incident_not_found(self, mock_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from ai.services.evidence_investigator import get_incident_investigation
        result = await get_incident_investigation(uuid4(), mock_db)

        assert result is None