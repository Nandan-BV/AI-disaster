import logging
from pathlib import Path
from typing import Optional, List

from ai.services.text_analyzer import analyze_text
from ai.services.image_analyzer import analyze_image
from ai.services.video_analyzer import analyze_video
from ai.schemas.analysis import DisasterAnalysis

logger = logging.getLogger(__name__)


def analyze_multimodal(
    text: Optional[str] = None,
    image_path: Optional[str] = None,
    video_path: Optional[str] = None,
) -> DisasterAnalysis:
    """
    Perform multimodal analysis combining available inputs.

    Args:
        text: Optional text content
        image_path: Optional path to image
        video_path: Optional path to video

    Returns:
        Combined DisasterAnalysis from all available modalities
    """
    analyses: List[DisasterAnalysis] = []
    modalities_used = []

    if text and text.strip():
        logger.info("Analyzing text modality")
        text_analysis = analyze_text(text)
        analyses.append(text_analysis)
        modalities_used.append("text")

    if image_path:
        logger.info("Analyzing image modality")
        image_analysis = analyze_image(image_path)
        analyses.append(image_analysis)
        modalities_used.append("image")

    if video_path:
        logger.info("Analyzing video modality")
        video_analysis = analyze_video(video_path)
        analyses.append(video_analysis)
        modalities_used.append("video")

    if not analyses:
        return DisasterAnalysis(
            summary="No analyzable content provided",
            evidence_description="No text, image, or video available"
        )

    combined = analyses[0]
    for analysis in analyses[1:]:
        combined = combined.merge_with(analysis)

    combined.evidence_description = f"Multimodal analysis ({', '.join(modalities_used)}): {combined.evidence_description}"

    return combined


class EventAnalyzer:
    """High-level analyzer for event objects from the database."""

    def __init__(self):
        pass

    def analyze_event(
        self,
        event,
        text: Optional[str] = None,
        image_path: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> DisasterAnalysis:
        """
        Analyze an event using available modalities.

        Priority order for text: event.text_content -> provided text
        Priority order for image: event.image_url (local path) -> provided image_path
        Priority order for video: event.video_url (local path) -> provided video_path
        """
        analysis_text = text or getattr(event, "text_content", None)
        analysis_image = image_path or getattr(event, "image_url", None)
        analysis_video = video_path or getattr(event, "video_url", None)

        return analyze_multimodal(
            text=analysis_text,
            image_path=analysis_image,
            video_path=analysis_video,
        )