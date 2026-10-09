"""
End-to-end copilot scenario (spec 50) and conversation context (spec 22).

Runs the full operator walkthrough against the real tool loop with a scripted
model, asserting that every factual answer is backed by a tool call and that
the conversation remembers the incident.
"""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.ai.copilot import CopilotService
from app.ai.llm.base import ChatCompletionResponse
from app.ai.tools import register_all_tools
from app.models.event import Event
from app.models.evidence import (
    Evidence,
    EvidenceRole,
    EvidenceType,
    IncidentInvestigation,
    InvestigationAssessment,
)
from app.models.incident import Incident, IncidentEvent, IncidentStatus
from app.models.infrastructure import Infrastructure, InfrastructureStatus, InfrastructureType
from app.models.resource import Resource, ResourceStatus, ResourceType
from app.models.risk import (
    AllocationStatus,
    ImpactAssessment,
    OptimizationResult,
    OptimizationStatus,
    ResourceAllocation,
    RiskAssessment,
    RiskLevel,
)
from tests.copilot_fakes import FakeSession, ScriptedLLMClient

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 15, 12, 0, 0)


@pytest.fixture(autouse=True)
def _registered():
    register_all_tools()


@pytest.fixture
def world():
    """A complete, self-consistent incident with data from every phase."""
    inc = Incident(
        id=uuid4(),
        incident_type="flood",
        title="Flooding reported on MG Road",
        summary="Water rising near the city centre; two roads affected.",
        centroid_latitude=12.9716,
        centroid_longitude=77.5946,
        start_time=NOW - timedelta(hours=4),
        last_updated=NOW - timedelta(minutes=8),
        event_count=2,
        status=IncidentStatus.ACTIVE,
        confidence=0.82,
    )

    event = Event(
        id=uuid4(),
        source="social_media",
        text_content="Water rising on MG Road, cars submerged near the junction.",
        event_type="flood",
        latitude=12.9716,
        longitude=77.5946,
        timestamp=NOW - timedelta(hours=2),
    )

    link = IncidentEvent(
        id=uuid4(),
        incident_id=inc.id,
        event_id=event.id,
        similarity_score=0.93,
        assignment_confidence=0.9,
    )

    evidence = [
        Evidence(
            id=uuid4(),
            incident_id=inc.id,
            evidence_type=EvidenceType.TEXT,
            evidence_role=EvidenceRole.SUPPORTING,
            description="Two independent posts describe rising water on MG Road.",
            evidence_quality=0.85,
            confidence=0.8,
            source="social_media",
        ),
        Evidence(
            id=uuid4(),
            incident_id=inc.id,
            evidence_type=EvidenceType.TEMPORAL,
            evidence_role=EvidenceRole.CONTRADICTING,
            description="A report mentions routine drainage maintenance that day.",
            evidence_quality=0.35,
            confidence=0.3,
            source="news",
        ),
    ]

    investigation = IncidentInvestigation(
        id=uuid4(),
        incident_id=inc.id,
        assessment=InvestigationAssessment.MODERATELY_SUPPORTED,
        evidence_confidence=0.66,
        supporting_evidence_count=1,
        contradicting_evidence_count=1,
        neutral_evidence_count=0,
        uncertain_evidence_count=0,
        explanation="Sources broadly agree but coverage is uneven.",
        model_name="Qwen2.5-7B-Instruct",
        investigated_at=NOW - timedelta(hours=1),
    )

    risk = RiskAssessment(
        id=uuid4(),
        incident_id=inc.id,
        risk_score=72.0,
        risk_level=RiskLevel.HIGH,
        severity_component=80.0,
        evidence_component=60.0,
        population_component=75.0,
        infrastructure_component=65.0,
        environment_component=55.0,
        accessibility_component=50.0,
        explanation="Driven by severity and population exposure.",
        model_name="resq-risk-v1",
        assessed_at=NOW - timedelta(minutes=15),
    )

    impact = ImpactAssessment(
        id=uuid4(),
        incident_id=inc.id,
        population_potentially_exposed=1800,
        population_zones_count=3,
        infrastructure_potentially_exposed=12,
        hospitals_count=1,
        shelters_count=4,
        roads_count=6,
        bridges_count=2,
        accessibility_status="partially_blocked",
        explanation="Estimates within the analysis area.",
        assessed_at=NOW - timedelta(minutes=15),
    )

    ambulance_id = uuid4()
    optimization = OptimizationResult(
        id=uuid4(),
        incident_id=inc.id,
        status=OptimizationStatus.FEASIBLE,
        objective_value=0.42,
        total_distance=1500.0,
        total_resources=1,
        unmet_demand=[{"resource_type": "ambulance", "quantity": 1}],
        explanation="One ambulance assigned; one demand unmet.",
        solver_name="SCIP",
        solver_status="OPTIMAL",
        created_at=NOW - timedelta(minutes=5),
    )
    allocation = ResourceAllocation(
        id=uuid4(),
        optimization_result_id=optimization.id,
        incident_id=inc.id,
        resource_id=ambulance_id,
        resource_type="ambulance",
        distance_meters=1500.0,
        assignment_score=0.88,
        assignment_reason="Nearest available ambulance with medical capability.",
        status=AllocationStatus.RECOMMENDED,
    )

    resource_rows = [
        {
            "id": str(ambulance_id),
            "name": "Ambulance A1",
            "resource_type": "ambulance",
            "status": "available",
            "latitude": 12.98,
            "longitude": 77.60,
            "capacity": 1,
            "current_load": 0,
            "capabilities": {"medical": True},
            "organization": "EMS",
            "updated_at": NOW - timedelta(minutes=8),
            "distance_meters": 1500.0,
        }
    ]

    infra_rows = [
        {
            "id": str(uuid4()),
            "name": "City Hospital",
            "infrastructure_type": "hospital",
            "status": "operational",
            "road_status": None,
            "latitude": 12.98,
            "longitude": 77.60,
            "capacity": 500,
            "updated_at": NOW - timedelta(minutes=20),
            "distance_meters": 812.4,
        },
        {
            "id": str(uuid4()),
            "name": "Riverside Shelter",
            "infrastructure_type": "shelter",
            "status": "operational",
            "road_status": None,
            "latitude": 12.97,
            "longitude": 77.59,
            "capacity": 200,
            "updated_at": NOW - timedelta(minutes=30),
            "distance_meters": 400.0,
        },
    ]

    session = FakeSession(
        objects={
            Incident: [inc],
            IncidentEvent: [(link, event)],
            Evidence: evidence,
            IncidentInvestigation: [investigation],
            RiskAssessment: [risk],
            ImpactAssessment: [impact],
            OptimizationResult: [optimization],
            ResourceAllocation: [allocation],
            Resource: [
                Resource(
                    id=ambulance_id,
                    name="Ambulance A1",
                    resource_type=ResourceType.AMBULANCE,
                    status=ResourceStatus.AVAILABLE,
                    latitude=12.98,
                    longitude=77.60,
                    capacity=1,
                    current_load=0,
                    capabilities={"medical": True},
                    organization="EMS",
                    updated_at=NOW - timedelta(minutes=8),
                )
            ],
            Infrastructure: [
                Infrastructure(
                    id=uuid4(),
                    name="City Hospital",
                    infrastructure_type=InfrastructureType.HOSPITAL,
                    latitude=12.98,
                    longitude=77.60,
                    capacity=500,
                    status=InfrastructureStatus.OPERATIONAL,
                    updated_at=NOW - timedelta(minutes=20),
                )
            ],
        },
        text_results={
            "FROM resources res": resource_rows,
            "FROM infrastructure infra": infra_rows,
        },
    )
    return session, inc


