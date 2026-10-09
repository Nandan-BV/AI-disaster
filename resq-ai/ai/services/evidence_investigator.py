import logging
import json
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ai.config import ai_config
from ai.models import model_manager
from ai.services.embedding_service import generate_embeddings_batch
from app.models.incident import Incident
from app.models.evidence import Evidence, IncidentInvestigation, EvidenceType, EvidenceRole, InvestigationAssessment
from ai.schemas.evidence import EvidenceInvestigation, EvidenceItem

logger = logging.getLogger(__name__)

import os
PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "evidence_investigation.txt")


def load_prompt() -> str:
    with open(PROMPT_PATH, "r") as f:
        return f.read()


PROMPT_TEMPLATE = load_prompt()


async def run_ai_investigation(
    incident_id: UUID,
    incident_type: Optional[str],
    incident_title: str,
    event_count: int,
    incident_location: Optional[str],
    evidence_items: List[Evidence],
    source_diversity: Optional[float],
    geographic_consistency: Optional[float],
    temporal_consistency: Optional[float],
    multimodal_consistency: Optional[float],
) -> Dict[str, Any]:
    """Run the AI evidence investigator on collected evidence."""
    # Format evidence items for prompt
    evidence_text = ""
    for i, ev in enumerate(evidence_items):
        event_info = f" (Event: {ev.event_id})" if ev.event_id else ""
        evidence_text += f"\n{i+1}. [{ev.evidence_type}] [{ev.evidence_role}] Quality:{ev.evidence_quality:.2f} Conf:{ev.confidence:.2f}{event_info}\n   {ev.description}\n"

    incident_location_str = incident_location or "Unknown"

    prompt = PROMPT_TEMPLATE.format(
        incident_id=incident_id,
        incident_type=incident_type or "unknown",
        incident_title=incident_title,
        event_count=event_count,
        incident_location=incident_location_str,
        evidence_items=evidence_text,
        source_diversity=f"{source_diversity:.2f}" if source_diversity else "N/A",
        geographic_consistency=f"{geographic_consistency:.2f}" if geographic_consistency else "N/A",
        temporal_consistency=f"{temporal_consistency:.2f}" if temporal_consistency else "N/A",
        multimodal_consistency=f"{multimodal_consistency:.2f}" if multimodal_consistency else "N/A",
    )

    model = model_manager.load_model()
    try:
        response = await model.analyze_text(prompt, "")
    except Exception as e:
        logger.error(f"AI investigation failed: {e}")
        # Fallback deterministic assessment
        return fallback_investigation(evidence_items, source_diversity, geographic_consistency, temporal_consistency, multimodal_consistency)

    # Parse AI response
    try:
        result = json.loads(response.strip())
        # Validate assessment
        valid_assessments = [
            "strongly_supported", "moderately_supported", "weakly_supported",
            "conflicting", "insufficient_evidence", "inconclusive"
        ]
        if result.get("assessment") not in valid_assessments:
            result["assessment"] = "inconclusive"
        # Clamp confidence
        if "evidence_confidence_score" in result:
            result["evidence_confidence_score"] = max(0.0, min(1.0, float(result["evidence_confidence_score"])))
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse AI investigation response: {e}")
        return fallback_investigation(evidence_items, source_diversity, geographic_consistency, temporal_consistency, multimodal_consistency)


def fallback_investigation(
    evidence_items: List[Evidence],
    source_diversity: Optional[float],
    geographic_consistency: Optional[float],
    temporal_consistency: Optional[float],
    multimodal_consistency: Optional[float],
) -> Dict[str, Any]:
    """Deterministic fallback when AI is unavailable."""
    supporting = [e for e in evidence_items if e.evidence_role == EvidenceRole.SUPPORTING]
    contradicting = [e for e in evidence_items if e.evidence_role == EvidenceRole.CONTRADICTING]
    uncertain = [e for e in evidence_items if e.evidence_role == EvidenceRole.UNCERTAIN]
    neutral = [e for e in evidence_items if e.evidence_role == EvidenceRole.NEUTRAL]

    total_evidence = len(evidence_items)
    if total_evidence == 0:
        return {
            "supporting_evidence_summary": "No evidence available",
            "contradicting_evidence_summary": "No evidence available",
            "uncertain_evidence_summary": "No evidence available",
            "explanation": "No evidence could be collected for this incident.",
            "limitations": "No events or analyses available for investigation.",
            "assessment": "insufficient_evidence",
            "evidence_confidence_score": 0.0,
        }

    # Calculate weighted confidence
    support_weight = sum(e.confidence or 0 for e in supporting)
    contradict_weight = sum(e.confidence or 0 for e in contradicting)
    uncertain_weight = sum(e.confidence or 0 for e in uncertain)

    # Component scores
    components = [
        ("source_diversity", source_diversity or 0.3, 0.2),
        ("geographic_consistency", geographic_consistency or 0.3, 0.2),
        ("temporal_consistency", temporal_consistency or 0.3, 0.2),
        ("multimodal_consistency", multimodal_consistency or 0.3, 0.2),
    ]
    component_score = sum(score * weight for _, score, weight in components)

    # Evidence-based score
    if total_evidence > 0:
        evidence_score = (support_weight * 1.0 + neutral_weight * 0.5 - contradict_weight * 1.0) / total_evidence
        evidence_score = max(0.0, min(1.0, evidence_score))
    else:
        evidence_score = 0.0

    # Combined score
    combined = 0.6 * evidence_score + 0.4 * component_score

    # Determine assessment
    if combined >= 0.8 and len(supporting) >= 3 and contradict_weight < 0.2:
        assessment = "strongly_supported"
    elif combined >= 0.6 and len(supporting) >= 2:
        assessment = "moderately_supported"
    elif combined >= 0.4 and len(supporting) >= 1:
        assessment = "weakly_supported"
    elif contradict_weight > 0.3 or len(contradicting) >= 2:
        assessment = "conflicting"
    elif total_evidence <= 2:
        assessment = "insufficient_evidence"
    else:
        assessment = "inconclusive"

    # Build summaries
    support_summary = f"{len(supporting)} supporting items" if supporting else "None"
    contradict_summary = f"{len(contradicting)} contradicting items" if contradicting else "None"
    uncertain_summary = f"{len(uncertain)} uncertain items" if uncertain else "None"

    # Build explanation
    explanation_parts = []
    if supporting:
        explanation_parts.append(f"Supporting evidence ({len(supporting)} items) includes: " + 
            "; ".join([e.description[:80] for e in supporting[:3]]))
    if contradicting:
        explanation_parts.append(f"Contradicting evidence ({len(contradicting)} items) includes: " +
            "; ".join([e.description[:80] for e in contradicting[:2]]))
    if uncertain:
        explanation_parts.append(f"Uncertain evidence ({len(uncertain)} items) reflects reports with limited confidence or hedging language.")
    if not supporting and not contradicting:
        explanation_parts.append("No clear supporting or contradicting evidence found.")

    # Limitations
    limitations_parts = []
    if source_diversity and source_diversity < 0.5:
        limitations_parts.append("Limited source diversity; all reports may originate from similar channels.")
    if geographic_consistency and geographic_consistency < 0.5:
        limitations_parts.append("Low geographic consistency among reports.")
    if temporal_consistency and temporal_consistency < 0.5:
        limitations_parts.append("Wide temporal spread reduces confidence in single-event interpretation.")
    if multimodal_consistency and multimodal_consistency < 0.5:
        limitations_parts.append("Low multimodal agreement; disaster type interpretations vary.")
    if len(evidence_items) < 3:
        limitations_parts.append("Few evidence items available; conclusions are tentative.")
    if not evidence_items:
        limitations_parts.append("No evidence items could be extracted.")

    limitations = " ".join(limitations_parts) if limitations_parts else "Standard evidence limitations apply."

    return {
        "supporting_evidence_summary": support_summary,
        "contradicting_evidence_summary": contradict_summary,
        "uncertain_evidence_summary": uncertain_summary,
        "explanation": " ".join(explanation_parts),
        "limitations": limitations,
        "assessment": assessment,
        "evidence_confidence_score": round(combined, 2),
    }


async def investigate_incident(
    incident_id: UUID,
    db: AsyncSession,
    force_rerun: bool = False,
) -> IncidentInvestigation:
    """
    Run a complete evidence investigation for an incident.
    """
    # Check if investigation already exists
    if not force_rerun:
        existing = await db.execute(
            select(IncidentInvestigation)
            .where(IncidentInvestigation.incident_id == incident_id)
            .order_by(IncidentInvestigation.investigated_at.desc())
        )
        existing_inv = existing.scalar_one_or_none()
        if existing_inv:
            logger.info(f"Returning existing investigation for incident {incident_id}")
            return existing_inv

    # Get incident
    incident_result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = incident_result.scalar_one_or_none()
    if not incident:
        raise ValueError(f"Incident {incident_id} not found")

    # Collect evidence
    from ai.services.evidence_collector import collect_incident_evidence
    collection = await collect_incident_evidence(incident_id, db)

    # Extract all evidence items
    all_evidence = []
    for event in collection.events:
        all_evidence.extend(extract_text_evidence(event))
        all_evidence.extend(extract_image_evidence(event))
        all_evidence.extend(extract_video_evidence(event))

    # Add consistency evidence
    incident_center = None
    if incident.centroid_latitude and incident.centroid_longitude:
        incident_center = (incident.centroid_latitude, incident.centroid_longitude)

    all_evidence.extend(extract_geographic_evidence(collection, incident_center))
    all_evidence.extend(extract_temporal_evidence(collection))
    all_evidence.extend(extract_multimodal_consistency(collection))
    all_evidence.extend(extract_source_diversity(collection))

    # Store evidence items in database
    for ev in all_evidence:
        db.add(ev)
    await db.flush()

    # Separate by role for AI
    supporting = [e for e in all_evidence if e.evidence_role == EvidenceRole.SUPPORTING]
    contradicting = [e for e in all_evidence if e.evidence_role == EvidenceRole.CONTRADICTING]
    uncertain = [e for e in all_evidence if e.evidence_role == EvidenceRole.UNCERTAIN]
    neutral = [e for e in all_evidence if e.evidence_role == EvidenceRole.NEUTRAL]

    # Calculate component scores for AI
    source_diversity_score = None
    geo_consistency = None
    temp_consistency = None
    multi_consistency = None

    for ev in all_evidence:
        if ev.evidence_type == EvidenceType.SOURCE_DIVERSITY:
            source_diversity_score = ev.evidence_quality
        elif ev.evidence_type == EvidenceType.GEOGRAPHIC:
            geo_consistency = ev.evidence_quality
        elif ev.evidence_type == EvidenceType.TEMPORAL:
            temp_consistency = ev.evidence_quality
        elif ev.evidence_type == EvidenceType.MULTIMODAL:
            multi_consistency = ev.evidence_quality

    # Run AI investigation
    ai_result = await run_ai_investigation(
        incident_id=incident_id,
        incident_type=incident.incident_type,
        incident_title=incident.title,
        event_count=collection.total_events,
        incident_location=incident.location_name or f"({incident.centroid_latitude}, {incident.centroid_longitude})",
        evidence_items=all_evidence,
        source_diversity=source_diversity_score,
        geographic_consistency=geo_consistency,
        temporal_consistency=temp_consistency,
        multimodal_consistency=multi_consistency,
    )

    # Create investigation record
    investigation = IncidentInvestigation(
        incident_id=incident_id,
        supporting_evidence_count=len(supporting),
        contradicting_evidence_count=len(contradicting),
        neutral_evidence_count=len(neutral),
        uncertain_evidence_count=len(uncertain),
        evidence_confidence=ai_result["evidence_confidence_score"],
        assessment=InvestigationAssessment(ai_result["assessment"]),
        explanation=ai_result["explanation"],
        limitations=ai_result["limitations"],
        source_diversity=source_diversity_score,
        geographic_consistency=geo_consistency,
        temporal_consistency=temp_consistency,
        multimodal_consistency=multi_consistency,
        model_name=ai_config.AI_MODEL_NAME,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    logger.info(f"Completed investigation for incident {incident_id}: {investigation.assessment} (confidence: {investigation.evidence_confidence})")
    return investigation


async def get_incident_investigation(
    incident_id: UUID,
    db: AsyncSession,
) -> Optional[IncidentInvestigation]:
    """Get the latest investigation for an incident."""
    result = await db.execute(
        select(IncidentInvestigation)
        .where(IncidentInvestigation.incident_id == incident_id)
        .order_by(IncidentInvestigation.investigated_at.desc())
    )
    return result.scalar_one_or_none()


async def get_incident_evidence(
    incident_id: UUID,
    db: AsyncSession,
    evidence_type: Optional[EvidenceType] = None,
    evidence_role: Optional[EvidenceRole] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Evidence]:
    """Get all evidence for an incident with optional filters."""
    query = select(Evidence).where(Evidence.incident_id == incident_id)

    if evidence_type:
        query = query.where(Evidence.evidence_type == evidence_type)
    if evidence_role:
        query = query.where(Evidence.evidence_role == evidence_role)

    query = query.order_by(Evidence.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())