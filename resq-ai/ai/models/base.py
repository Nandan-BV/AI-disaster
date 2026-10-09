from abc import ABC, abstractmethod
from typing import Optional, List, Union
from pathlib import Path
from ai.schemas.analysis import DisasterAnalysis


class BaseMultimodalModel(ABC):
    """Abstract base class for multimodal AI models."""

    @abstractmethod
    def load(self) -> None:
        """Load the model into memory."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Unload the model from memory."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        pass

    @abstractmethod
    def analyze_text(self, text: str, prompt: str) -> DisasterAnalysis:
        """Analyze text content."""
        pass

    @abstractmethod
    def analyze_image(self, image_path: Union[str, Path], prompt: str) -> DisasterAnalysis:
        """Analyze a single image."""
        pass

    @abstractmethod
    def analyze_frames(self, frame_paths: List[Union[str, Path]], prompt: str) -> DisasterAnalysis:
        """Analyze multiple frames (for video)."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass