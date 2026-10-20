"""
OpenAI-compatible HTTP client for the copilot.

This is the default provider. Any server that speaks the OpenAI chat-completions
API can back the copilot, so the serving framework stays configurable:

    vLLM       -> python -m vllm.entrypoints.openai.api_server \\
                    --model Qwen/Qwen2.5-7B-Instruct
    Ollama     -> ollama serve          (base url http://localhost:11434/v1)
    llama.cpp  -> llama-server           (OpenAI-compatible mode)
    TGI        -> text-generation-launcher

No external credential is required; ``COPILOT_API_KEY`` is only sent when set.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from app.ai.llm.base import (
    ChatCompletionResponse,
    CopilotLLMError,
    LLMClient,
    Message,
    ToolDefinition,
)
from app.config import settings

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(LLMClient):
    """Talks to a local/remote OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self._base_url = (
            base_url
            or settings.COPILOT_API_BASE_URL
            or f"{settings.OLLAMA_BASE_URL.rstrip('/')}/v1"
        ).rstrip("/")
        self._model_name = model_name or settings.COPILOT_MODEL_NAME
        self._api_key = api_key if api_key is not None else settings.COPILOT_API_KEY
        self._timeout = timeout or float(settings.COPILOT_TIMEOUT_SECONDS)

    @property
    def model_name(self) -> str:
        return self._model_name

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            # Local servers commonly expect a placeholder rather than a real key.
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    @staticmethod
    def _serialize(messages: List[Message]) -> List[Dict[str, Any]]:
        payload: List[Dict[str, Any]] = []
        for m in messages:
            entry: Dict[str, Any] = {"role": m.role, "content": m.content}
            if m.name:
                entry["name"] = m.name
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            if m.tool_calls:
                entry["tool_calls"] = [
                    call
                    if "function" in call
                    else {
                        "id": call.get("id"),
                        "type": "function",
                        "function": {
                            "name": call.get("name"),
                            "arguments": call.get("arguments") or "{}",
                        },
                    }
                    for call in m.tool_calls
                ]
            payload.append(entry)
        return payload

    @staticmethod
    def _parse_tool_calls(raw: Any) -> List[Dict[str, Any]]:
        """Normalise provider tool calls into ``{id,name,arguments}`` dicts.

        ``arguments`` is kept as a JSON *string* here; the registry parses and
        validates it before anything executes.
        """
        calls: List[Dict[str, Any]] = []
        for call in raw or []:
            fn = call.get("function") or {}
            arguments = fn.get("arguments")
            if isinstance(arguments, (dict, list)):
                arguments = json.dumps(arguments)
            calls.append(
                {
                    "id": call.get("id"),
                    "name": fn.get("name"),
                    "arguments": arguments or "{}",
                }
            )
        return calls

    @staticmethod
    def _build_response(data: Dict[str, Any]) -> ChatCompletionResponse:
        choices = data.get("choices") or []
        if not choices:
            raise CopilotLLMError("Model returned no completion choices.")
        message = choices[0].get("message") or {}
        return ChatCompletionResponse(
            content=(message.get("content") or "").strip(),
            tool_calls=OpenAICompatibleClient._parse_tool_calls(message.get("tool_calls")),
            finish_reason=choices[0].get("finish_reason"),
            usage=data.get("usage"),
        )

    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> ChatCompletionResponse:
        if not self._base_url:
            raise CopilotLLMError("COPILOT_API_BASE_URL is not configured.")

        body: Dict[str, Any] = {
            "model": self._model_name,
            "messages": self._serialize(messages),
            # Low temperature by default: groundedness over creativity (spec 45).
            "temperature": settings.COPILOT_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.COPILOT_MAX_TOKENS if max_tokens is None else max_tokens,
            "top_p": settings.COPILOT_TOP_P if top_p is None else top_p,
        }
        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]
            body["tool_choice"] = "auto"

        url = f"{self._base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=self._headers(), json=body)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise CopilotLLMError(
                f"The copilot model did not respond within {self._timeout:.0f}s."
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.error("Copilot endpoint returned HTTP %s.", exc.response.status_code)
            raise CopilotLLMError(
                f"The copilot model returned an error ({exc.response.status_code})."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Copilot endpoint unreachable: %s", exc)
            raise CopilotLLMError(
                "The AI copilot is temporarily unavailable. The model server "
                f"could not be reached at {self._base_url}."
            ) from exc
        except ValueError as exc:
            raise CopilotLLMError("The copilot model returned a malformed response.") from exc

        return self._build_response(data)

    async def chat_completion_stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        if not self._base_url:
            raise CopilotLLMError("COPILOT_API_BASE_URL is not configured.")

        body: Dict[str, Any] = {
            "model": self._model_name,
            "messages": self._serialize(messages),
            "temperature": settings.COPILOT_TEMPERATURE if temperature is None else temperature,
            "max_tokens": settings.COPILOT_MAX_TOKENS if max_tokens is None else max_tokens,
            "top_p": settings.COPILOT_TOP_P if top_p is None else top_p,
            "stream": True,
        }
        if tools:
            body["tools"] = [t.to_openai_schema() for t in tools]
            body["tool_choice"] = "auto"

        url = f"{self._base_url}/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream("POST", url, headers=self._headers(), json=body) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        chunk = line[len("data:"):].strip()
                        if chunk == "[DONE]":
                            break
                        try:
                            parsed = json.loads(chunk)
                        except json.JSONDecodeError:
                            logger.warning("Skipping unparseable SSE chunk from copilot model.")
                            continue
                        for choice in parsed.get("choices") or []:
                            delta = (choice.get("delta") or {}).get("content")
                            if delta:
                                yield delta
        except httpx.HTTPError as exc:
            raise CopilotLLMError(
                "The AI copilot is temporarily unavailable."
            ) from exc

    async def health_check(self) -> bool:
        """Return True only when the configured model is served."""
        if not self._base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models", headers=self._headers())
                response.raise_for_status()
                data = response.json()
                models = data.get("data") if isinstance(data, dict) else None
                return isinstance(models, list) and any(
                    model.get("id") == self._model_name
                    for model in models
                    if isinstance(model, dict)
                )
        except (httpx.HTTPError, ValueError):
            return False

    def is_available(self) -> bool:
        """Configuration-level availability check (no network call).

        The HTTP provider is considered available as long as it is configured;
        reachability is checked per request and surfaced as
        :class:`CopilotLLMError`.
        """
        return bool(self._base_url and self._model_name)
