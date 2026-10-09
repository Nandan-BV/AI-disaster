"""
In-process ``transformers`` provider (development / single-node only).

Prefer :mod:`app.ai.llm.openai_compatible` for anything beyond local
development: loading a 7B model inside the API process pins multi-GB weights to
the web server and competes with request handling for memory.

Two correctness details this module exists to get right:

1. Model loading and token generation are CPU/GPU-bound and blocking, so they
   are pushed onto a worker thread (``anyio.to_thread``). Running them directly
   inside ``async def`` would stall the event loop for the whole generation.
2. ``transformers`` is imported lazily, so the backend still imports on hosts
   that only use the HTTP provider and never install torch.
"""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.ai.llm.base import (
    ChatCompletionResponse,
    CopilotLLMError,
    LLMClient,
    Message,
    ToolDefinition,
)
from app.config import get_device, get_torch_dtype, settings

logger = logging.getLogger(__name__)


class TransformersLocalClient(LLMClient):
    """Runs a local Hugging Face causal LM in-process."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self._model_name = model_name or settings.COPILOT_MODEL_NAME
        self._model: Any = None
        self._tokenizer: Any = None
        self._device = get_device()
        self._dtype = get_torch_dtype()
        self._load_lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return True

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as exc:  # pragma: no cover - env dependent
            raise CopilotLLMError(
                "The in-process copilot provider requires 'transformers' and 'torch'. "
                "Install them, or set COPILOT_PROVIDER=openai_compatible."
            ) from exc

        logger.info("Loading copilot model %s on %s (%s)", self._model_name, self._device, self._dtype)
        self._tokenizer = AutoTokenizer.from_pretrained(
            self._model_name, revision=settings.COPILOT_MODEL_REVISION, trust_remote_code=True
        )

        kwargs: Dict[str, Any] = {
            "torch_dtype": self._dtype,
            "trust_remote_code": True,
        }
        if self._device == "cuda":
            kwargs["device_map"] = "auto"
            if settings.COPILOT_MAX_MEMORY:
                kwargs["max_memory"] = {0: settings.COPILOT_MAX_MEMORY}
            if settings.COPILOT_OFFLOAD_FOLDER:
                kwargs["offload_folder"] = settings.COPILOT_OFFLOAD_FOLDER

        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_name, revision=settings.COPILOT_MODEL_REVISION, **kwargs
        )
        if self._device != "cuda":
            self._model = self._model.to(self._device)
        self._model.eval()

    async def _load_async(self) -> None:
        async with self._load_lock:
            if self._model is None:
                await asyncio.to_thread(self._ensure_loaded)

    @staticmethod
    def _serialize(messages: List[Message]) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def _generate_sync(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]],
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> str:
        import torch

        chat = self._serialize(messages)
        if tools:
            # Qwen2.5 supports the OpenAI-style tool schema in its template.
            chat[-1]["content"] = chat[-1]["content"] + (
                "\n\nYou may call these tools. Tool schemas:\n"
                + json.dumps([t.to_openai_schema() for t in tools], indent=2)
                + "\nRespond with a single JSON object: "
                  '{"tool": "<name>", "arguments": {...}} or {"content": "..."}.'
            )

        text = self._tokenizer.apply_chat_template(
            chat, tokenize=False, add_generation_prompt=True
        )
        inputs = self._tokenizer([text], return_tensors="pt").to(self._device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=settings.COPILOT_DO_SAMPLE,
                pad_token_id=self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
            )

        generated = output_ids[0][inputs["input_ids"].shape[-1]:]
        return self._tokenizer.decode(generated, skip_special_tokens=True).strip()

    def _parse_output(self, raw: str) -> ChatCompletionResponse:
        """Best-effort parse of a model turn into content and/or a tool call."""
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[len("json"):]
            text = text.strip().removesuffix("```").strip()

        if text.startswith("{"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = None
            if isinstance(payload, dict):
                tool_name = payload.get("tool")
                if tool_name:
                    return ChatCompletionResponse(
                        content="",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "name": tool_name,
                                "arguments": json.dumps(payload.get("arguments") or {}),
                            }
                        ],
                        finish_reason="tool_calls",
                    )
                if payload.get("content"):
                    return ChatCompletionResponse(
                        content=str(payload["content"]).strip(), finish_reason="stop"
                    )

        return ChatCompletionResponse(content=text, finish_reason="stop")

    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> ChatCompletionResponse:
        await self._load_async()
        try:
            raw = await asyncio.to_thread(
                self._generate_sync,
                messages,
                tools,
                settings.COPILOT_TEMPERATURE if temperature is None else temperature,
                settings.COPILOT_MAX_TOKENS if max_tokens is None else max_tokens,
                settings.COPILOT_TOP_P if top_p is None else top_p,
            )
        except CopilotLLMError:
            raise
        except Exception as exc:  # pragma: no cover - model/runtime dependent
            logger.exception("Local copilot generation failed")
            raise CopilotLLMError("The AI copilot is temporarily unavailable.") from exc

        return self._parse_output(raw)

    async def chat_completion_stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Token streaming is not supported in-process; emit a single chunk."""
        response = await self.chat_completion(messages, tools, temperature, max_tokens, top_p)
        if response.tool_calls:
            yield "[tool call pending]"
            return
        yield response.content

    def unload(self) -> None:
        """Free model memory. Safe to call when nothing is loaded."""
        self._model = None
        self._tokenizer = None
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
