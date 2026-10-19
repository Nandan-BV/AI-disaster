import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List
import numpy as np

from ai.config import ai_config
from ai.services.embedding_service import (
    build_event_text_representation,
    generate_event_embedding,
    generate_embeddings_batch,
    cosine_similarity,
)
from ai.services.similarity_service import (
    calculate_geographic_distance,
    calculate_temporal_distance,
    calculate_disaster_type_score,
    calculate_geographic_score,
    calculate_temporal_score,
    calculate_relationship_score,
    RelationshipScore,
    SimilarityComponents,
    haversine_distance,
)
from ai.services.clustering_service import (
    build_incident_title,
    calculate_centroid,
    create_new_incident,
    add_event_to_incident,
    find_best_matching_incident,
    process_new_event,
)
from ai.models.embedding_base import BaseEmbeddingModel
from ai.schemas.analysis import DisasterAnalysis


# Mock embedding model for testing
class MockEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, embeddings_map=None):
        self._loaded = True
        self._embeddings_map = embeddings_map or {}
        self._default_embedding = np.random.rand(384).astype(np.float32)

    @property
    def model_name(self) -> str:
        return "test-embedding-model"

    @property
    def embedding_dim(self) -> int:
        return 384

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def encode(self, texts: List[str]) -> np.ndarray:
        embeddings = []
        for text in texts:
            if text in self._embeddings_map:
                embeddings.append(self._embeddings_map[text])
            else:
                embeddings.append(self._default_embedding)
        return np.array(embeddings)

    def encode_single(self, text: str) -> np.ndarray:
        if text in self._embeddings_map:
            return self._embeddings_map[text]
        return self._default_embedding


# Test data
SIMILAR_TEXTS = [
    "Heavy flooding reported near MG Road, water covering the main road",
    "Water has covered MG Road near the city center, vehicles stuck",
    "Vehicles are trapped due to flooding near MG Road, rescue requested",
]

DIFFERENT_TEXTS = [
    "Heavy flooding reported near MG Road",
    "Wildfire detected near Bannerghatta forest area",
]


class TestEmbeddingService:
    @pytest.fixture
    def mock_embedding_manager(self):
        mock_model = MockEmbeddingModel()
        with patch("ai.services.embedding_service.embedding_manager") as mock:
            mock.load_model.return_value = mock_model
            mock.get_model.return_value = mock_model
            yield mock

    def test_build_event_text_representation(self):
        result = build_event_text_representation(
            event_text="Flooding near city center",
            disaster_type="flood",
            ai_summary="Heavy flooding on main road",
            location_mentions=["city center", "main road"],
            damage_observed=["vehicles submerged"],
        )
        assert "Flooding near city center" in result
        assert "Disaster type: flood" in result
        assert "Heavy flooding on main road" in result
        assert "city center, main road" in result
        assert "vehicles submerged" in result

    def test_build_event_text_representation_empty(self):
        result = build_event_text_representation()
        assert result == "No event information"

    def test_generate_event_embedding(self, mock_embedding_manager):
        result = generate_event_embedding(
            event_text="Flooding near city center",
            disaster_type="flood",
        )
        assert result is not None
        assert len(result) == 384

    def test_generate_event_embedding_empty(self, mock_embedding_manager):
        result = generate_event_embedding()
        assert result is None

    def test_generate_embeddings_batch(self, mock_embedding_manager):
        results = generate_embeddings_batch(SIMILAR_TEXTS)
        assert len(results) == 3
        assert all(len(r) == 384 for r in results)

    def test_cosine_similarity_identical(self):
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == 1.0

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == 0.0

    def test_cosine_similarity_opposite(self):
        a = [1.0, 0.0, 0.0]
        b = [-1.0, 0.0, 0.0]
        sim = cosine_similarity(a, b)
        assert sim == -1.0


class TestSimilarityService:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.mark.asyncio
    async def test_calculate_geographic_distance(self, mock_db):
<<<<<<< HEAD
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1000.0
        mock_db.execute.return_value = mock_result
=======
        result = MagicMock()
        result.scalar.return_value = 1000.0
        mock_db.execute.return_value = result
>>>>>>> origin/main
        distance = await calculate_geographic_distance(
            12.9716, 77.5946, 12.9718, 77.5948, mock_db
        )
        assert distance == 1000.0

    def test_haversine_distance(self):
        # Distance between two close points (~31 m apart at this latitude)
        dist = haversine_distance(12.9716, 77.5946, 12.9718, 77.5948)
<<<<<<< HEAD
        assert 30 < dist < 32
=======
        assert 20 < dist < 40  # ~31 meters
