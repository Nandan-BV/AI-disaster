"""
Registration of the copilot's fixed toolset.

The registry is populated exactly once per process. Note what is *absent*:
there is no tool to approve, reject, dispatch, activate, contact, delete, or
otherwise mutate operational state. The model cannot reach SQL either - the
only database access reachable from here is through the fixed handlers below.
"""

import logging
from typing import Optional

from app.ai.tool_registry import ToolPermission, tool_registry
from app.ai.tools import (
    geo_tools,
    incident_tools,
    resource_tools,
    risk_tools,
)

logger = logging.getLogger(__name__)

_registered = False

# Permission classification, surfaced by the API for transparency (spec 17).
PERMISSIONS: dict = {
    # Read-only
    "get_incident": ToolPermission.READ_ONLY,
    "get_incident_events": ToolPermission.READ_ONLY,
    "get_incident_evidence": ToolPermission.READ_ONLY,
    "get_incident_investigation": ToolPermission.READ_ONLY,
    "get_incident_location": ToolPermission.READ_ONLY,
    "get_incident_infrastructure": ToolPermission.READ_ONLY,
    "get_incident_risk": ToolPermission.READ_ONLY,
    "get_incident_impact": ToolPermission.READ_ONLY,
    "get_nearby_resources": ToolPermission.READ_ONLY,
    "get_resource": ToolPermission.READ_ONLY,
    "get_optimization_result": ToolPermission.READ_ONLY,
    "get_optimization_history": ToolPermission.READ_ONLY,
    # Controlled action (opt-in; still never approves or dispatches)
    "run_resource_optimization": ToolPermission.CONTROLLED_ACTION,
}

# Human-readable provenance per tool, echoed in response source attribution.
SOURCES: dict = {
    "get_incident": "Database incident record",
    "get_incident_events": "Incident event records",
    "get_incident_evidence": "Phase 4 evidence investigation",
    "get_incident_investigation": "Phase 4 evidence investigation",
    "get_incident_location": "Incident location (PostGIS)",
    "get_incident_infrastructure": "Infrastructure inventory (PostGIS)",
    "get_incident_risk": "Phase 6 risk assessment",
    "get_incident_impact": "Phase 6 impact assessment",
    "get_nearby_resources": "Phase 7 resource inventory",
    "get_resource": "Phase 7 resource inventory",
    "get_optimization_result": "Phase 8 optimization result",
    "get_optimization_history": "Phase 8 optimization history",
    "run_resource_optimization": "Phase 8 optimization (controlled action)",
}


def register_all_tools(force: bool = False) -> None:
    """Register every copilot tool. Idempotent unless ``force`` is set."""
    global _registered
    if _registered and not force:
        return

    # Incident / events / evidence
    tool_registry.register(
        "get_incident",
        "Get an incident's type, title, summary, location, status and confidence.",
        incident_tools.GetIncidentInput,
        incident_tools.get_incident,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident"],
    )
    tool_registry.register(
        "get_incident_events",
        "Get the events clustered into an incident, including source and text content.",
        incident_tools.GetIncidentEventsInput,
        incident_tools.get_incident_events,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_events"],
    )
    tool_registry.register(
        "get_incident_evidence",
        "Get evidence items for an incident with their role, quality and confidence.",
        incident_tools.GetIncidentEvidenceInput,
        incident_tools.get_incident_evidence,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_evidence"],
    )
    tool_registry.register(
        "get_incident_investigation",
        "Get the latest evidence investigation: assessment, confidence and counts.",
        incident_tools.GetIncidentInvestigationInput,
        incident_tools.get_incident_investigation,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_investigation"],
    )

    # Geospatial
    tool_registry.register(
        "get_incident_location",
        "Get an incident's centroid and its configured analysis area radius.",
        geo_tools.GetIncidentLocationInput,
        geo_tools.get_incident_location,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_location"],
    )
    tool_registry.register(
        "get_incident_infrastructure",
        "Get critical infrastructure (hospitals, shelters, fire/police stations, "
        "schools, bridges, roads, power and water facilities, emergency centers) "
        "within a radius of the incident.",
        geo_tools.GetIncidentInfrastructureInput,
        geo_tools.get_incident_infrastructure,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_infrastructure"],
    )

    # Risk / impact
    tool_registry.register(
        "get_incident_risk",
        "Get the latest stored risk assessment with its component scores.",
        risk_tools.GetIncidentRiskInput,
        risk_tools.get_incident_risk,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_risk"],
    )
    tool_registry.register(
        "get_incident_impact",
        "Get the latest stored impact assessment: potentially exposed population "
        "and infrastructure, and accessibility status.",
        risk_tools.GetIncidentImpactInput,
        risk_tools.get_incident_impact,
        ToolPermission.READ_ONLY,
        SOURCES["get_incident_impact"],
    )

    # Resources
    tool_registry.register(
        "get_nearby_resources",
        "Get emergency resources near an incident, with status, distance, capacity "
        "and capabilities. Use this whenever asked how many resources are available.",
        resource_tools.GetNearbyResourcesInput,
        resource_tools.get_nearby_resources,
        ToolPermission.READ_ONLY,
        SOURCES["get_nearby_resources"],
    )
    tool_registry.register(
        "get_resource",
        "Get a single resource record by id.",
        resource_tools.GetResourceInput,
        resource_tools.get_resource,
        ToolPermission.READ_ONLY,
        SOURCES["get_resource"],
    )

    # Optimization
    tool_registry.register(
        "get_optimization_result",
        "Get the latest (or a specific) stored optimization result, including "
        "recommended allocations and unmet demand. Does not run a new optimization.",
        resource_tools.GetOptimizationResultInput,
        resource_tools.get_optimization_result,
        ToolPermission.READ_ONLY,
        SOURCES["get_optimization_result"],
    )
    tool_registry.register(
        "get_optimization_history",
        "Get previous optimization runs and how their recommended allocations differ.",
        resource_tools.GetOptimizationHistoryInput,
        resource_tools.get_optimization_history,
        ToolPermission.READ_ONLY,
        SOURCES["get_optimization_history"],
    )
    tool_registry.register(
        "run_resource_optimization",
        "Controlled action: produce a new resource optimization recommendation. "
        "Never approves or dispatches. Refused unless explicitly enabled.",
        resource_tools.RunResourceOptimizationInput,
        resource_tools.run_resource_optimization,
        ToolPermission.CONTROLLED_ACTION,
        SOURCES["run_resource_optimization"],
    )

    _registered = True
    logger.info("Registered %d copilot tools: %s", len(tool_registry.names()), tool_registry.names())


def permission_map() -> dict:
    """Current permission classification for every registered tool."""
    return {
        name: tool_registry.get(name).permission.value
        for name in tool_registry.names()
    }


def is_registered() -> bool:
    return _registered
