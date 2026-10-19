import pytest
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime
from uuid import UUID, uuid4

from ai.schemas.analysis import DisasterAnalysis
from ai.services.text_analyzer import analyze_text
from ai.services.image_analyzer import analyze_image
from ai.services.video_analyzer import analyze_video
from ai.services.multimodal_analyzer import analyze_multimodal, EventAnalyzer
from ai.models.base import BaseMultimodalModel
from ai.models.qwen_vl import QwenVLModel


# Mock AI responses for testing
MOCK_TEXT_ANALYSIS = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.92,
    severity_indicators=["water rising rapidly", "vehicles stuck", "rescue requested"],
    location_mentions=["city center", "main road"],
    damage_observed=["vehicles submerged", "road flooded"],
    people_affected="residents requesting rescue",
    vehicles_observed=["stuck vehicles"],
    infrastructure_damage=["main road flooded"],
    environmental_conditions=["heavy rain"],
    summary="Heavy flooding on main road near city center with vehicles stuck and rescue requested.",
    evidence_description="Text analysis: Social media post describing flooding"
)

MOCK_IMAGE_ANALYSIS = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.88,
    severity_indicators=["water covering road", "water above curb level"],
    location_mentions=["street view"],
    damage_observed=["flooded street", "submerged vehicles"],
    people_affected=None,
    vehicles_observed=["partially submerged cars"],
    infrastructure_damage=["road flooded"],
    environmental_conditions=["overcast", "daytime"],
    summary="Street-level view showing flood water covering road with partially submerged vehicles.",
    evidence_description="Image analysis showing flooded street with submerged vehicles"
)

MOCK_VIDEO_ANALYSIS = DisasterAnalysis(
    disaster_type="wildfire",
    disaster_type_confidence=0.95,
    severity_indicators=["fire spreading", "large smoke plume"],
    location_mentions=["forest area"],
    damage_observed=["burning vegetation", "smoke"],
    people_affected=None,
    vehicles_observed=["fire trucks visible in later frames"],
    infrastructure_damage=["power lines at risk"],
    environmental_conditions=["dry", "windy", "daytime"],
    summary="Drone footage showing active wildfire spreading through forest with large smoke plume. Fire trucks arrive in later frames.",
    evidence_description="Video frame analysis (12 frames) showing wildfire progression"
)

MOCK_MULTIMODAL_ANALYSIS = DisasterAnalysis(
    disaster_type="flood",
    disaster_type_confidence=0.95,
    severity_indicators=[
        "water rising rapidly", "vehicles stuck", "rescue requested",
        "water covering road", "water above curb level"
    ],
    location_mentions=["city center", "main road", "street view"],
    damage_observed=["vehicles submerged", "road flooded", "flooded street"],
    people_affected="residents requesting rescue",
    vehicles_observed=["stuck vehicles", "partially submerged cars"],
    infrastructure_damage=["main road flooded", "road flooded"],
    environmental_conditions=["heavy rain", "overcast", "daytime"],
    summary="Heavy flooding on main road near city center with vehicles stuck and rescue requested. Street-level view confirms water covering road with partially submerged vehicles.",
    evidence_description="Multimodal analysis (text, image): Text analysis: Social media post describing flooding; Image analysis showing flooded street with submerged vehicles"
)


class MockModel(BaseMultimodalModel):
    """Mock model for testing."""

    def __init__(self, response_map=None):
        self._loaded = True
        self._response_map = response_map or {}

    @property
    def model_name(self) -> str:
        return "test-model"

    def is_loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        self._loaded = True

    def unload(self) -> None:
        self._loaded = False

    def analyze_text(self, text: str, prompt: str) -> DisasterAnalysis:
        return self._response_map.get("text", MOCK_TEXT_ANALYSIS)

    def analyze_image(self, image_path: str, prompt: str) -> DisasterAnalysis:
        return self._response_map.get("image", MOCK_IMAGE_ANALYSIS)

    def analyze_frames(self, frame_paths: list, prompt: str) -> DisasterAnalysis:
        return self._response_map.get("video", MOCK_VIDEO_ANALYSIS)


