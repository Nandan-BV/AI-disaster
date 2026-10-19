import logging
import tempfile
import os
from pathlib import Path
from typing import List, Union
import cv2

from ai.models import model_manager
from ai.schemas.analysis import DisasterAnalysis
from ai.config import ai_config

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "video_analysis.txt"


def load_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


PROMPT_TEMPLATE = load_prompt()


def validate_video_path(video_path: Union[str, Path]) -> Path:
    """Validate video path and format."""
    path = Path(video_path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"Video not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    if path.suffix.lower() not in ai_config.SUPPORTED_VIDEO_FORMATS:
        raise ValueError(
            f"Unsupported video format: {path.suffix}. "
            f"Supported: {ai_config.SUPPORTED_VIDEO_FORMATS}"
        )

    return path


def extract_frames(
    video_path: Path,
    interval_seconds: int = None,
    max_frames: int = None,
) -> List[Path]:
    """
    Extract frames from video at specified interval.

    Args:
        video_path: Path to video file
        interval_seconds: Sample one frame every N seconds
        max_frames: Maximum number of frames to extract

    Returns:
        List of paths to extracted frame images
    """
    interval_seconds = interval_seconds or ai_config.VIDEO_FRAME_INTERVAL
    max_frames = max_frames or ai_config.VIDEO_MAX_FRAMES

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise ValueError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0

    if fps <= 0 or frame_count <= 0:
        cap.release()
        raise ValueError(f"Invalid video properties: fps={fps}, frames={frame_count}")

    frame_interval = int(fps * interval_seconds)
    frame_indices = list(range(0, frame_count, frame_interval))[:max_frames]

    frame_paths = []
    temp_dir = Path(tempfile.mkdtemp(prefix="resq_ai_frames_"))

    try:
        for idx, frame_idx in enumerate(frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret:
                continue

            frame_path = temp_dir / f"frame_{idx:04d}.jpg"
            cv2.imwrite(str(frame_path), frame)
            frame_paths.append(frame_path)

        logger.info(
            f"Extracted {len(frame_paths)} frames from {video_path.name} "
            f"(duration: {duration:.1f}s, fps: {fps:.1f}, interval: {interval_seconds}s)"
        )

    finally:
        cap.release()

    return frame_paths


def analyze_video(video_path: Union[str, Path]) -> DisasterAnalysis:
    """
    Analyze a disaster-related video by sampling frames.

    Args:
        video_path: Path to the video file

    Returns:
        DisasterAnalysis with combined results from sampled frames
    """
    validated_path = validate_video_path(video_path)

    frame_paths = extract_frames(validated_path)

    if not frame_paths:
        return DisasterAnalysis(
            summary="No frames could be extracted from video",
            evidence_description=f"Video: {validated_path.name}"
        )

    try:
        model = model_manager.load_model()
        # The prompt contains single braces for its JSON schema, so str.format()
        # cannot be used: it raises KeyError on the schema. Substitute the frame
        # count token directly instead.
        prompt = PROMPT_TEMPLATE.replace("{{frame_count}}", str(len(frame_paths)))
        return model.analyze_frames(frame_paths, prompt)

    finally:
        for frame_path in frame_paths:
            try:
                frame_path.unlink()
            except Exception:
                pass
        try:
            frame_paths[0].parent.rmdir()
        except Exception:
            pass