import logging
from pathlib import Path
from typing import Optional
from ai.models import model_manager
from ai.schemas.analysis import DisasterAnalysis

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "text_analysis.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


PROMPT_TEMPLATE = load_prompt()


def analyze_text(text: str) -> DisasterAnalysis:
    """
    Analyze disaster-related text using the configured AI model.

    Args:
        text: The text content to analyze

    Returns:
        DisasterAnalysis with structured results
    """
    if not text or not text.strip():
        return DisasterAnalysis(
            summary="No text content provided",
            evidence_description="Empty text input"
        )

    model = model_manager.load_model()
    prompt = PROMPT_TEMPLATE
    return model.analyze_text(text.strip(), prompt)