def call(name: str, **arguments) -> ChatCompletionResponse:
    import json

    return ChatCompletionResponse(
        content="",
        tool_calls=[{"id": "c1", "name": name, "arguments": json.dumps(arguments)}],
        finish_reason="tool_calls",
    )


def final(text: str) -> ChatCompletionResponse:
    return ChatCompletionResponse(content=text, tool_calls=[], finish_reason="stop")


async def ask(session, script, message, incident_id=None, history=None):
    service = CopilotService(db=session, client=ScriptedLLMClient(script))
    answer = await service._run_turn(
        message=message, history=history or [], incident_id=incident_id
    )
    return answer, service.client.calls


# -- spec 50 walkthrough -----------------------------------------------------

async def test_full_operator_walkthrough_is_grounded(world):
    session, inc = world

    # 1. "What is happening?"
    answer, _ = await ask(
        session,
        [call("get_incident", incident_id=str(inc.id)), final("Flooding on MG Road.")],
        "What is happening?",
        inc.id,
    )
    assert [e.tool for e in answer.tools_used] == ["get_incident"]

    # 2. "Why is this incident supported?"
    answer, _ = await ask(
        session,
        [
            call("get_incident_investigation", incident_id=str(inc.id)),
            call("get_incident_evidence", incident_id=str(inc.id)),
            final("Moderately supported, with one contradicting item."),
        ],
        "Why is this incident supported?",
        inc.id,
    )
    assert [e.tool for e in answer.tools_used] == [
        "get_incident_investigation",
        "get_incident_evidence",
    ]

    # 3. "What is the current risk?"
    answer, _ = await ask(
        session,
        [call("get_incident_risk", incident_id=str(inc.id)), final("High, 72/100.")],
        "What is the current risk?",
        inc.id,
    )
    assert answer.tools_used[0].tool == "get_incident_risk"
    assert answer.tools_used[0].source == "Phase 6 risk assessment"

    # 4. "What resources are nearby?"
    answer, _ = await ask(
        session,
        [
            call("get_nearby_resources", incident_id=str(inc.id)),
            final("1 ambulance is available."),
        ],
        "What resources are nearby?",
        inc.id,
    )
    assert answer.tools_used[0].status == "success"

    # 5. "What did the optimizer recommend?"
    answer, _ = await ask(
        session,
        [
            call("get_optimization_result", incident_id=str(inc.id)),
            final("1 ambulance recommended, 1 unmet."),
        ],
        "What did the optimizer recommend?",
        inc.id,
    )
    assert answer.tools_used[0].source == "Phase 8 optimization result"

    # 6. "What remains uncertain?"
    answer, _ = await ask(
        session,
        [
            call("get_incident_evidence", incident_id=str(inc.id)),
            call("get_incident_investigation", incident_id=str(inc.id)),
            final("Evidence coverage is uneven; one contradicting report exists."),
        ],
        "What remains uncertain?",
        inc.id,
    )
    assert {e.tool for e in answer.tools_used} == {
        "get_incident_evidence",
        "get_incident_investigation",
    }


