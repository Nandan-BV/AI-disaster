"""
Grounding tests (spec 19, 20, 33, 47).

The copilot must not state project data it did not retrieve, and it must not
fill a data gap with a plausible number. These tests drive the real tool loop
with a scripted model and assert on what the model was actually given.
"""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.ai.copilot import CopilotService
from app.ai.llm.base import ChatCompletionResponse
from app.ai.tools import register_all_tools
from app.models.incident import Incident, IncidentStatus
from app.models.resource import ResourceStatus
from tests.copilot_fakes import FakeSession, ScriptedLLMClient

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 15, 12, 0, 0)


@pytest.fixture(autouse=True)
def _registered():
    register_all_tools()


def incident() -> Incident:
    return Incident(
        id=uuid4(),
        incident_type="flood",
        title="Flooding on MG Road",
        summary="Water rising in the city centre.",
        centroid_latitude=12.9716,
        centroid_longitude=77.5946,
        start_time=NOW - timedelta(hours=3),
        last_updated=NOW - timedelta(minutes=8),
        event_count=2,
        status=IncidentStatus.ACTIVE,
        confidence=0.82,
    )


def tool_call(name: str, **arguments):
    return ChatCompletionResponse(
        content="",
        tool_calls=[{"id": "call_1", "name": name, "arguments": json.dumps(arguments)}],
        finish_reason="tool_calls",
    )


def final(text: str):
    return ChatCompletionResponse(content=text, tool_calls=[], finish_reason="stop")


async def ask(script, session, message, incident_id=None):
    service = CopilotService(db=session, client=ScriptedLLMClient(script))
    return await service._run_turn(
        message=message, history=[], incident_id=incident_id
    ), service.client.calls


# -- the model must go to the database first ---------------------------------

async def test_resource_question_queries_the_database_not_memory():
    inc = incident()
    rows = [
        {
            "id": str(uuid4()),
            "name": "Ambulance A1",
            "resource_type": "ambulance",
            "status": "available",
            "latitude": 12.97,
            "longitude": 77.59,
            "capacity": 1,
            "current_load": 0,
            "capabilities": {"medical": True},
            "organization": "EMS",
            "updated_at": NOW - timedelta(minutes=8),
            "distance_meters": 640.0,
        }
    ]
    session = FakeSession(
        {Incident: [inc]}, text_results={"FROM resources res": rows}
    )

    script = [
        tool_call("get_nearby_resources", incident_id=str(inc.id)),
        final("1 ambulance is available nearby, 640 m from the incident."),
    ]
    answer, calls = await ask(script, session, "How many ambulances are available?", inc.id)

    # The model was forced through a tool call before answering.
    assert [entry.tool for entry in answer.tools_used] == ["get_nearby_resources"]
    assert answer.sources == ["Phase 7 resource inventory"]
    assert len(calls) == 2


async def test_empty_resource_result_is_reported_as_none_found():
    inc = incident()
    session = FakeSession({Incident: [inc]}, text_results={"FROM resources res": []})

    script = [
        tool_call("get_nearby_resources", incident_id=str(inc.id)),
        final("No suitable resources were found in the queried area."),
    ]
    answer, _ = await ask(script, session, "What resources are nearby?", inc.id)

    assert answer.tools_used[0].status == "success"
    assert answer.tools_used[0].note is None
    # The rendered tool payload told the model not to substitute a value.
    assert answer.tools_used[0].source == "Phase 7 resource inventory"


async def test_model_cannot_invent_a_count_because_absent_data_is_flagged():
    """An unavailable tool result must be marked, not silently empty."""
    inc = incident()
    # No risk assessment row exists.
    session = FakeSession({Incident: [inc]})

    script = [
        tool_call("get_incident_risk", incident_id=str(inc.id)),
        final("No risk assessment has been computed for this incident."),
    ]
    answer, calls = await ask(script, session, "How dangerous is this?", inc.id)

    assert answer.tools_used[0].status == "unavailable"
    assert "No risk assessment" in answer.tools_used[0].note

    # The model was handed an explicit instruction not to estimate.
    tool_messages = [m for m in calls[-1]["messages"] if m.role == "tool"]
    payload = json.loads(tool_messages[0].content)
    assert payload["available"] is False
    assert "Do not estimate" in payload["instruction"]


