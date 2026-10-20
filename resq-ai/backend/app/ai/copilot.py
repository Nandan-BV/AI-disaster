"""
Copilot orchestration.

Responsibilities:

* Resolve which incident a question refers to, so "what resources are nearby?"
  works after the operator has discussed incident 42 (spec 22).
* Run a bounded tool-calling loop against the fixed registry.
* Keep system instructions, operator instructions, and untrusted tool data in
  separate, explicitly labelled positions (spec 36).
* Emit a safe tool trace containing no SQL, credentials, or prompt text
  (spec 26).
* Persist the conversation for history retrieval (spec 23, 25).

The loop is bounded by ``max_iterations`` so a confused model cannot spin.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.llm import get_llm_client
from app.ai.llm.base import CopilotLLMError, LLMClient, Message
from app.ai.tool_registry import (
    PermissionDeniedError,
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
    tool_registry,
)
from app.ai.tools import register_all_tools
from app.ai.tools.common import ToolResult, use_session
from app.config import settings
from app.models.copilot import CopilotConversation, CopilotMessage, MessageRole

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "copilot_system.txt"

_SYSTEM_PROMPT: Optional[str] = None

# Requests the copilot must refuse and redirect rather than execute.
#
# These match *intent to act*, not topic keywords. "How many ambulances are
# available?" must still reach the resource tool even though it is about
# dispatching, so the patterns key on imperative or status-changing verbs
# rather than on the nouns involved.
#
# The verbs split into two groups. UNAMBIGUOUS_REFUSAL_PATTERNS are terms that
# only appear when someone wants something done; a question containing one is
# still a request for that thing. AMBIGUOUS_REFUSAL_PATTERNS are verbs that also
# appear in ordinary capacity or availability questions ("how many ambulances
# can we send to MG Road?"), so they are checked against _INQUIRY_RE first.
UNAMBIGUOUS_REFUSAL_PATTERNS = (
    r"\bdispatch\b",
    r"\bde-?deploy\b",
    r"\bapprove\b",
    r"\bapproval\b",
    r"\bmark\b.*\b(?:deployed|available|unavailable|approved)\b",
    r"\bchange\b.*\bstatus\b",
    r"\bset\b.*\bstatus\b",
    r"\bupdate\b.*\b(?:status|record)\b",
    r"\bdelete\b",
    r"\bbypass\b",
    r"\bskip\b.*\bapproval\b",
    r"\bwithout (?:approval|human)\b",
    r"\bgo ahead and\b",
)

AMBIGUOUS_REFUSAL_PATTERNS = (
    r"\bsend\b",
    r"\breject\b",
    r"\bactivate\b",
    r"\bcontact\b",
    r"\bcall (?:out to|emergency)\b",
    r"\bnotify\b",
    r"\bassign\b",
)

# An inquiry reads as a question about capacity, availability, or status rather
# than a command. When one of these is present, an ambiguous verb is treated as
# something the operator is asking about, not asking for.
_INQUIRY_PATTERNS = (
    r"\bhow (?:many|much)\b",
    r"\bwhat (?:is|are|would|does|do)\b",
    r"\bwhich\b",
    r"\bwho\b",
    r"\bwhere\b",
    r"\bcan (?:we|i|you)\b",
    r"\bcould (?:we|i|you)\b",
    r"\bdo (?:we|i|you)\b",
    r"\bdoes (?:we|i|you)\b",
    r"\bshould (?:we|i|you)\b",
    r"\bwould (?:we|i|you)\b",
    r"\bis it possible\b",
    r"\bcan\b.*\bavailable\b",
    r"\bavailable\b",
    r"\bin stock\b",
    r"\bcapacity\b",
    r"\benough\b",
    r"\bcould fit\b",
    r"\bwill fit\b",
)

_UNAMBIGUOUS_REFUSAL_RE = tuple(
    re.compile(p, re.IGNORECASE) for p in UNAMBIGUOUS_REFUSAL_PATTERNS
)
_AMBIGUOUS_REFUSAL_RE = tuple(
    re.compile(p, re.IGNORECASE) for p in AMBIGUOUS_REFUSAL_PATTERNS
)
_INQUIRY_RE = tuple(re.compile(p, re.IGNORECASE) for p in _INQUIRY_PATTERNS)


def is_operational_request(text: str) -> bool:
    """Whether the operator asked for an action rather than information.

    An unambiguous action verb is always a request for that action. An ambiguous
    verb only counts when the message is not phrased as an inquiry, so
    "how many ambulances can we send to MG Road?" stays answerable while
    "send two ambulances to MG Road" is refused.
    """
    if any(p.search(text) for p in _UNAMBIGUOUS_REFUSAL_RE):
        return True

    if not any(p.search(text) for p in _AMBIGUOUS_REFUSAL_RE):
        return False

    return not any(p.search(text) for p in _INQUIRY_RE)

MAX_TOOL_ITERATIONS = 6
NO_GROUNDED_DATA_ANSWER = (
    "I could not retrieve supporting RESQ-AI data, so I cannot provide a "
    "grounded answer. Select an incident or retry when the relevant data is available."
)


def load_system_prompt() -> str:
    """Read the system prompt from disk, cached after first read."""
    global _SYSTEM_PROMPT
    if _SYSTEM_PROMPT is None:
        try:
            _SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - packaging error
            raise CopilotLLMError(
                "The copilot system prompt is missing from the deployment."
            ) from exc
    return _SYSTEM_PROMPT


@dataclass
class ToolTraceEntry:
    """One safe, displayable step of the tool trace."""

    tool: str
    status: str  # success | unavailable | error | denied | invalid
    source: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {"tool": self.tool, "status": self.status}
        if self.source:
            payload["source"] = self.source
        if self.note:
            payload["note"] = self.note
        return payload


@dataclass
class CopilotAnswer:
    """Result of one copilot turn."""

    answer: str
    sources: List[str] = field(default_factory=list)
    tools_used: List[ToolTraceEntry] = field(default_factory=list)
    incident_id: Optional[UUID] = None
    model_name: Optional[str] = None
    refused: bool = False
    uncertainty: List[str] = field(default_factory=list)


class CopilotService:
    """Answers operator questions using the fixed toolset."""

    def __init__(self, db: AsyncSession, client: Optional[LLMClient] = None) -> None:
        self._db = db
        self._client = client
        register_all_tools()

    @property
    def client(self) -> LLMClient:
        return self._client or get_llm_client()

    # -- conversation context -------------------------------------------
    async def _get_or_create_conversation(
        self, session_id: str, incident_id: Optional[UUID]
    ) -> CopilotConversation:
        conversation = (
            await self._db.execute(
                select(CopilotConversation).where(CopilotConversation.session_id == session_id)
            )
        ).scalar_one_or_none()

        if conversation is None:
            conversation = CopilotConversation(session_id=session_id, incident_id=incident_id)
            self._db.add(conversation)
            await self._db.flush()
            return conversation

        # An explicit incident in the request updates the pinned context;
        # otherwise keep whatever the operator selected earlier.
        if incident_id is not None:
            conversation.incident_id = incident_id
        await self._db.flush()
        return conversation

    async def _history(self, conversation: CopilotConversation) -> List[Message]:
        """Recent user/assistant turns, bounded by configuration."""
        rows = (
            await self._db.execute(
                select(CopilotMessage)
                .where(CopilotMessage.conversation_id == conversation.id)
                .order_by(CopilotMessage.sequence.desc())
                .limit(settings.COPILOT_MAX_HISTORY_MESSAGES)
            )
        ).scalars().all()

        messages: List[Message] = []
        for row in reversed(rows):
            if row.role in (MessageRole.USER, MessageRole.ASSISTANT):
                messages.append(Message(role=row.role.value, content=row.content))
        return messages

    # -- persistence -----------------------------------------------------
    async def _append_message(
        self,
        conversation: CopilotConversation,
        role: MessageRole,
        content: str,
        sequence: int,
        tool_name: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
        tool_output: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._db.add(
            CopilotMessage(
                conversation_id=conversation.id,
                role=role,
                content=content,
                sequence=sequence,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
            )
        )

    async def _next_sequence(self, conversation: CopilotConversation) -> int:
        from sqlalchemy import func

        current = (
            await self._db.execute(
                select(func.coalesce(func.max(CopilotMessage.sequence), 0)).where(
                    CopilotMessage.conversation_id == conversation.id
                )
            )
        ).scalar_one()
        return int(current) + 1

    # -- argument hardening ----------------------------------------------
    @staticmethod
    def _apply_incident_context(
        tool_name: str, arguments: Dict[str, Any], incident_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """Fill in the conversation's incident unless the model set one.

        Also neutralises a missing/zero id, which the model sometimes emits when
        the operator referred to "this incident" without repeating the id.
        """
        arguments = dict(arguments or {})
        if incident_id is None:
            return arguments
        tool = tool_registry.get(tool_name)
        if "incident_id" not in (tool.definition.parameters.get("properties") or {}):
            return arguments
        current = arguments.get("incident_id")
        if current in (None, "", 0, "0"):
            arguments["incident_id"] = str(incident_id)
        return arguments

    # -- refusal ---------------------------------------------------------
    @staticmethod
    def _looks_like_prohibited_request(message: str) -> bool:
        return is_operational_request(message)

    # -- main loop -------------------------------------------------------
    async def answer(
        self,
        session_id: str,
        message: str,
        incident_id: Optional[UUID] = None,
    ) -> CopilotAnswer:
        conversation = await self._get_or_create_conversation(session_id, incident_id)
        sequence = await self._next_sequence(conversation)
        await self._append_message(conversation, MessageRole.USER, message, sequence)
        sequence += 1

        # Tool results are rendered as labelled untrusted data, never placed in
        # an instruction position (spec 36).
        answer = await self._run_turn(
            message=message,
            history=await self._history(conversation),
            incident_id=conversation.incident_id,
        )

        await self._append_message(
            conversation,
            MessageRole.ASSISTANT,
            answer.answer,
            sequence,
            tool_output={
                "tools_used": [entry.to_dict() for entry in answer.tools_used],
                "sources": answer.sources,
            },
        )
        await self._db.commit()

        answer.incident_id = conversation.incident_id
        return answer

    async def answer_stream(
        self,
        session_id: str,
        message: str,
        incident_id: Optional[UUID] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a grounded answer and persist it after generation completes."""
        conversation = await self._get_or_create_conversation(session_id, incident_id)
        sequence = await self._next_sequence(conversation)
        await self._append_message(conversation, MessageRole.USER, message, sequence)
        sequence += 1

        history = await self._history(conversation)
        if history and history[-1].role == MessageRole.USER.value:
            history.pop()

        if self._looks_like_prohibited_request(message):
            answer = await self._operational_redirect(conversation.incident_id, history)
            if answer is not None:
                async for token in self._text_chunks(answer.answer):
                    yield {"type": "token", "token": token}
                await self._persist_streamed_answer(conversation, answer, sequence)
                yield {"type": "done", **self._stream_metadata(answer)}
                return

        prompt: List[Message] = [
            Message(role="system", content=load_system_prompt()),
            *history,
            Message(role="user", content=message),
        ]
        trace: List[ToolTraceEntry] = []
        sources: List[str] = []
        uncertainty: List[str] = []
        model_name = self.client.model_name
        answer_text = ""

        with use_session(self._db):
            for _ in range(MAX_TOOL_ITERATIONS):
                response = await self.client.chat_completion(
                    messages=prompt,
                    tools=tool_registry.definitions(),
                )
                if response.tool_calls:
                    prompt.append(
                        Message(
                            role="assistant",
                            content=response.content or "",
                            tool_calls=response.tool_calls,
                        )
                    )
                    for call in response.tool_calls:
                        rendered, entry, _ = await self._run_tool(
                            call, conversation.incident_id
                        )
                        trace.append(entry)
                        if entry.source and entry.source not in sources:
                            sources.append(entry.source)
                        if entry.note and entry.note not in uncertainty:
                            uncertainty.append(entry.note)
                        prompt.append(
                            Message(
                                role="tool",
                                content=rendered,
                                name=entry.tool,
                                tool_call_id=call.get("id"),
                            )
                        )
                    continue

                if not trace:
                    answer_text = NO_GROUNDED_DATA_ANSWER
                    uncertainty.append("No supporting RESQ-AI data was retrieved.")
                    async for token in self._text_chunks(answer_text):
                        yield {"type": "token", "token": token}
                    break

                async for token in self.client.chat_completion_stream(
                    messages=prompt,
                    tools=None,
                ):
                    if token:
                        answer_text += token
                        yield {"type": "token", "token": token}
                if not answer_text:
                    answer_text = response.content or (
                        "The copilot could not produce an answer from the available data."
                    )
                    async for token in self._text_chunks(answer_text):
                        yield {"type": "token", "token": token}
                break
            else:
                answer_text = (
                    "I could not complete this request within the allowed number of "
                    "data lookups. Please narrow the question or ask about one aspect at a time."
                )
                async for token in self._text_chunks(answer_text):
                    yield {"type": "token", "token": token}

        answer = CopilotAnswer(
            answer=answer_text,
            sources=sources,
            tools_used=trace,
            incident_id=conversation.incident_id,
            model_name=model_name,
            uncertainty=uncertainty,
        )
        await self._persist_streamed_answer(conversation, answer, sequence)
        yield {"type": "done", **self._stream_metadata(answer)}

    async def _persist_streamed_answer(
        self,
        conversation: CopilotConversation,
        answer: CopilotAnswer,
        sequence: int,
    ) -> None:
        await self._append_message(
            conversation,
            MessageRole.ASSISTANT,
            answer.answer,
            sequence,
            tool_output={
                "tools_used": [entry.to_dict() for entry in answer.tools_used],
                "sources": answer.sources,
            },
        )
        await self._db.commit()

    @staticmethod
    def _stream_metadata(answer: CopilotAnswer) -> Dict[str, Any]:
        return {
            "incident_id": str(answer.incident_id) if answer.incident_id else None,
            "sources": answer.sources,
            "tools_used": [entry.to_dict() for entry in answer.tools_used],
            "uncertainty": answer.uncertainty,
            "model_name": answer.model_name,
            "refused_action": answer.refused,
        }

    @staticmethod
    async def _text_chunks(text: str) -> AsyncGenerator[str, None]:
        import asyncio
        import re

        for chunk in re.findall(r"\S+\s*", text):
            yield chunk
            await asyncio.sleep(0)

    async def _run_turn(
        self,
        message: str,
        history: List[Message],
        incident_id: Optional[UUID],
    ) -> CopilotAnswer:
        # The session is bound here, not by the caller, so every code path that
        # enters the tool loop has a session available to the tools.
        with use_session(self._db):
            return await self._run_turn_bound(message, history, incident_id)

    async def _run_turn_bound(
        self,
        message: str,
        history: List[Message],
        incident_id: Optional[UUID],
    ) -> CopilotAnswer:
        # A request to dispatch/approve/mutate is answered from data, never acted on.
        if self._looks_like_prohibited_request(message):
            guidance = await self._operational_redirect(incident_id, history)
            if guidance is not None:
                return guidance

        conversation: List[Message] = [
            Message(role="system", content=load_system_prompt())
        ]
        conversation.extend(history)
        conversation.append(Message(role="user", content=message))

        trace: List[ToolTraceEntry] = []
        sources: List[str] = []
        uncertainty: List[str] = []
        model_name = self.client.model_name

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                response = await self.client.chat_completion(
                    messages=conversation,
                    tools=tool_registry.definitions(),
                )
            except CopilotLLMError:
                raise

            if not response.tool_calls:
                if not trace:
                    return CopilotAnswer(
                        answer=NO_GROUNDED_DATA_ANSWER,
                        incident_id=incident_id,
                        model_name=model_name,
                        uncertainty=["No supporting RESQ-AI data was retrieved."],
                    )
                return CopilotAnswer(
                    answer=response.content
                    or "The copilot could not produce an answer from the available data.",
                    sources=sources,
                    tools_used=trace,
                    model_name=model_name,
                    uncertainty=uncertainty,
                )

            conversation.append(
                Message(role="assistant", content=response.content or "", tool_calls=response.tool_calls)
            )

            for call in response.tool_calls:
                rendered, entry, result = await self._run_tool(call, incident_id)
                trace.append(entry)
                if entry.source and entry.source not in sources:
                    sources.append(entry.source)
                if entry.note and entry.note not in uncertainty:
                    uncertainty.append(entry.note)
                conversation.append(
                    Message(
                        role="tool",
                        content=rendered,
                        name=entry.tool,
                        tool_call_id=call.get("id"),
                    )
                )

        logger.warning("Copilot tool loop hit the iteration cap (%d)", MAX_TOOL_ITERATIONS)
        return CopilotAnswer(
            answer=(
                "I could not complete this request within the allowed number of "
                "data lookups. Please narrow the question or ask about one "
                "aspect at a time."
            ),
            sources=sources,
            tools_used=trace,
            model_name=model_name,
            uncertainty=uncertainty,
        )

    async def _run_tool(self, call: Dict[str, Any], incident_id: Optional[UUID]):
        """Execute one requested tool and render its result for the model."""
        tool_name = call.get("name") or ""
        raw_arguments = call.get("arguments") or "{}"

        try:
            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
        except (json.JSONDecodeError, TypeError):
            note = "The model produced unreadable tool arguments; nothing was run."
            return (
                f"TOOL_ERROR {tool_name}: {note}",
                ToolTraceEntry(tool=tool_name or "unknown", status="invalid", note=note),
                None,
            )

        if not tool_registry.has(tool_name):
            note = f"{tool_name!r} is not an available tool."
            return (
                f"TOOL_ERROR {tool_name}: {note}",
                ToolTraceEntry(tool=tool_name or "unknown", status="error", note=note),
                None,
            )

        arguments = self._apply_incident_context(tool_name, arguments, incident_id)
        tool = tool_registry.get(tool_name)

        try:
            outcome = await tool_registry.invoke(tool_name, arguments)
        except PermissionDeniedError as exc:
            return (
                f"TOOL_DENIED {tool_name}: {exc}",
                ToolTraceEntry(
                    tool=tool_name,
                    status="denied",
                    source=tool.source,
                    note="This action requires a human operator and was not performed.",
                ),
                None,
            )
        except ToolValidationError as exc:
            return (
                f"TOOL_INVALID_INPUT {tool_name}: {exc}",
                ToolTraceEntry(tool=tool_name, status="invalid", source=tool.source, note=str(exc)),
                None,
            )
        except ToolNotFoundError as exc:
            return (
                f"TOOL_NOT_FOUND {tool_name}: {exc}",
                ToolTraceEntry(tool=tool_name, status="error", note=str(exc)),
                None,
            )
        except ToolError as exc:
            return (
                f"TOOL_ERROR {tool_name}: {exc}",
                ToolTraceEntry(tool=tool_name, status="error", source=tool.source, note=str(exc)),
                None,
            )

        result = _coerce_result(outcome)
        status = "success" if result.available else "unavailable"
        rendered = _render_tool_result(tool_name, result)
        entry = ToolTraceEntry(
            tool=tool_name,
            status=status,
            source=result.source,
            note=result.notes if not result.available else None,
        )
        return rendered, entry, result

    async def _operational_redirect(
        self, incident_id: Optional[UUID], history: List[Message]
    ) -> Optional[CopilotAnswer]:
        """Answer a dispatch/approval request with data instead of acting."""
        if incident_id is None:
            return CopilotAnswer(
                answer=(
                    "I can't dispatch, approve, or change anything - those are "
                    "human operator actions. Select an incident and I can show you "
                    "the current recommendations and available resources."
                ),
                refused=True,
            )

        trace: List[ToolTraceEntry] = []
        sources: List[str] = []
        blocks: List[str] = []

        for tool_name in ("get_optimization_result", "get_nearby_resources"):
            arguments = {"incident_id": str(incident_id)}
            try:
                outcome = await tool_registry.invoke(tool_name, arguments)
            except ToolError:
                continue
            result = _coerce_result(outcome)
            trace.append(
                ToolTraceEntry(
                    tool=tool_name,
                    status="success" if result.available else "unavailable",
                    source=result.source,
                    note=result.notes if not result.available else None,
                )
            )
            if result.source not in sources:
                sources.append(result.source)
            blocks.append(_render_tool_result(tool_name, result))

        return CopilotAnswer(
            answer=(
                "I can't dispatch, approve, or change a resource status - that "
                "requires a human operator. Here is the current information for "
                "the selected incident:\n\n"
                + "\n\n".join(blocks)
                + "\n\nAny allocation remains a recommendation until an operator "
                "approves it."
            ),
            sources=sources,
            tools_used=trace,
            refused=True,
        )


def _coerce_result(outcome: Any) -> ToolResult:
    """Accept a ToolResult or a plain dict from a handler."""
    if isinstance(outcome, ToolResult):
        return outcome
    if isinstance(outcome, dict):
        return ToolResult(source="backend", data=outcome)
    return ToolResult(source="backend", data={"value": str(outcome)})


def _render_tool_result(tool_name: str, result: ToolResult) -> str:
    """Serialise a tool result as explicitly untrusted data for the model."""
    if not result.available:
        return json.dumps(
            {
                "tool": tool_name,
                "available": False,
                "source": result.source,
                "unavailable_reason": result.notes,
                "instruction": (
                    "Report this as unavailable. Do not estimate, infer, or "
                    "substitute a value."
                ),
            }
        )

    return json.dumps(
        {
            "tool": tool_name,
            "available": True,
            "source": result.source,
            "retrieved_at": result.retrieved_at.isoformat() if result.retrieved_at else None,
            "data": result.data,
            "notes": result.notes,
        }
    )