>>>>>>> origin/main

    def test_calculate_temporal_distance(self):
        ts1 = datetime(2026, 9, 21, 10, 30)
        ts2 = datetime(2026, 9, 21, 11, 00)
        diff = calculate_temporal_distance(ts1, ts2)
        assert diff == 30.0

    def test_calculate_disaster_type_score_exact_match(self):
        match, score = calculate_disaster_type_score("flood", "flood")
        assert match is True
        assert score == 1.0

    def test_calculate_disaster_type_score_compatible(self):
        match, score = calculate_disaster_type_score("flood", "flash_flood")
        assert match is True
        assert score == 0.8

    def test_calculate_disaster_type_score_incompatible(self):
        match, score = calculate_disaster_type_score("flood", "wildfire")
        assert match is False
        assert score == 0.0

    def test_calculate_geographic_score(self):
        # Within threshold
        score = calculate_geographic_score(500)  # 500m
        assert score > 0.5

        # At threshold
        score = calculate_geographic_score(2000)  # 2000m (max)
        assert score == 0.0

        # Beyond threshold
        score = calculate_geographic_score(5000)
        assert score == 0.0

    def test_calculate_temporal_score(self):
        # Within threshold
        score = calculate_temporal_score(30)  # 30 min
        assert score > 0.5

        # At threshold
        score = calculate_temporal_score(120)  # 120 min (max)
        assert score == 0.0

    def test_calculate_relationship_score_high_match(self):
        result = calculate_relationship_score(
            semantic_similarity=0.95,
            geographic_distance_meters=100,
            temporal_distance_minutes=5,
            disaster_type_match=True,
            disaster_type_score=1.0,
        )
        assert result.overall_score > 0.8
        assert "Semantic similarity: 0.95" in result.explanation

    def test_calculate_relationship_score_low_match(self):
        result = calculate_relationship_score(
            semantic_similarity=0.30,
            geographic_distance_meters=5000,
            temporal_distance_minutes=500,
            disaster_type_match=False,
            disaster_type_score=0.0,
        )
        assert result.overall_score < 0.3


class TestClusteringService:
    def test_build_incident_title(self):
        title = build_incident_title("flood", "MG Road", 1)
        assert "flood" in title.lower()
        assert "MG Road" in title
        assert "1 report" in title

        title = build_incident_title("flood", "MG Road", 5)
        assert "5 reports" in title

        title = build_incident_title(None, None, 1)
        assert "incident" in title.lower()

    def test_calculate_centroid(self):
        class MockEvent:
            def __init__(self, lat, lon):
                self.latitude = lat
                self.longitude = lon

        events = [
            MockEvent(12.97, 77.59),
            MockEvent(12.98, 77.60),
            MockEvent(12.99, 77.61),
        ]
        lat, lon = calculate_centroid(events)
        assert abs(lat - 12.98) < 0.01
        assert abs(lon - 77.60) < 0.01

    def test_calculate_centroid_empty(self):
        lat, lon = calculate_centroid([])
        assert lat is None
        assert lon is None


# Need to import haversine for the test
from ai.services.similarity_service import haversine_distance


class TestIncidentEventRelationship:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        return db

    @pytest.fixture
    def sample_event(self):
        class MockEvent:
            def __init__(self):
                self.id = uuid4()
                self.text_content = "Flooding near MG Road"
                self.event_type = "flood"
                self.latitude = 12.9716
                self.longitude = 77.5946
                self.location_name = "MG Road, Bengaluru"
                self.timestamp = datetime(2026, 9, 21, 10, 30)
                self.metadata = {}

        return MockEvent()

    @pytest.fixture
    def sample_incident(self):
        class MockIncident:
            def __init__(self):
                self.id = uuid4()
                self.incident_type = "flood"
                self.centroid_latitude = 12.9716
                self.centroid_longitude = 77.5946
                self.start_time = datetime(2026, 9, 21, 10, 30)
                self.last_updated = datetime(2026, 9, 21, 10, 30)
                self.event_count = 1
                self.status = "emerging"
                self.confidence = 0.9
                self.title = "Test Incident"
                self.summary = "Test summary"

        return MockIncident()

    @pytest.mark.asyncio
    async def test_create_new_incident(self, mock_db, sample_event):
        with patch(
            "ai.services.clustering_service.get_latest_ai_analysis",
            new_callable=AsyncMock,
            return_value=None,
        ):
            incident = await create_new_incident(sample_event, [0.1]*384, mock_db)

            assert incident.incident_type == "flood"
            assert incident.event_count == 1
            assert incident.status == "emerging"

    @pytest.mark.asyncio
    async def test_add_event_to_incident(self, mock_db, sample_event, sample_incident):
        result = MagicMock()
        result.scalars.return_value.all.return_value = [sample_event]
        mock_db.execute.return_value = result

        relationship = calculate_relationship_score(
            semantic_similarity=0.90,
            geographic_distance_meters=100,
            temporal_distance_minutes=15,
            disaster_type_match=True,
            disaster_type_score=1.0,
        )

<<<<<<< HEAD
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_event]
        mock_db.execute.return_value = mock_result

        with patch("ai.services.clustering_service.get_latest_ai_analysis", return_value=None):
=======
        with patch(
            "ai.services.clustering_service.get_latest_ai_analysis",
            new_callable=AsyncMock,
            return_value=None,
        ):