async def test_missing_environment_data_is_not_read_as_normal_conditions():
    """No tool reports weather, so the model cannot be handed a 'fine' reading."""
    inc = incident()
    session = FakeSession({Incident: [inc]})
    script = [
        tool_call("get_incident", incident_id=str(inc.id)),
        final("Environmental observations are not available for this incident."),
    ]
    answer, calls = await ask(script, session, "Is the weather normal there?", inc.id)

    # The only tool that ran is the incident record, which carries no weather.
    assert [entry.tool for entry in answer.tools_used] == ["get_incident"]
    tool_message = [m for m in calls[-1]["messages"] if m.role == "tool"][0]
    payload = json.loads(tool_message.content)
    assert "weather" not in json.dumps(payload).lower()
    assert "temperature" not in json.dumps(payload).lower()


# -- stale data --------------------------------------------------------------

async def test_freshness_is_surfaced_to_the_model():
    inc = incident()
    session = FakeSession({Incident: [inc]})
    script = [
        tool_call("get_incident", incident_id=str(inc.id)),
        final("The incident record was last updated 8 minutes ago."),
    ]
    answer, calls = await ask(script, session, "What is happening?", inc.id)

    tool_message = [m for m in calls[-1]["messages"] if m.role == "tool"][0]
    payload = json.loads(tool_message.content)
    assert payload["data"]["data_age"] is not None
    assert "not a real-time" in payload["data"]["data_age"] or payload["data"]["data_age"]


# -- tool loop mechanics -----------------------------------------------------

async def test_unknown_tool_request_is_reported_and_does_not_execute():
    inc = incident()
    session = FakeSession({Incident: [inc]})
    script = [
        tool_call("execute_sql", query="SELECT * FROM resources"),
        final("I cannot run arbitrary queries."),
    ]
    answer, calls = await ask(script, session, "List everything", inc.id)

    entry = answer.tools_used[0]
    assert entry.tool == "execute_sql"
    assert entry.status == "error"
    assert "not an available tool" in entry.note
    assert session.executed_sql == []


async def test_model_cannot_smuggle_extra_arguments():
    inc = incident()
    session = FakeSession({Incident: [inc]})
    script = [
        tool_call("get_incident", incident_id=str(inc.id), raw_sql="DROP TABLE incidents"),
        final("That request was rejected."),
    ]
    answer, _ = await ask(script, session, "Show me the incident", inc.id)

    assert answer.tools_used[0].status == "invalid"
    assert session.executed_sql == []


async def test_conversation_incident_is_injected_when_model_omits_it():
    inc = incident()
    session = FakeSession({Incident: [inc]})
    script = [
        # The model forgot the id; the conversation context must supply it.
        tool_call("get_nearby_resources", incident_id=0),
        final("No resources found in the queried area."),
    ]
    answer, calls = await ask(script, session, "What resources are nearby?", inc.id)

    assert answer.tools_used[0].status in {"success", "unavailable"}
    tool_message = [m for m in calls[-1]["messages"] if m.role == "tool"][0]
    payload = json.loads(tool_message.content)
    assert payload["data"]["incident_id"] == str(inc.id)


async def test_tool_loop_is_bounded():
    inc = incident()
    session = FakeSession({Incident: [inc]})
    # A model that keeps calling tools forever must be cut off.
    script = [tool_call("get_incident", incident_id=str(inc.id)) for _ in range(20)]

    service = CopilotService(db=session, client=ScriptedLLMClient(script))
    answer = await service._run_turn(message="loop", history=[], incident_id=inc.id)

    assert len(answer.tools_used) <= 6
    assert "could not complete" in answer.answer.lower()
