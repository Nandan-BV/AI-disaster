"""
LLM provider registry for the RESQ-AI copilot.

Providers are registered by key so the serving stack stays swappable:

    openai_compatible -> vLLM / Ollama / llama.cpp / TGI (default)
    transformers     -> in-process loading, development only
    mock             -> deterministic offline stub for tests
"""

from app.ai.llm.base import (
    ChatCompletionResponse,
    CopilotLLMError,
    LLMClient,
    LLMClientFactory,
    Message,
    ToolDefinition,
)
from app.ai.llm.mock_client import MockLLMClient
from app.ai.llm.openai_compatible import OpenAICompatibleClient

LLMClientFactory.register("openai_compatible", OpenAICompatibleClient)
LLMClientFactory.register("mock", MockLLMClient)

try:  # Optional: only needed for in-process inference.
    from app.ai.llm.transformers_local import TransformersLocalClient

    LLMClientFactory.register("transformers", TransformersLocalClient)
except Exception:  # pragma: no cover - torch/transformers may be absent
    TransformersLocalClient = None  # type: ignore[assignment]

_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the process-wide copilot client, creating it on first use."""
    global _client
    if _client is None:
        _client = LLMClientFactory.create()
    return _client


def set_llm_client(client: LLMClient) -> None:
    """Override the copilot client (used by tests to inject a stub)."""
    global _client
    _client = client


def reset_llm_client() -> None:
    """Drop the cached client so the next call re-reads configuration."""
    global _client
    _client = None


__all__ = [
    "ChatCompletionResponse",
    "CopilotLLMError",
    "LLMClient",
    "LLMClientFactory",
    "Message",
    "ToolDefinition",
    "MockLLMClient",
    "OpenAICompatibleClient",
    "get_llm_client",
    "set_llm_client",
    "reset_llm_client",
]
