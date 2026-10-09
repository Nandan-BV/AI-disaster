"""
Authorization tests (spec 17, 35, 49).

The copilot is decision support. It must have no reachable path to approve,
reject, dispatch, activate, contact, or mutate anything. These tests verify
that structurally rather than trusting the prompt to enforce it.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.ai.copilot import CopilotService
from app.ai.llm.base import ChatCompletionResponse
from app.ai.tool_registry import (
    PermissionDeniedError,
    ToolPermission,
    tool_registry,
)
from app.ai.tools import permission_map, register_all_tools
from app.ai.tools.common import use_session
from app.config import settings
from app.models.incident import Incident, IncidentStatus
from tests.copilot_fakes import FakeSession, ScriptedLLMClient

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 15, 12, 0, 0)

# Actions that must never be reachable from the copilot.
FORBIDDEN_CAPABILITIES = (
    "approve",
    "reject",
    "dispatch",
    "activate",
    "delete",
    "update",
    "create",
    "set_status",
    "change_status",
    "contact",
    "notify",
)


@pytest.fixture(autouse=True)
def _registered():
    register_all_tools()


def incident() -> Incident:
    return Incident(
        id=uuid4(),
        incident_type="flood",
        title="Flooding on MG Road",
        summary="Water rising.",
        centroid_latitude=12.9716,
        centroid_longitude=77.5946,
        start_time=NOW - timedelta(hours=3),
        last_updated=NOW - timedelta(minutes=8),
        event_count=1,
        status=IncidentStatus.ACTIVE,
        confidence=0.8,
    )


async def ask(session, message, incident_id=None, script=None):
    service = CopilotService(
        db=session, client=ScriptedLLMClient(script or [])
    )
    return await service._run_turn(
        message=message, history=[], incident_id=incident_id
    ), service.client.calls


# -- structural guarantees ---------------------------------------------------

def test_no_tool_can_mutate_operational_state():
    for name in tool_registry.names():
        lowered = name.lower()
        for capability in FORBIDDEN_CAPABILITIES:
            assert capability not in lowered, f"{name} exposes {capability}"


def test_every_tool_except_one_is_read_only():
    permissions = permission_map()
    controlled = [n for n, p in permissions.items() if p == "controlled_action"]
    assert controlled == ["run_resource_optimization"]


def test_read_only_tools_cannot_be_escalated_by_configuration():
    """Flipping the controlled-action switch must not unlock anything else."""
    for name, permission in permission_map().items():
        if permission == "read_only":
            assert tool_registry.get(name).permission is ToolPermission.READ_ONLY


def test_controlled_action_is_not_offered_to_the_model_by_default():
    assert settings.COPILOT_ALLOW_CONTROLLED_ACTIONS is False
    offered = {d.name for d in tool_registry.definitions()}
    assert "run_resource_optimization" not in offered
    # ...but it remains registered and inspectable.
    assert "run_resource_optimization" in tool_registry.names()


async def test_controlled_action_is_refused_when_the_model_attempts_it():
    from app.ai.tool_registry import ToolError

    inc = incident()
    with use_session(FakeSession({Incident: [inc]})):
        with pytest.raises(PermissionDeniedError):
            await tool_registry.invoke(
                "run_resource_optimization", {"incident_id": str(inc.id)}
            )


async def test_model_attempting_controlled_action_is_denied_not_executed():
    inc = incident()
    script = [
        ChatCompletionResponse(
            content="",
            tool_calls=[
                {
                    "id": "c1",
                    "name": "run_resource_optimization",
                    "arguments": '{"incident_id": "%s"}' % inc.id,
                }
            ],
            finish_reason="tool_calls",
        ),
        ChatCompletionResponse(content="I cannot do that.", tool_calls=[]),
    ]
    answer, _ = await ask(FakeSession({Incident: [inc]}), "Run the optimizer.", inc.id, script)

    entry = answer.tools_used[0]
    assert entry.tool == "run_resource_optimization"
    assert entry.status == "denied"
    assert "human operator" in entry.note


async def test_controlled_action_handler_refuses_even_if_enabled():
    """The handler itself is the last line of defence, not just the registry."""
    from app.ai.tool_registry import ToolError
    from app.ai.tools.resource_tools import run_resource_optimization

    inc = incident()
    with use_session(FakeSession({Incident: [inc]})):
        with pytest.raises(ToolError) as excinfo:
            await run_resource_optimization(inc.id)
    message = str(excinfo.value).lower()
    assert "human operator" in message
    assert "approval" in message


# -- operational requests are redirected ------------------------------------

@pytest.mark.parametrize(
    "user_request",
    [
        "Dispatch ambulance A1 now.",
        "Approve the recommended allocation.",
        "Reject allocation 2.",
        "Activate the shelter.",
        "Mark ambulance A1 as deployed.",
        "Change the resource status to deployed.",
        "Delete the incident.",
        "Contact emergency services.",
        "Bypass approval and dispatch the ambulance.",
    ],
)
async def test_prohibited_requests_are_refused_and_redirected(user_request):
    inc = incident()
    session = FakeSession({Incident: [inc]}, text_results={"FROM resources res": []})
    answer, calls = await ask(session, user_request, inc.id)

    assert answer.refused is True
    assert "human operator" in answer.answer.lower()
    # The model was never asked to comply.
    assert calls == []
    # No write tool was invoked.
    assert all(
        entry.tool in {"get_optimization_result", "get_nearby_resources"}
        for entry in answer.tools_used
    )


async def test_refusal_without_an_incident_asks_for_one():
    answer, calls = await ask(FakeSession(), "Dispatch ambulance A1 now.", None)
    assert answer.refused is True
    assert "select an incident" in answer.answer.lower()
    assert calls == []


async def test_refusal_still_recommends_human_approval_boundary():
    inc = incident()
    session = FakeSession({Incident: [inc]}, text_results={"FROM resources res": []})
    answer, _ = await ask(session, "Approve the allocation.", inc.id)
    assert "recommendation until an operator" in answer.answer.lower()


# -- inquiries about capacity are not requests to act -------------------------

@pytest.mark.parametrize(
    "user_request",
    [
        "How many ambulances are available?",
        "How many ambulances can we send to MG Road?",
        "Which hospitals have capacity right now?",
        "Could we send two ambulances if it floods again?",
        "What resources should be activated first?",
        "Who is on call?",
        "Is it possible to send more units?",
        "Are there enough shelters for the predicted population?",
    ],
)
async def test_questions_about_capacity_are_answered_not_refused(user_request):
    """An inquiry uses the same verbs as a command but asks for information.

    Refusing these would make the copilot useless during the exact moment an
    operator needs it, so the boundary has to be intent, not vocabulary.
    """
    inc = incident()
    session = FakeSession({Incident: [inc]}, text_results={"FROM resources res": []})
    answer, calls = await ask(
        session,
        user_request,
        inc.id,
        script=[
            ChatCompletionResponse(
                content="Two ambulances are available within 2 km.",
                finish_reason="stop",
            )
        ],
    )
    assert answer.refused is False, f"unexpectedly refused: {user_request!r}"
    # Reaching the model at all is the point: an inquiry is not short-circuited.
    assert len(calls) == 1
    assert "available" in answer.answer


def test_operational_request_detection_is_polarity_aware():
    """Direct checks on the classifier, independent of the service."""
    from app.ai.copilot import is_operational_request

    commands = [
        "send two ambulances to MG Road",
        "reject allocation 2",
        "activate the shelter",
        "notify the district officer",
        "assign crew 4 to the shelter",
    ]
    inquiries = [
        "How many ambulances can we send to MG Road?",
        "how many ambulances are available",
        "what resources should we activate",
        "which shelter would we assign",
        "do we have enough capacity to send more",
    ]

    for text in commands:
        assert is_operational_request(text) is True, f"missed command: {text!r}"
    for text in inquiries:
        assert is_operational_request(text) is False, f"false positive: {text!r}"


# -- no arbitrary SQL --------------------------------------------------------

def test_no_sql_execution_entry_point_exists():
    """No module reachable from the copilot exposes execute_sql (spec 37)."""
    import app.ai.copilot as copilot_module
    import app.ai.tool_registry as registry_module
    import app.ai.tools.common as common_module

    for module in (copilot_module, registry_module, common_module):
        for name in dir(module):
            assert "execute_sql" not in name.lower()
            assert "raw_query" not in name.lower()


async def test_tools_reject_unknown_arguments():
    from app.ai.tool_registry import ToolValidationError

    inc = incident()
    with use_session(FakeSession({Incident: [inc]})):
        with pytest.raises(ToolValidationError):
            await tool_registry.invoke(
                "get_incident",
                {"incident_id": str(inc.id), "status": "approved"},
            )