class TestTextAnalyzer:
    @pytest.fixture
    def mock_model_manager(self):
        with patch("ai.services.text_analyzer.model_manager") as mock:
            mock_model = MockModel()
            mock.get_model.return_value = mock_model
            mock.load_model.return_value = mock_model
            yield mock

    def test_analyze_text_success(self, mock_model_manager):
        result = analyze_text("Heavy flooding reported near city center")
        assert result.disaster_type == "flood"
        assert result.disaster_type_confidence == 0.92
        assert "water rising rapidly" in result.severity_indicators

    def test_analyze_text_empty_input(self, mock_model_manager):
        result = analyze_text("")
        assert result.summary == "No text content provided"

    def test_analyze_text_whitespace_only(self, mock_model_manager):
        result = analyze_text("   ")
        assert result.summary == "No text content provided"


class TestImageAnalyzer:
    @pytest.fixture
    def mock_model_manager(self):
        with patch("ai.services.image_analyzer.model_manager") as mock:
            mock_model = MockModel()
            mock.get_model.return_value = mock_model
            mock.load_model.return_value = mock_model
            yield mock

    def test_analyze_image_success(self, mock_model_manager, tmp_path):
        test_image = tmp_path / "test_flood.jpg"
        test_image.write_bytes(b"fake image data")

        result = analyze_image(str(test_image))
        assert result.disaster_type == "flood"
        assert "water covering road" in result.severity_indicators

    def test_analyze_image_not_found(self, mock_model_manager):
        with pytest.raises(FileNotFoundError):
            analyze_image("nonexistent.jpg")

    def test_analyze_image_unsupported_format(self, mock_model_manager, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("not an image")
        with pytest.raises(ValueError, match="Unsupported image format"):
            analyze_image(str(test_file))


class TestVideoAnalyzer:
    @pytest.fixture
    def mock_model_manager(self):
        with patch("ai.services.video_analyzer.model_manager") as mock:
            mock_model = MockModel()
            mock.get_model.return_value = mock_model
            mock.load_model.return_value = mock_model
            yield mock

    def test_analyze_video_not_found(self, mock_model_manager):
        with pytest.raises(FileNotFoundError):
            analyze_video("nonexistent.mp4")

    def test_analyze_video_unsupported_format(self, mock_model_manager, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("not a video")
        with pytest.raises(ValueError, match="Unsupported video format"):
            analyze_video(str(test_file))

    @patch("ai.services.video_analyzer.cv2.VideoCapture")
    def test_analyze_video_invalid_video(self, mock_cv2, mock_model_manager, tmp_path):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False
        mock_cv2.return_value = mock_cap

        test_video = tmp_path / "test.mp4"
        test_video.write_bytes(b"fake video")

        with pytest.raises(ValueError, match="Could not open video"):
            analyze_video(str(test_video))


class TestMultimodalAnalyzer:
    @pytest.fixture
    def mock_model_manager(self):
        # analyze_multimodal() has no module-level model_manager: it delegates
        # to the text/image/video analyzers, so those are the patch targets.
        with ExitStack() as stack:
            mocks = [
                stack.enter_context(patch(f"ai.services.{name}.model_manager"))
                for name in ("text_analyzer", "image_analyzer", "video_analyzer")
            ]
            mock_model = MockModel()
            for mock in mocks:
                mock.get_model.return_value = mock_model
                mock.load_model.return_value = mock_model
            yield mocks[0]

    def test_analyze_text_only(self, mock_model_manager):
        result = analyze_multimodal(text="Flood reported")
        assert result.disaster_type == "flood"
        assert "text" in result.evidence_description

    def test_analyze_image_only(self, mock_model_manager, tmp_path):
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake")
        result = analyze_multimodal(image_path=str(test_image))
        assert result.disaster_type == "flood"
        assert "image" in result.evidence_description

    def test_analyze_video_only(self, mock_model_manager, tmp_path):
        test_video = tmp_path / "test.mp4"
        test_video.write_bytes(b"fake")
        with patch("ai.services.video_analyzer.extract_frames") as mock_extract:
            mock_extract.return_value = [Path("/tmp/frame1.jpg"), Path("/tmp/frame2.jpg")]
            result = analyze_multimodal(video_path=str(test_video))
            assert result.disaster_type == "wildfire"
            assert "video" in result.evidence_description

    def test_analyze_text_and_image(self, mock_model_manager, tmp_path):
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake")
        result = analyze_multimodal(text="Flood", image_path=str(test_image))
        assert result.disaster_type == "flood"
        assert "text" in result.evidence_description
        assert "image" in result.evidence_description

    def test_analyze_all_three(self, mock_model_manager, tmp_path):
        test_image = tmp_path / "test.jpg"
        test_image.write_bytes(b"fake")
        test_video = tmp_path / "test.mp4"
        test_video.write_bytes(b"fake")
        with patch("ai.services.video_analyzer.extract_frames") as mock_extract:
            mock_extract.return_value = [Path("/tmp/frame1.jpg")]
            result = analyze_multimodal(
                text="Flood",
                image_path=str(test_image),
                video_path=str(test_video)
            )
            assert "text" in result.evidence_description
            assert "image" in result.evidence_description
            assert "video" in result.evidence_description

    def test_analyze_no_content(self, mock_model_manager):
        result = analyze_multimodal()
        assert result.summary == "No analyzable content provided"


class TestEventAnalyzer:
    @pytest.fixture
    def mock_model_manager(self):
        # EventAnalyzer.analyze_event() delegates to analyze_multimodal(),
        # which in turn uses the text/image/video analyzers' model_manager.
        with ExitStack() as stack:
            mocks = [
                stack.enter_context(patch(f"ai.services.{name}.model_manager"))
                for name in ("text_analyzer", "image_analyzer", "video_analyzer")
            ]
            mock_model = MockModel()
            for mock in mocks:
                mock.get_model.return_value = mock_model
                mock.load_model.return_value = mock_model
            yield mocks[0]

    def test_analyze_event_with_text(self, mock_model_manager):
        class MockEvent:
            text_content = "Flood reported"
            image_url = None
            video_url = None

        analyzer = EventAnalyzer()
        result = analyzer.analyze_event(MockEvent())
        assert result.disaster_type == "flood"

    def test_analyze_event_override_text(self, mock_model_manager):
        class MockEvent:
            text_content = "Original text"
            image_url = None
            video_url = None

        analyzer = EventAnalyzer()
        result = analyzer.analyze_event(MockEvent(), text="Override text")
        assert result.disaster_type == "flood"


class TestDisasterAnalysisMerge:
    def test_merge_combines_unique_values(self):
        a1 = DisasterAnalysis(
            disaster_type="flood",
            severity_indicators=["water rising"],
            location_mentions=["city center"],
        )
        a2 = DisasterAnalysis(
            disaster_type="flood",
            severity_indicators=["vehicles stuck"],
            location_mentions=["downtown"],
        )
        merged = a1.merge_with(a2)
        assert "water rising" in merged.severity_indicators
        assert "vehicles stuck" in merged.severity_indicators
        assert "city center" in merged.location_mentions
        assert "downtown" in merged.location_mentions

    def test_merge_prefers_non_none_disaster_type(self):
        a1 = DisasterAnalysis(disaster_type=None)
        a2 = DisasterAnalysis(disaster_type="flood")
        merged = a1.merge_with(a2)
        assert merged.disaster_type == "flood"

    def test_merge_takes_max_confidence(self):
        a1 = DisasterAnalysis(disaster_type_confidence=0.7)
        a2 = DisasterAnalysis(disaster_type_confidence=0.9)
        merged = a1.merge_with(a2)
        assert merged.disaster_type_confidence == 0.9

    def test_merge_combines_evidence_description(self):
        a1 = DisasterAnalysis(evidence_description="Text analysis")
        a2 = DisasterAnalysis(evidence_description="Image analysis")
        merged = a1.merge_with(a2)
        assert "Text analysis" in merged.evidence_description
        assert "Image analysis" in merged.evidence_description