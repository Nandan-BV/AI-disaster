from typing import Optional
from ai.models.base import BaseMultimodalModel
from ai.models.qwen_vl import QwenVLModel
from ai.models.embedding_base import BaseEmbeddingModel
from ai.models.sentence_transformer_embedding import SentenceTransformerEmbedding
from ai.config import ai_config


def get_multimodal_model(model_name: Optional[str] = None) -> BaseMultimodalModel:
    """Factory function to get the appropriate multimodal model instance."""
    name = model_name or ai_config.AI_MODEL_NAME

    if "qwen" in name.lower():
        return QwenVLModel()
    else:
        raise ValueError(f"Unsupported multimodal model: {name}")


def get_embedding_model(model_name: Optional[str] = None) -> BaseEmbeddingModel:
    """Factory function to get the appropriate embedding model instance."""
    name = model_name or ai_config.EMBEDDING_MODEL_NAME

    if "sentence-transformers" in name.lower() or "bge" in name.lower() or "minilm" in name.lower() or "mpnet" in name.lower():
        return SentenceTransformerEmbedding()
    else:
        raise ValueError(f"Unsupported embedding model: {name}")


class ModelManager:
    """Singleton manager for multimodal model lifecycle."""

    _instance = None
    _model: Optional[BaseMultimodalModel] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self) -> BaseMultimodalModel:
        if self._model is None:
            self._model = get_multimodal_model()
        return self._model

    def load_model(self) -> BaseMultimodalModel:
        model = self.get_model()
        if not model.is_loaded():
            model.load()
        return model

    def unload_model(self) -> None:
        if self._model and self._model.is_loaded():
            self._model.unload()
            self._model = None


class EmbeddingManager:
    """Singleton manager for embedding model lifecycle."""

    _instance = None
    _model: Optional[BaseEmbeddingModel] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_model(self) -> BaseEmbeddingModel:
        if self._model is None:
            self._model = get_embedding_model()
        return self._model

    def load_model(self) -> BaseEmbeddingModel:
        model = self.get_model()
        if not model.is_loaded():
            model.load()
        return model

    def unload_model(self) -> None:
        if self._model and self._model.is_loaded():
            self._model.unload()
            self._model = None


model_manager = ModelManager()
embedding_manager = EmbeddingManager()