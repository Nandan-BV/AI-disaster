"""
Model-agnostic LLM abstraction for the RESQ-AI copilot.

The rest of the application talks to :class:`LLMClient` only. Concrete serving
backends (an OpenAI-compatible local server, in-process transformers, or an
offline stub) are registered against a *provider* key, so swapping Qwen for
another open-source model - or moving it between runtimes - requires no change
to calling code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field


class CopilotLLMError(RuntimeError):
    """Raised when the copilot model is unavailable or fails to respond.

    The copilot API maps this to a controlled "temporarily unavailable"
    response instead of surfacing a stack trace (spec 46).
    """


@dataclass
class Message:
    """A single conversation message.

    ``content`` is always text. Untrusted incident/event content must be
    wrapped by the caller in explicit delimiters before it reaches a model, so
    that it can never be mistaken for an instruction (spec 36).
    """

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ChatCompletionResponse:
    """A non-streaming completion."""

    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


@dataclass
class ToolDefinition:
    """A tool the model may call.

    This is the single definition used by both the registry and the wire format
    handed to the provider, so a tool can never be described to the model
    differently from how it is executed.
    """

    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema for the tool input
    handler: Optional[Any] = None  # async callable; populated by the registry

    def to_openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class LLMClient(ABC):
    """Abstract base class for copilot LLM clients."""

    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> ChatCompletionResponse:
        """Generate a chat completion, optionally with tool-calling enabled."""
        raise NotImplementedError

    @abstractmethod
    def chat_completion_stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a chat completion token by token."""
        raise NotImplementedError

    async def generate_structured(
        self,
        messages: List[Message],
        response_model: type[BaseModel],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> BaseModel:
        """Generate output validated against ``response_model``."""
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Whether the backend can currently serve a request."""
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identifier of the served model."""
        raise NotImplementedError


class LLMClientFactory:
    """Creates clients by *provider* key (not by model name)."""

    _providers: Dict[str, Any] = {}

    @classmethod
    def register(cls, provider: str, client_class: Any) -> None:
        cls._providers[provider.strip().lower()] = client_class

    @classmethod
    def available_providers(cls) -> List[str]:
        return sorted(cls._providers)

    @classmethod
    def create(cls, provider: Optional[str] = None) -> LLMClient:
        """Instantiate the configured provider's client.

        Raises:
            ValueError: if the provider is unknown or no provider is registered.
        """
        from app.config import settings

        key = (provider or settings.COPILOT_PROVIDER or "openai_compatible").strip().lower()
        if key not in cls._providers:
            raise ValueError(
                f"Unknown copilot provider {key!r}. "
                f"Registered providers: {cls.available_providers()}"
            )
        return cls._providers[key]()