>>>>>>> origin/main
            incident_event = await add_event_to_incident(
                sample_event, sample_incident, relationship, [0.1]*384, mock_db
            )

            assert incident_event.incident_id == sample_incident.id
            assert incident_event.event_id == sample_event.id
            assert sample_incident.event_count == 2
            assert sample_incident.status == "active"


# Integration-style tests with mocked database
class TestProcessEventFlow:
    @pytest.fixture
    def mock_db(self):
        mock = AsyncMock()
        mock.add = MagicMock()
        return mock

    @pytest.mark.asyncio
    async def test_process_new_event_creates_incident(self, mock_db):
        event_id = uuid4()
        mock_event = MagicMock()
        mock_event.id = event_id
        mock_event.text_content = "Flooding near MG Road"
        mock_event.event_type = "flood"
        mock_event.latitude = 12.9716
        mock_event.longitude = 77.5946
        mock_event.location_name = "MG Road"
        mock_event.timestamp = datetime(2026, 9, 21, 10, 30)
        mock_event.metadata = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

<<<<<<< HEAD
        with patch("ai.services.clustering_service.find_best_matching_incident", return_value=(None, None)):
            with patch("ai.services.clustering_service.generate_and_store_embedding", return_value=[0.1]*384):
                with patch("ai.services.clustering_service.create_new_incident") as mock_create:
=======
        with patch(
            "ai.services.clustering_service.find_best_matching_incident",
            new_callable=AsyncMock,
            return_value=(None, None),
        ):
            with patch(
                "ai.services.clustering_service.generate_and_store_embedding",
                new_callable=AsyncMock,
                return_value=[0.1] * 384,
            ):
                with patch(
                    "ai.services.clustering_service.create_new_incident",
                    new_callable=AsyncMock,
                ) as mock_create:
>>>>>>> origin/main
                    mock_incident = MagicMock()
                    mock_incident.id = uuid4()
                    mock_create.return_value = mock_incident

                    result = await process_new_event(event_id, mock_db)

                    assert result["action"] == "created_new"
                    assert "incident_id" in result

    @pytest.mark.asyncio
    async def test_process_new_event_adds_to_existing(self, mock_db):
        event_id = uuid4()
        incident_id = uuid4()

        mock_event = MagicMock()
        mock_event.id = event_id
        mock_event.text_content = "More flooding near MG Road"
        mock_event.event_type = "flood"
        mock_event.latitude = 12.9716
        mock_event.longitude = 77.5946
        mock_event.location_name = "MG Road"
        mock_event.timestamp = datetime(2026, 9, 21, 10, 45)
        mock_event.metadata = {}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_event
        mock_db.execute.return_value = mock_result

        mock_incident = MagicMock()
        mock_incident.id = incident_id
        mock_incident.incident_type = "flood"
        mock_incident.centroid_latitude = 12.9716
        mock_incident.centroid_longitude = 77.5946
        mock_incident.last_updated = datetime(2026, 9, 21, 10, 30)

        relationship = calculate_relationship_score(
            semantic_similarity=0.85,
            geographic_distance_meters=100,
            temporal_distance_minutes=15,
            disaster_type_match=True,
            disaster_type_score=1.0,
        )

        with patch(
            "ai.services.clustering_service.find_best_matching_incident",
            new_callable=AsyncMock,
            return_value=(mock_incident, relationship),
        ):
            with patch(
                "ai.services.clustering_service.generate_and_store_embedding",
                new_callable=AsyncMock,
                return_value=[0.1] * 384,
            ):
                with patch(
                    "ai.services.clustering_service.add_event_to_incident",
                    new_callable=AsyncMock,
                ) as mock_add:
                    mock_incident_event = MagicMock()
                    mock_incident_event.id = uuid4()
                    mock_add.return_value = mock_incident_event

                    result = await process_new_event(event_id, mock_db)

                    assert result["action"] == "added_to_existing"
                    assert result["incident_id"] == str(incident_id)
                    assert result["relationship_score"] == pytest.approx(relationship.overall_score, rel=0.01)


# Additional tests for edge cases
class TestEdgeCases:
    def test_disaster_type_compatibility_groups(self):
        # Test various compatibility groups
        assert calculate_disaster_type_score("flood", "flash_flood")[0] is True
        assert calculate_disaster_type_score("wildfire", "forest_fire")[0] is True
        assert calculate_disaster_type_score("cyclone", "hurricane")[0] is True
        assert calculate_disaster_type_score("cyclone", "typhoon")[0] is True

    def test_disaster_type_incompatibility(self):
        assert calculate_disaster_type_score("flood", "wildfire")[0] is False
        assert calculate_disaster_type_score("earthquake", "flood")[0] is False
        assert calculate_disaster_type_score("landslide", "wildfire")[0] is False

    def test_weights_sum_to_one(self):
        assert abs(
            ai_config.SEMANTIC_WEIGHT
            + ai_config.GEOGRAPHIC_WEIGHT
            + ai_config.TEMPORAL_WEIGHT
            + ai_config.DISASTER_TYPE_WEIGHT
            - 1.0
        ) < 0.001