async def test_multi_step_summary_uses_several_phases(world):
    session, inc = world
    answer, _ = await ask(
        session,
        [
            call("get_incident", incident_id=str(inc.id)),
            call("get_incident_risk", incident_id=str(inc.id)),
            call("get_incident_impact", incident_id=str(inc.id)),
            final("Summary assembled from incident, risk and impact data."),
        ],
        "Summarize this incident.",
        inc.id,
    )
    assert [e.tool for e in answer.tools_used] == [
        "get_incident",
        "get_incident_risk",
        "get_incident_impact",
    ]
    # Each consulted phase is attributed.
    assert set(answer.sources) == {
        "Database incident record",
        "Phase 6 risk assessment",
        "Phase 6 impact assessment",
    }


# -- conversation context (spec 22) -----------------------------------------

async def test_follow_up_question_reuses_the_conversation_incident(world):
    session, inc = world
    # The model omits the id entirely on the follow-up.
    answer, calls = await ask(
        session,
        [call("get_nearby_resources"), final("1 ambulance available.")],
        "What resources are nearby?",
        inc.id,
    )

    # The pinned incident was supplied by the conversation, not the model.
    tool_message = [m for m in calls[-1]["messages"] if m.role == "tool"][0]
    import json

    payload = json.loads(tool_message.content)
    assert payload["data"]["incident_id"] == str(inc.id)


async def test_history_is_forwarded_as_context(world):
    session, inc = world
    from app.ai.llm.base import Message

    history = [
        Message(role="user", content="Tell me about incident 42."),
        Message(role="assistant", content="It is a flood incident."),
    ]
    answer, calls = await ask(
        session,
        [call("get_nearby_resources"), final("1 ambulance.")],
        "What resources are nearby?",
        inc.id,
        history=history,
    )

    roles = [m.role for m in calls[0]["messages"]]
    # system -> prior user/assistant -> current user
    assert roles[0] == "system"
    assert roles[-1] == "user"
    assert "Tell me about incident 42." in [m.content for m in calls[0]["messages"]]


async def test_infrastructure_question_returns_typed_breakdown(world):
    session, inc = world
    answer, _ = await ask(
        session,
        [
            call("get_incident_infrastructure", incident_id=str(inc.id)),
            final("1 hospital and 1 shelter are within range."),
        ],
        "What infrastructure is nearby?",
        inc.id,
    )
    assert answer.tools_used[0].tool == "get_incident_infrastructure"
    # The trace names the phase the data came from, matching the other tools.
    assert answer.tools_used[0].source == "Infrastructure inventory (PostGIS)"


# -- controlled action stays operator-gated ---------------------------------

async def test_dispatch_request_returns_recommendation_not_action(world):
    session, inc = world
    answer, calls = await ask(
        session, [], "Dispatch ambulance A1 now.", inc.id
    )
    assert answer.refused is True
    assert "can't dispatch" in answer.answer.lower()
    assert "recommendation until an operator" in answer.answer.lower()
