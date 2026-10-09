from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class AIConfig(BaseSettings):
    # Model Configuration
    AI_MODEL_NAME: str = Field(
        default="Qwen/Qwen2.5-VL-3B-Instruct",
        alias="AI_MODEL_NAME",
        description="HuggingFace model identifier for the vision-language model"
    )
    AI_MODEL_REVISION: str = Field(
        default="main",
        alias="AI_MODEL_REVISION",
        description="Model revision/branch to use"
    )
    AI_DEVICE: str = Field(
        default="auto",
        alias="AI_DEVICE",
        description="Device to run model on: auto, cuda, cpu, mps"
    )
    AI_DTYPE: str = Field(
        default="auto",
        alias="AI_DTYPE",
        description="Model dtype: auto, float16, bfloat16, float32"
    )
    AI_MAX_MEMORY: Optional[str] = Field(
        default=None,
        alias="AI_MAX_MEMORY",
        description="Max GPU memory per GPU (e.g., '8GiB')"
    )
    AI_OFFLOAD_FOLDER: Optional[str] = Field(
        default=None,
        alias="AI_OFFLOAD_FOLDER",
        description="Folder for offloading weights if using CPU offload"
    )

    # Inference Configuration
    AI_MAX_NEW_TOKENS: int = Field(
        default=1024,
        alias="AI_MAX_NEW_TOKENS",
        description="Maximum new tokens to generate"
    )
    AI_TEMPERATURE: float = Field(
        default=0.1,
        alias="AI_TEMPERATURE",
        description="Sampling temperature (lower = more deterministic)"
    )
    AI_TOP_P: float = Field(
        default=0.9,
        alias="AI_TOP_P",
        description="Top-p sampling"
    )
    AI_DO_SAMPLE: bool = Field(
        default=False,
        alias="AI_DO_SAMPLE",
        description="Whether to use sampling"
    )

    # Video Analysis
    VIDEO_FRAME_INTERVAL: int = Field(
        default=5,
        alias="VIDEO_FRAME_INTERVAL",
        description="Sample one frame every N seconds"
    )
    VIDEO_MAX_FRAMES: int = Field(
        default=20,
        alias="VIDEO_MAX_FRAMES",
        description="Maximum frames to analyze per video"
    )

    # Image Processing
    MAX_IMAGE_SIZE: int = Field(
        default=1024,
        alias="MAX_IMAGE_SIZE",
        description="Maximum image dimension (resize larger images)"
    )
    SUPPORTED_IMAGE_FORMATS: list[str] = Field(
        default=[".jpg", ".jpeg", ".png", ".webp", ".bmp"],
        alias="SUPPORTED_IMAGE_FORMATS",
    )
    SUPPORTED_VIDEO_FORMATS: list[str] = Field(
        default=[".mp4", ".avi", ".mov", ".mkv", ".webm"],
        alias="SUPPORTED_VIDEO_FORMATS",
    )

    # Timeouts
    AI_INFERENCE_TIMEOUT: int = Field(
        default=300,
        alias="AI_INFERENCE_TIMEOUT",
        description="Inference timeout in seconds"
    )
    MODEL_LOAD_TIMEOUT: int = Field(
        default=120,
        alias="MODEL_LOAD_TIMEOUT",
        description="Model loading timeout in seconds"
    )

    # Cache
    HF_CACHE_DIR: Optional[str] = Field(
        default=None,
        alias="HF_CACHE_DIR",
        description="HuggingFace cache directory"
    )

    # Embedding Model (Phase 3)
    EMBEDDING_MODEL_NAME: str = Field(
        default="BAAI/bge-small-en-v1.5",
        alias="EMBEDDING_MODEL_NAME",
        description="HuggingFace model identifier for sentence embeddings"
    )
    EMBEDDING_DEVICE: str = Field(
        default="auto",
        alias="EMBEDDING_DEVICE",
        description="Device for embedding model: auto, cuda, cpu, mps"
    )
    EMBEDDING_BATCH_SIZE: int = Field(
        default=32,
        alias="EMBEDDING_BATCH_SIZE",
        description="Batch size for embedding generation"
    )
    EMBEDDING_MAX_LENGTH: int = Field(
        default=512,
        alias="EMBEDDING_MAX_LENGTH",
        description="Maximum sequence length for embeddings"
    )

    # Clustering Configuration (Phase 3)
    SEMANTIC_SIMILARITY_THRESHOLD: float = Field(
        default=0.75,
        alias="SEMANTIC_SIMILARITY_THRESHOLD",
        description="Minimum cosine similarity for semantic match (0-1)"
    )
    MAX_DISTANCE_METERS: float = Field(
        default=2000.0,
        alias="MAX_DISTANCE_METERS",
        description="Maximum geographic distance for incident clustering (meters)"
    )
    MAX_TIME_DIFFERENCE_MINUTES: int = Field(
        default=120,
        alias="MAX_TIME_DIFFERENCE_MINUTES",
        description="Maximum time difference for incident clustering (minutes)"
    )
    RELATIONSHIP_SCORE_THRESHOLD: float = Field(
        default=0.65,
        alias="RELATIONSHIP_SCORE_THRESHOLD",
        description="Minimum overall relationship score to assign to existing incident (0-1)"
    )

    # Weight for relationship score components (must sum to 1.0)
    SEMANTIC_WEIGHT: float = Field(
        default=0.40,
        alias="SEMANTIC_WEIGHT",
        description="Weight for semantic similarity in relationship score"
    )
    GEOGRAPHIC_WEIGHT: float = Field(
        default=0.30,
        alias="GEOGRAPHIC_WEIGHT",
        description="Weight for geographic proximity in relationship score"
    )
    TEMPORAL_WEIGHT: float = Field(
        default=0.20,
        alias="TEMPORAL_WEIGHT",
        description="Weight for temporal proximity in relationship score"
    )
    DISASTER_TYPE_WEIGHT: float = Field(
        default=0.10,
        alias="DISASTER_TYPE_WEIGHT",
        description="Weight for disaster type compatibility in relationship score"
    )

    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


ai_config = AIConfig()


def get_device() -> str:
    """Determine the best available device."""
    if ai_config.AI_DEVICE != "auto":
        return ai_config.AI_DEVICE

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def get_torch_dtype() -> "torch.dtype":
    """Get the torch dtype for model loading."""
    import torch
    if ai_config.AI_DTYPE != "auto":
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        return dtype_map.get(ai_config.AI_DTYPE, torch.float16)

    device = get_device()
    if device == "cuda":
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    return torch.float32