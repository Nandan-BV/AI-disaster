import logging
from typing import List, Optional
import numpy as np

from sentence_transformers import SentenceTransformer
import torch

from ai.config import ai_config
from ai.models.embedding_base import BaseEmbeddingModel

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedding(BaseEmbeddingModel):
    """Sentence-Transformers implementation for embeddings."""

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._device = self._get_device()
        self._loaded = False

    def _get_device(self) -> str:
        if ai_config.EMBEDDING_DEVICE != "auto":
            return ai_config.EMBEDDING_DEVICE
        try:
            if torch.cuda.is_available():
                return "cuda"
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    @property
    def model_name(self) -> str:
        return ai_config.EMBEDDING_MODEL_NAME

    @property
    def embedding_dim(self) -> int:
        # bge-small-en-v1.5: 384, all-MiniLM-L6-v2: 384, all-mpnet-base-v2: 768
        if "bge-small" in self.model_name:
            return 384
        if "MiniLM" in self.model_name:
            return 384
        if "mpnet" in self.model_name:
            return 768
        return 384  # default

    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None

    def load(self) -> None:
        if self.is_loaded():
            logger.info(f"Embedding model {self.model_name} already loaded")
            return

        logger.info(f"Loading embedding model {self.model_name} on {self._device}")

        try:
            self._model = SentenceTransformer(
                self.model_name,
                device=self._device,
            )
            self._model.max_seq_length = ai_config.EMBEDDING_MAX_LENGTH
            self._loaded = True
            logger.info(f"Embedding model {self.model_name} loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load embedding model {self.model_name}: {e}")
            self._loaded = False
            raise

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self._loaded = False
        logger.info(f"Embedding model {self.model_name} unloaded")

    def encode(self, texts: List[str]) -> np.ndarray:
        if not self.is_loaded():
            raise RuntimeError("Model not loaded. Call load() first.")

        if not texts:
            return np.array([]).reshape(0, self.embedding_dim)

        embeddings = self._model.encode(
            texts,
            batch_size=ai_config.EMBEDDING_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,  # Normalize for cosine similarity
        )
        return embeddings

    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]