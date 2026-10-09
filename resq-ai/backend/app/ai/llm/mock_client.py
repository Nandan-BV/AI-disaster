"""
Deterministic offline copilot provider.

Used by the test suite and by local development when no model server is
running. It is *not* a language model: it selects tools by keyword and then
summarises the tool payloads it was given.

Because it can only ever speak from tool output, it is also the easiest way to
assert the grounding property required by spec 20/47 - if a fact is not in a
tool result, this provider cannot say it.
"""

import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.ai.llm.base import (
    ChatCompletionResponse,
    CopilotLLMError,
    LLMClient,
    Message,
    ToolDefinition,
)

# Keyword -> tool name, evaluated in order. First match wins.
_ROUTING = [
    (r"\boptimiz|recommend|allocat|unmet demand|dispatch", "get_optimization_result"),
    (r"\bnearby (resource|ambulance|shelter)|available|how many (ambulance|resource|shelter)|resource", "get_nearby_resources"),
    (r"\binfrastructure|hospital|shelter|fire station|police|school|bridge|road|power|water|emergency center", "get_infrastructure"),
    (r"\brisk|danger|severe|severity", "get_risk"),
    (r"\bimpact|exposed|population|casualt|people affected", "get_impact"),
    (r"\bevidence|support|investigat|real|true|credible|contradict", "get_evidence"),
    (r"\buncert|unknown|unclear|missing|confidence", "get_evidence"),
    (r"\bhappen|what is this|summar|status|overview|describe", "get_incident"),
]

_UNAVAILABLE = (
    "That information is not available in the database right now. "
    "I have not estimated or inferred it."
)


class MockLLMClient(LLMClient):
    """Keyword-routed tool-calling stand-in for a real model."""

    def __init__(self, model_name: str = "mock-copilot") -> None:
        self._model_name = model_name
        # Tools offered to the model in the current turn, keyed by name.
        self._offered: Dict[str, ToolDefinition] = {}

    @property
    def model_name(self) -> str:
        return self._model_name

    def is_available(self) -> bool:
        return True

    def _select_tool(self, question: str) -> Optional[str]:
        for pattern, tool_name in _ROUTING:
            if re.search(pattern, question, re.IGNORECASE):
                if tool_name in self._offered:
                    return tool_name
        # Fall back to the first offered tool so the loop is still exercised.
        return next(iter(self._offered), None)

    @staticmethod
    def _last_user_question(messages: List[Message]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return ""

    @staticmethod
    def _last_tool_output(messages: List[Message]) -> Optional[str]:
        for message in reversed(messages):
            if message.role == "tool":
                return message.content
        return None

    async def chat_completion(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> ChatCompletionResponse:
        self._offered = {t.name: t for t in (tools or [])}

        # Turn 2+: the previous tool result is present - answer from it.
        tool_output = self._last_tool_output(messages)
        if tool_output is not None:
            return ChatCompletionResponse(
                content=self._summarise(tool_output),
                tool_calls=[],
                finish_reason="stop",
            )

        question = self._last_user_question(messages)
        tool_name = self._select_tool(question)
        if tool_name is None:
            return ChatCompletionResponse(
                content=_UNAVAILABLE, tool_calls=[], finish_reason="stop"
            )

        tool = self._offered[tool_name]
        arguments = self._build_arguments(tool_name, tool, question, messages)
        return ChatCompletionResponse(
            content="",
            tool_calls=[
                {"id": "call_1", "name": tool_name, "arguments": json.dumps(arguments)}
            ],
            finish_reason="tool_calls",
        )

    def _build_arguments(
        self,
        tool_name: str,
        tool: ToolDefinition,
        question: str,
        messages: List[Message],
    ) -> Dict[str, Any]:
        """Fill required arguments from the question or the active incident."""
        properties = (tool.parameters.get("properties") or {})
        required = tool.parameters.get("required") or []
        args: Dict[str, Any] = {}
        for field_name in required:
            if field_name == "incident_id":
                match = re.search(r"incident\s+(\d+)", question, re.IGNORECASE)
                args[field_name] = int(match.group(1)) if match else 0
            elif field_name in properties:
                args[field_name] = properties[field_name].get("default")
        return args

    def _summarise(self, raw_tool_output: str) -> str:
        try:
            payload = json.loads(raw_tool_output)
        except (json.JSONDecodeError, TypeError):
            return raw_tool_output

        if payload.get("error") or payload.get("available") is False:
            return str(payload.get("error") or _UNAVAILABLE)

        lines = [f"Based on {payload.get('source', 'backend data')}:", ""]
        for key, value in payload.items():
            if key in {"source", "error", "available"}:
                continue
            if value in (None, [], {}, ""):
                lines.append(f"- {key}: not available")
            elif isinstance(value, (dict, list)):
                lines.append(f"- {key}: {len(value)} item(s) returned")
            else:
                lines.append(f"- {key}: {value}")
        lines.append("")
        lines.append(
            "This is retrieved data, not a new assessment. "
            "Human review is required before any operational action."
        )
        return "\n".join(lines)

    async def chat_completion_stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        response = await self.chat_completion(messages, tools, temperature, max_tokens, top_p)
        if response.tool_calls:
            yield "[tool call pending]"
            return
        # Emit in small chunks so streaming consumers behave realistically.
        for token in re.findall(r"\S+\s*", response.content) or [response.content]:
            yield token
