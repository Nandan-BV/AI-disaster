"""
Registry of the fixed tools the copilot may call.

Design constraints this module enforces (spec 37, 38, 17):

* Tools are declared in code. There is no path from model output to SQL, and no
  ``execute_sql`` entry point exists anywhere in the copilot.
* Every tool has a Pydantic input model; arguments are validated *before* the
  handler touches the database.
* Every tool declares its permission class, and the registry refuses to invoke
  a controlled action unless it is explicitly enabled in configuration.
* Unknown tool names are an error, never a silent no-op.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from app.ai.llm.base import ToolDefinition

logger = logging.getLogger(__name__)


class ToolPermission(str, Enum):
    """How much authority a tool carries."""

    READ_ONLY = "read_only"
    CONTROLLED_ACTION = "controlled_action"


@dataclass
class RegisteredTool:
    """A tool plus the metadata the registry needs to police it."""

    definition: ToolDefinition
    input_model: type[BaseModel]
    permission: ToolPermission
    source: str = "backend"  # human-readable provenance for the response
    handler: Callable[..., Awaitable[Any]] = field(repr=False, default=None)  # type: ignore[assignment]

    @property
    def name(self) -> str:
        return self.definition.name


class ToolError(Exception):
    """A tool failed in a way the copilot may report to the operator."""


class ToolValidationError(ToolError):
    """Tool input failed validation; nothing was executed."""


class ToolNotFoundError(ToolError):
    """The model asked for a tool that does not exist."""


class PermissionDeniedError(ToolError):
    """A tool is not permitted to run in the current configuration."""


class ToolRegistry:
    """Holds the copilot's fixed toolset."""

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    # -- registration ----------------------------------------------------
    def register(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        handler: Callable[..., Awaitable[Any]],
        permission: ToolPermission = ToolPermission.READ_ONLY,
        source: str = "backend",
    ) -> RegisteredTool:
        """Register a tool, deriving its JSON Schema from ``input_model``."""
        if name in self._tools:
            logger.warning("Replacing already-registered tool %s", name)

        definition = ToolDefinition(
            name=name,
            description=description,
            parameters=input_model.model_json_schema(),
            handler=handler,
        )
        tool = RegisteredTool(
            definition=definition,
            input_model=input_model,
            permission=permission,
            source=source,
            handler=handler,
        )
        self._tools[name] = tool
        return tool

    # -- lookup ----------------------------------------------------------
    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(
                f"Unknown tool {name!r}. Available tools: {sorted(self._tools)}"
            ) from exc

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return sorted(self._tools)

    def definitions(self) -> List[ToolDefinition]:
        """Tool definitions to advertise to the model.

        Controlled actions are withheld while they are disabled. The Phase 9
        spec requires the optimization tool to be exposed only when the
        optimization pipeline is working, and advertising a tool that will
        always be refused only invites the model to attempt it.
        """
        from app.config import settings

        allowed = []
        for name in sorted(self._tools):
            tool = self._tools[name]
            if (
                tool.permission is ToolPermission.CONTROLLED_ACTION
                and not settings.COPILOT_ALLOW_CONTROLLED_ACTIONS
            ):
                continue
            allowed.append(tool.definition)
        return allowed

    def sources(self) -> Dict[str, str]:
        return {name: self._tools[name].source for name in sorted(self._tools)}

    # -- invocation ------------------------------------------------------
    async def invoke(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """Validate arguments and run a tool.

        Raises:
            ToolNotFoundError: unknown tool name.
            PermissionDeniedError: controlled action disabled by configuration.
            ToolValidationError: input failed Pydantic validation.
            ToolError: the handler itself failed.
        """
        tool = self.get(name)
        self._check_permission(tool)

        raw = arguments or {}
        if not isinstance(raw, dict):
            raise ToolValidationError(f"Tool {name} expects an object of arguments.")

        try:
            validated = tool.input_model(**raw)
        except ValidationError as exc:
            # Reject before any database access (spec 38).
            raise ToolValidationError(
                f"Invalid input for {name}: {_format_validation_error(exc)}"
            ) from exc

        try:
            return await tool.handler(**validated.model_dump())
        except ToolError:
            raise
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator, not swallowed
            logger.exception("Tool %s failed", name)
            raise ToolError(f"Tool {name} could not complete: {exc}") from exc

    def _check_permission(self, tool: RegisteredTool) -> None:
        """Controlled actions are opt-in; read-only tools always run."""
        if tool.permission is ToolPermission.READ_ONLY:
            return

        from app.config import settings

        if not settings.COPILOT_ALLOW_CONTROLLED_ACTIONS:
            raise PermissionDeniedError(
                f"Tool {tool.name!r} is a controlled action and is disabled. "
                "A human operator must run it from the optimization interface."
            )


def _format_validation_error(exc: ValidationError) -> str:
    parts = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", ())) or "input"
        parts.append(f"{location}: {error.get('msg')}")
    return "; ".join(parts)


# Process-wide registry. Populated by app.ai.tools.register_all_tools().
tool_registry = ToolRegistry()
