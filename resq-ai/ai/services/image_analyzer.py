import logging
from pathlib import Path
from typing import Union
from ai.models import model_manager
from ai.schemas.analysis import DisasterAnalysis
from ai.config import ai_config

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "image_analysis.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


PROMPT_TEMPLATE = load_prompt()


def validate_image_path(image_path: Union[str, Path]) -> Path:
    """Validate image path and format."""
    path = Path(image_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    if path.suffix.lower() not in ai_config.SUPPORTED_IMAGE_FORMATS:
        raise ValueError(
            f"Unsupported image format: {path.suffix}. "
            f"Supported: {ai_config.SUPPORTED_IMAGE_FORMATS}"
    )

    return path


def analyze_image(image_path: Union[str, Path]) -> DisasterAnalysis:
    """
    Analyze a disaster-related image using the configured AI model.

    Args:
        image_path: Path to the image file

    Returns:
        DisasterAnalysis with structured results
    """
    validated_path = validate_image_path(image_path)

    model = model_manager.load_model()
    prompt = PROMPT_TEMPLATE
    return model.analyze_image(validated_path, prompt)