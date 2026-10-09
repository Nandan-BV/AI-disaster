import logging
from typing import Optional
from ai.models import embedding_manager
from ai.schemas.analysis import DisasterAnalysis

logger = logging.getLogger(__name__)


def build_event_text_representation(
    event_text: Optional[str] = None,
    disaster_type: Optional[str] = None,
    ai_summary: Optional[str] = None,
    location_mentions: Optional[list] = None,
    damage_observed: Optional[list] = None,
) -> str:
    """
    Build a meaningful text representation of an event for embedding.

    Combines available information from original event and AI analysis.
    """
    parts = []

    if event_text and event_text.strip():
        parts.append(event_text.strip())

    if disaster_type:
        parts.append(f"Disaster type: {disaster_type}")

    if ai_summary and ai_summary.strip():
        parts.append(f"Summary: {ai_summary.strip()}")

    if location_mentions:
        parts.append(f"Locations: {', '.join(location_mentions)}")

    if damage_observed:
        parts.append(f"Damage: {', '.join(damage_observed)}")

    return " | ".join(parts) if parts else "No event information"


def generate_event_embedding(
    event_text: Optional[str] = None,
    disaster_type: Optional[str] = None,
    ai_summary: Optional[str] = None,
    location_mentions: Optional[list] = None,
    damage_observed: Optional[list] = None,
) -> Optional[list]:
    """
    Generate embedding for an event using the embedding model.

    Returns list of floats (embedding vector) or None if no content.
    """
    text = build_event_text_representation(
        event_text=event_text,
        disaster_type=disaster_type,
        ai_summary=ai_summary,
        location_mentions=location_mentions,
        damage_observed=damage_observed,
    )

    if text == "No event information":
        return None

    try:
        model = embedding_manager.load_model()
        embedding = model.encode_single(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    if not texts:
        return []

    try:
        model = embedding_manager.load_model()
        embeddings = model.encode(texts)
        return embeddings.tolist()
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return []


def cosine_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """Calculate cosine similarity between two embeddings."""
    import numpy as np

    a = np.array(embedding1)
    b = np.array(embedding2)

    a_norm = np.linalg.norm(a)
    b_norm = np.linalg.norm(b)

    if a_norm == 0 or b_norm == 0:
        return 0.0

    return float(np.dot(a, b) / (a_norm * b_norm))