"""
case_evaluation.py

GOAL
----
This file evaluates the current state of a CaseRecord as an operational
situation.

Riskseer is not a generic event severity engine. Its goal is to identify
when a field team or operator is at risk of making the wrong decision under
uncertainty before that decision turns into damage.

This file interprets the case as it exists now through the lens of actual
operator feedback:
- excavation damage is usually layered, not single-cause
- process compliance alone does not equal safety
- human habit can override red flags
- changing site conditions and incomplete context matter
- the real problem is not just "bad events"
  but "bad decisions made with flawed confidence"

WHAT case_evaluation.py DOES
----------------------------
1. Evaluates a completed CaseRecord as a current operational situation.
2. Synthesizes case observations into structured assessments:
   - alignment
   - information integrity
   - behavioral risk
   - uncertainty burden
3. Builds explicit evidence layers:
   - observed
   - derived
   - inferred
   - assumed
4. Assigns current-state interpretation:
   - decision_state
   - urgency
   - response_posture
   - failure_layers
5. Produces structured current-state outputs for downstream orchestration.

WHAT case_evaluation.py MUST NOT DO
-----------------------------------
1. It must not group events into cases. case.py owns that.
2. It must not parse raw CSV inputs. main.py / normalization layers own that.
3. It must not compare current state to prior saved state. case_temporal.py owns that.
4. It must not generate polished operator prose. explanations.py / orchestration layers own that.
5. It must not pretend uncertainty is resolved when it is not.
6. It must not reward "ticket exists" as equivalent to "safe to proceed".
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from schemas import (
    AlignmentAssessment,
    BehavioralRiskAssessment,
    CaseRecord,
    DataQuality,
    DecisionDefensibilityEvaluation,
    DecisionDefensibilityState,
    DecisionState,
    EvidenceItem,
    EvidenceKind,
    EvidenceLayers,
    FailureLayer,
    InformationIntegrityAssessment,
    Observation,
    ObservationType,
    DecisionRiskLevel,
    DecisionSupportIntegrity,
    DecisionSupportState,
    ResponsibilityIntegrityBundle,
    ResponsibilityLayerAssessment,
    ResponsibilityLayerState,
    ResponsePosture,
    UrgencyLevel,
)

MAX_SCORE = 1.0
MIN_SCORE = 0.0


# ============================================================
# SMALL HELPERS
# ============================================================

def clamp01(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(MIN_SCORE, min(MAX_SCORE, value))


def avg(values: Sequence[float]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def add_unique_text(target: List[str], items: Iterable[str]) -> None:
    existing = set(target)
    for item in items:
        if item and item not in existing:
            target.append(item)
            existing.add(item)


def observation_field(obs: object, field: str, default: object = None) -> object:
    if isinstance(obs, dict):
        return obs.get(field, default)
    return getattr(obs, field, default)


def observation_type_value(obs: object) -> object:
    raw = observation_field(obs, "observation_type")
    return getattr(raw, "value", raw)


def obs_by_type(observations: Sequence[Observation], obs_type: ObservationType) -> List[Observation]:
    target = getattr(obs_type, "value", obs_type)
    matched: List[Observation] = []
    for obs in observations:
        raw_type = observation_field(obs, "observation_type")
        normalized_type = getattr(raw_type, "value", raw_type)
        if raw_type == obs_type or normalized_type == target:
            matched.append(obs)
    return matched


def has_obs(observations: Sequence[Observation], obs_type: ObservationType) -> bool:
    return len(obs_by_type(observations, obs_type)) > 0


def highest_confidence(observations: Sequence[Observation]) -> Optional[float]:
    vals: List[float] = []
    for obs in observations:
        confidence = observation_field(obs, "confidence")
        if confidence is not None:
            try:
                vals.append(float(confidence))
            except (TypeError, ValueError):
                continue
    return max(vals) if vals else None


def summarize_count(label: str, count: int) -> str:
    if count == 1:
        return f"1 {label}"
    return f"{count} {label}s"


def normalize_decision_state(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# EVIDENCE LAYERS
# ============================================================

def build_observed_evidence(case: CaseRecord) -> List[EvidenceItem]:
    evidence: List[EvidenceItem] = []

    if case.event_ids:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement=f"Case contains {summarize_count('event', len(case.event_ids))}",
                source_ids=list(case.event_ids),
                confidence=0.95,
                metadata={},
            )
        )

    repeated = obs_by_type(case.observations, ObservationType.REPEATED_ACTIVITY)
    if repeated:
        prior_ids: List[str] = []
        for obs in repeated:
            metadata = observation_field(obs, "metadata", {}) or {}
            if isinstance(metadata, dict):
                prior_ids.extend(metadata.get("prior_event_ids", []))
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement="Repeated nearby activity was observed within a short time window",
                source_ids=[observation_field(obs, "event_id") for obs in repeated if observation_field(obs, "event_id")] + prior_ids,
                confidence=highest_confidence(repeated) or 0.7,
                metadata={},
            )
        )

    escalating = obs_by_type(case.observations, ObservationType.ESCALATING_ACTIVITY)
    if escalating:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement="Activity intensity increased relative to nearby recent activity",
                source_ids=[observation_field(obs, "event_id") for obs in escalating if observation_field(obs, "event_id")],
                confidence=highest_confidence(escalating) or 0.65,
                metadata={},
            )
        )

    heavy = obs_by_type(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    if heavy:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement="Observed signals suggest heavy equipment presence",
                source_ids=[observation_field(obs, "event_id") for obs in heavy if observation_field(obs, "event_id")],
                confidence=highest_confidence(heavy) or 0.7,
                metadata={},
            )
        )

    trenchless = obs_by_type(case.observations, ObservationType.TRENCHLESS_INDICATOR)
    if trenchless:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement="Observed signals suggest trenchless or HDD-related activity",
                source_ids=[observation_field(obs, "event_id") for obs in trenchless if observation_field(obs, "event_id")],
                confidence=highest_confidence(trenchless) or 0.7,
                metadata={},
            )
        )

    near_asset = obs_by_type(case.observations, ObservationType.NEAR_ASSET)
    if near_asset:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.OBSERVED,
                statement="Activity was observed near one or more mapped assets",
                source_ids=[observation_field(obs, "event_id") for obs in near_asset if observation_field(obs, "event_id")],
                confidence=0.9,
                metadata={},
            )
        )

    return evidence


def build_derived_evidence(case: CaseRecord) -> List[EvidenceItem]:
    evidence: List[EvidenceItem] = []

    inside_area = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_AREA)
    outside_area = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    if outside_area:
        statement = (
            "Observed activity conflicts with one or more associated ticket areas"
            if inside_area
            else "Observed activity falls outside the matched ticket area"
        )
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.DERIVED,
                statement=statement,
                source_ids=[observation_field(obs, "event_id") for obs in outside_area if observation_field(obs, "event_id")]
                + [observation_field(obs, "ticket_id") for obs in outside_area if observation_field(obs, "ticket_id")],
                confidence=highest_confidence(outside_area) or 0.75,
                metadata={},
            )
        )

    inside_window = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_WINDOW)
    outside_window = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    if outside_window:
        statement = (
            "Observed activity conflicts with one or more associated ticket time windows"
            if inside_window
            else "Observed activity falls outside the matched ticket time window"
        )
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.DERIVED,
                statement=statement,
                source_ids=[observation_field(obs, "event_id") for obs in outside_window if observation_field(obs, "event_id")]
                + [observation_field(obs, "ticket_id") for obs in outside_window if observation_field(obs, "ticket_id")],
                confidence=highest_confidence(outside_window) or 0.75,
                metadata={},
            )
        )

    no_ticket = obs_by_type(case.observations, ObservationType.NO_MATCHING_TICKET)
    if no_ticket:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.DERIVED,
                statement=(
                    "Attached ticket context does not support at least part of the observed activity"
                    if case.ticket_ids or case.context_ticket_ids
                    else "No plausible matching ticket was found for at least part of the activity"
                ),
                source_ids=[observation_field(obs, "event_id") for obs in no_ticket if observation_field(obs, "event_id")],
                confidence=highest_confidence(no_ticket) or 0.9,
                metadata={},
            )
        )

    multi_ticket = obs_by_type(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    if multi_ticket:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.DERIVED,
                statement="Multiple plausible tickets are associated with the activity, increasing ambiguity",
                source_ids=[observation_field(obs, "event_id") for obs in multi_ticket if observation_field(obs, "event_id")],
                confidence=highest_confidence(multi_ticket) or 0.6,
                metadata={},
            )
        )

    far_asset = obs_by_type(case.observations, ObservationType.FAR_FROM_ASSET)
    if far_asset and not has_obs(case.observations, ObservationType.NEAR_ASSET):
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.DERIVED,
                statement="Mapped asset relevance appears weak based on current proximity observations",
                source_ids=[observation_field(obs, "event_id") for obs in far_asset if observation_field(obs, "event_id")],
                confidence=0.6,
                metadata={},
            )
        )

    return evidence


def build_inferred_evidence(case: CaseRecord) -> List[EvidenceItem]:
    evidence: List[EvidenceItem] = []

    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    repeated = has_obs(case.observations, ObservationType.REPEATED_ACTIVITY)
    escalating = has_obs(case.observations, ObservationType.ESCALATING_ACTIVITY)
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)
    data_gap = has_obs(case.observations, ObservationType.DATA_GAP)

    if (outside_area or outside_window or no_ticket) and (repeated or escalating):
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.INFERRED,
                statement="Work is continuing while scope or authorization remains unresolved",
                source_ids=list(case.event_ids),
                confidence=0.65,
                metadata={},
            )
        )

    if heavy and (outside_area or no_ticket):
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.INFERRED,
                statement="Mechanized excavation may be continuing under weak or mismatched authorization context",
                source_ids=list(case.event_ids),
                confidence=0.7,
                metadata={},
            )
        )

    if trenchless:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.INFERRED,
                statement="Reduced visibility work methods may shrink the recovery window when assumptions are weak",
                source_ids=list(case.event_ids),
                confidence=0.65,
                metadata={},
            )
        )

    if data_gap:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.INFERRED,
                statement="Important context may be missing or incomplete, reducing confidence in the basis for proceeding",
                source_ids=list(case.event_ids),
                confidence=0.75,
                metadata={},
            )
        )

    return evidence


def build_assumed_evidence(case: CaseRecord) -> List[EvidenceItem]:
    evidence: List[EvidenceItem] = []

    if case.ticket_ids:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.ASSUMED,
                statement="Work appears authorized because it falls within a valid ticket",
                source_ids=list(case.ticket_ids),
                confidence=0.4,
                metadata={},
            )
        )

    if case.asset_ids:
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.ASSUMED,
                statement="Mapped asset geometry may be treated as reliable even when the field basis for trust is limited",
                source_ids=list(case.asset_ids),
                confidence=0.4,
                metadata={},
            )
        )

    if has_obs(case.observations, ObservationType.INSIDE_TICKET_AREA) and has_obs(case.observations, ObservationType.INSIDE_TICKET_WINDOW):
        evidence.append(
            EvidenceItem(
                kind=EvidenceKind.ASSUMED,
                statement="Visible ticket coverage can look valid even when authorization conflicts remain unresolved",
                source_ids=list(case.event_ids),
                confidence=0.45,
                metadata={},
            )
        )

    return evidence


def build_evidence_layers(case: CaseRecord) -> EvidenceLayers:
    return EvidenceLayers(
        observed=build_observed_evidence(case),
        derived=build_derived_evidence(case),
        inferred=build_inferred_evidence(case),
        assumed=build_assumed_evidence(case),
    )


# ============================================================
# ALIGNMENT ASSESSMENT
# ============================================================

def evaluate_alignment(case: CaseRecord) -> AlignmentAssessment:
    inside_area = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_AREA)
    outside_area = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    inside_window = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_WINDOW)
    outside_window = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    no_ticket = obs_by_type(case.observations, ObservationType.NO_MATCHING_TICKET)
    near_asset = obs_by_type(case.observations, ObservationType.NEAR_ASSET)

    concerns: List[str] = []

    if no_ticket:
        spatial_alignment = 0.1
        if case.ticket_ids or case.context_ticket_ids:
            concerns.append("Attached ticket context does not support part of the observed activity")
        else:
            concerns.append("No plausible ticket relationship was found for part of the activity")
    elif outside_area and inside_area:
        spatial_alignment = 0.4
        concerns.append("Authorization boundary conflicts across associated ticket areas")
    elif outside_area:
        spatial_alignment = 0.2
        concerns.append("Activity falls outside the matched ticket area")
    elif inside_area:
        spatial_alignment = 0.8
    else:
        spatial_alignment = 0.5
        concerns.append("Spatial alignment could not be established clearly")

    if no_ticket:
        temporal_alignment = 0.1
    elif outside_window and inside_window:
        temporal_alignment = 0.4
        concerns.append("Ticket time coverage conflicts across associated tickets")
    elif outside_window:
        temporal_alignment = 0.2
        concerns.append("Activity falls outside the matched ticket time window")
    elif inside_window:
        temporal_alignment = 0.8
    else:
        temporal_alignment = 0.5
        concerns.append("Temporal alignment could not be established clearly")

    match_strength = avg([spatial_alignment, temporal_alignment])

    if near_asset:
        asset_relevance = 0.9
    elif case.asset_ids:
        asset_relevance = 0.4
        concerns.append("Asset association exists but proximity evidence is weak")
    else:
        asset_relevance = 0.3
        concerns.append("No mapped asset context is clearly tied to this case")

    if match_strength is None:
        summary = "Alignment is unclear"
    elif match_strength >= 0.75:
        summary = "Activity broadly aligns with available ticket context"
    elif match_strength >= 0.45:
        summary = "Activity has partial or mixed alignment with available ticket context"
    else:
        summary = "Activity shows weak alignment with available ticket context"

    return AlignmentAssessment(
        spatial_alignment=clamp01(spatial_alignment),
        temporal_alignment=clamp01(temporal_alignment),
        ticket_match_strength=clamp01(match_strength),
        asset_relevance=clamp01(asset_relevance),
        summary=summary,
        concerns=concerns,
    )


# ============================================================
# INFORMATION INTEGRITY ASSESSMENT
# ============================================================

def evaluate_information_integrity(case: CaseRecord) -> InformationIntegrityAssessment:
    data_gap = obs_by_type(case.observations, ObservationType.DATA_GAP)
    multi_ticket = obs_by_type(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    inside_area = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_AREA)
    inside_window = obs_by_type(case.observations, ObservationType.INSIDE_TICKET_WINDOW)
    outside_area = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = obs_by_type(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    no_ticket = obs_by_type(case.observations, ObservationType.NO_MATCHING_TICKET)
    near_asset = obs_by_type(case.observations, ObservationType.NEAR_ASSET)
    far_asset = obs_by_type(case.observations, ObservationType.FAR_FROM_ASSET)

    concerns: List[str] = []

    ticket_quality_score = 0.7
    if no_ticket:
        ticket_quality_score = 0.1
        if case.ticket_ids or case.context_ticket_ids:
            concerns.append("Attached ticket context does not support part of the observed activity")
        else:
            concerns.append("Ticket context is absent for part of the activity")
    elif data_gap:
        ticket_quality_score -= 0.25
        concerns.append("Ticket validation is weakened by missing context")
    if multi_ticket:
        ticket_quality_score -= 0.20
        concerns.append("Multiple plausible tickets increase ambiguity")
    if outside_area or outside_window:
        ticket_quality_score -= 0.15
        concerns.append("Ticket relationship is present but misaligned")
    if inside_area and inside_window and not (outside_area or outside_window):
        ticket_quality_score += 0.05

    asset_quality_score = 0.6
    if near_asset:
        asset_quality_score += 0.2
    elif far_asset:
        asset_quality_score -= 0.15
        concerns.append("Asset geometry may not explain the observed activity clearly")
    if not case.asset_ids:
        asset_quality_score = 0.3
        concerns.append("Asset context is limited or missing")

    event_quality_score = 0.75
    if data_gap:
        event_quality_score -= 0.15
    if not case.event_ids:
        event_quality_score = 0.1
        concerns.append("Case has no event support")

    ticket_quality_score = clamp01(ticket_quality_score) or 0.0
    asset_quality_score = clamp01(asset_quality_score) or 0.0
    event_quality_score = clamp01(event_quality_score) or 0.0

    overall = avg([ticket_quality_score, asset_quality_score, event_quality_score])

    if overall is None:
        summary = "Information integrity could not be assessed"
    elif overall >= 0.75:
        summary = "Available context is relatively coherent, but still not direct field confirmation"
    elif overall >= 0.50:
        summary = "Available context is usable but contains meaningful uncertainty"
    else:
        summary = "Available context is weak, incomplete, or potentially misleading"

    if multi_ticket and (inside_area or inside_window) and (outside_area or outside_window):
        concerns.append("Authorization appears partial and conflicting across multiple tickets")

    return InformationIntegrityAssessment(
        ticket_quality=DataQuality(
            confidence=ticket_quality_score,
            freshness=None,
            completeness=None,
            notes=[],
        ),
        asset_quality=DataQuality(
            confidence=asset_quality_score,
            freshness=None,
            completeness=None,
            notes=[],
        ),
        event_quality=DataQuality(
            confidence=event_quality_score,
            freshness=None,
            completeness=None,
            notes=[],
        ),
        overall_confidence=clamp01(overall),
        summary=summary,
        concerns=concerns,
    )


# ============================================================
# BEHAVIORAL RISK ASSESSMENT
# ============================================================

def evaluate_behavioral_risk(case: CaseRecord) -> BehavioralRiskAssessment:
    repeated = obs_by_type(case.observations, ObservationType.REPEATED_ACTIVITY)
    escalating = obs_by_type(case.observations, ObservationType.ESCALATING_ACTIVITY)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)
    has_scope_conflict = outside_area or outside_window or no_ticket

    conflicting_signals_ignored = has_scope_conflict and bool(repeated or escalating)

    concerns: List[str] = []
    habit_risk = 0.20

    if repeated:
        if has_scope_conflict:
            habit_risk += 0.20
            concerns.append("Activity is repeating while authorization support is unresolved")
        else:
            habit_risk += 0.08
            concerns.append("Activity is repeating within a short operational window")
    if escalating:
        habit_risk += 0.20 if has_scope_conflict else 0.12
        concerns.append("Activity intensity is increasing")
    if conflicting_signals_ignored:
        habit_risk += 0.25
        concerns.append("Work appears to continue despite unresolved authorization conflicts")
    if heavy:
        if has_scope_conflict:
            habit_risk += 0.10
            concerns.append("Mechanized work increases consequence if crews keep relying on weak assumptions")
        else:
            habit_risk += 0.03
            concerns.append("Mechanized work is consequential, but current support does not show a scope conflict")
    if trenchless:
        if has_scope_conflict:
            habit_risk += 0.10
            concerns.append("Trenchless or HDD work may reduce visibility and recovery time")
        else:
            habit_risk += 0.04
            concerns.append("Trenchless or HDD work is consequential, but current support does not show a scope conflict")

    habit_risk = clamp01(habit_risk) or 0.0

    if conflicting_signals_ignored and habit_risk >= 0.75:
        summary = "Work is continuing despite unresolved authorization conflicts"
    elif has_scope_conflict and habit_risk >= 0.45:
        summary = "Work may continue before authorization contradictions are resolved"
    else:
        summary = "Behavioral risk is limited based on current observed activity pattern"

    return BehavioralRiskAssessment(
        repeated_activity=bool(repeated),
        escalating_activity=bool(escalating),
        conflicting_signals_ignored=conflicting_signals_ignored,
        habit_risk=habit_risk,
        summary=summary,
        concerns=concerns,
    )


# ============================================================
# RESPONSIBILITY INTEGRITY MODEL
# ============================================================

def observation_summaries(case: CaseRecord, obs_type: ObservationType) -> List[str]:
    return [
        str(observation_field(obs, "summary"))
        for obs in obs_by_type(case.observations, obs_type)
        if observation_field(obs, "summary")
    ]


def responsibility_layer(
    state: ResponsibilityLayerState,
    reason: str,
    confidence: float,
    *,
    observed_facts: Optional[Sequence[str]] = None,
    derived_facts: Optional[Sequence[str]] = None,
    missing_facts: Optional[Sequence[str]] = None,
    assumptions: Optional[Sequence[str]] = None,
) -> ResponsibilityLayerAssessment:
    return ResponsibilityLayerAssessment(
        state=state,
        reason=reason,
        confidence=clamp01(confidence),
        observed_facts=list(observed_facts or []),
        derived_facts=list(derived_facts or []),
        missing_facts=list(missing_facts or []),
        assumptions=list(assumptions or []),
    )


def layer_state_score(state: ResponsibilityLayerState) -> float:
    if state == ResponsibilityLayerState.STRONG:
        return 0.85
    if state == ResponsibilityLayerState.WEAK:
        return 0.55
    if state == ResponsibilityLayerState.UNKNOWN:
        return 0.40
    if state == ResponsibilityLayerState.MISSING:
        return 0.30
    if state == ResponsibilityLayerState.CONFLICTED:
        return 0.20
    return 0.40


def normalize_layer_state(value: Any) -> ResponsibilityLayerState:
    text = getattr(value, "value", value)
    try:
        return ResponsibilityLayerState(str(text))
    except ValueError:
        return ResponsibilityLayerState.WEAK


def evaluate_excavator_layer(
    case: CaseRecord,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityLayerAssessment:
    observed: List[str] = []
    derived: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    event_count = len(case.event_ids or [])
    if event_count:
        observed.append(f"{summarize_count('event', event_count)} attached to this case")
    else:
        missing.append("Event support is unknown because no event evidence is attached")

    add_unique_text(observed, observation_summaries(case, ObservationType.HEAVY_EQUIPMENT_INDICATOR))
    add_unique_text(observed, observation_summaries(case, ObservationType.TRENCHLESS_INDICATOR))
    add_unique_text(derived, observation_summaries(case, ObservationType.REPEATED_ACTIVITY))
    add_unique_text(derived, observation_summaries(case, ObservationType.ESCALATING_ACTIVITY))

    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    repeated = has_obs(case.observations, ObservationType.REPEATED_ACTIVITY)
    escalating = has_obs(case.observations, ObservationType.ESCALATING_ACTIVITY)
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)

    if case.metadata.get("mixed_contractors"):
        derived.append("Attached activity includes mixed contractor signals")
    if case.metadata.get("mixed_work_types"):
        derived.append("Attached activity includes mixed work-type signals")
    if not case.metadata.get("dominant_contractor"):
        missing.append("Excavator or contractor identity is unknown from attached case data")
    if not case.metadata.get("dominant_work_type"):
        missing.append("Work intent is unknown and only inferred from event context")

    if no_ticket or ((outside_area or outside_window) and (repeated or escalating)):
        return responsibility_layer(
            ResponsibilityLayerState.CONFLICTED,
            "Observed work behavior conflicts with the available authorization context",
            0.68,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if event_count == 0:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Excavator behavior is unknown because no attached event evidence is available",
            0.25,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if missing or outside_area or outside_window or (escalating and (heavy or trenchless)):
        return responsibility_layer(
            ResponsibilityLayerState.WEAK,
            "Excavator intent or behavior support is partial, inferred, or operationally consequential",
            0.56,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if repeated:
        assumptions.append("Repeated activity is treated as aligned because ticket, timing, and location support do not conflict")
    if heavy or trenchless:
        assumptions.append("Consequential work method is not treated as weak by itself when authorization and field support align")
    if not assumptions:
        assumptions.append("Routine activity pattern is treated as aligned because no contradictory behavior is present")
    return responsibility_layer(
        ResponsibilityLayerState.STRONG,
        "Observed behavior aligns with available ticket context and shows no continuation conflict",
        0.78,
        observed_facts=observed,
        derived_facts=derived,
        missing_facts=missing,
        assumptions=assumptions,
    )


def evaluate_locate_layer(
    case: CaseRecord,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityLayerAssessment:
    observed: List[str] = []
    derived: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    if case.ticket_ids or case.context_ticket_ids:
        observed.append(f"{summarize_count('ticket', len(set(case.ticket_ids + case.context_ticket_ids)))} associated with this case")
    else:
        missing.append("Ticket context is unknown from attached case data")

    if case.positive_response_ids:
        observed.append(f"{summarize_count('positive response', len(case.positive_response_ids))} attached to this case")
    else:
        missing.append("Positive response completeness is unknown because no response record is attached")

    add_unique_text(observed, observation_summaries(case, ObservationType.POSITIVE_RESPONSE_REPORTED))
    add_unique_text(derived, observation_summaries(case, ObservationType.MULTIPLE_POSSIBLE_TICKETS))
    add_unique_text(derived, observation_summaries(case, ObservationType.DATA_GAP))

    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    inside_area = has_obs(case.observations, ObservationType.INSIDE_TICKET_AREA)
    inside_window = has_obs(case.observations, ObservationType.INSIDE_TICKET_WINDOW)
    multi_ticket = has_obs(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    data_gap = has_obs(case.observations, ObservationType.DATA_GAP)

    if no_ticket:
        reason = (
            "Locate execution support is unsupported because attached ticket context does not cover part of the activity"
            if case.ticket_ids or case.context_ticket_ids
            else "Locate execution support is missing because the backend found no plausible matching ticket for part of the activity"
        )
        return responsibility_layer(
            ResponsibilityLayerState.MISSING,
            reason,
            0.35,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if (outside_area and inside_area) or (outside_window and inside_window) or multi_ticket:
        return responsibility_layer(
            ResponsibilityLayerState.CONFLICTED,
            "Locate execution support points in conflicting ticket directions",
            0.62,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if not case.ticket_ids and not case.context_ticket_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Locate execution support is unknown because no ticket context is attached",
            0.38,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if not case.positive_response_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Locate execution completeness is unknown because no positive response record is attached",
            0.42,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if outside_area or outside_window or data_gap:
        return responsibility_layer(
            ResponsibilityLayerState.WEAK,
            "Locate execution support is incomplete or misaligned with the active work context",
            0.54,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if inside_area and inside_window:
        return responsibility_layer(
            ResponsibilityLayerState.STRONG,
            "Ticket, timing, and response support line up for the current activity",
            0.80,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    assumptions.append("Locate support is treated as usable because no direct contradiction is present")
    return responsibility_layer(
        ResponsibilityLayerState.WEAK,
        "Locate execution support exists but full area/time alignment is not directly established",
        0.57,
        observed_facts=observed,
        derived_facts=derived,
        missing_facts=missing,
        assumptions=assumptions,
    )


def evaluate_mark_layer(
    case: CaseRecord,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityLayerAssessment:
    observed: List[str] = []
    derived: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    near_asset = has_obs(case.observations, ObservationType.NEAR_ASSET)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    data_gap = has_obs(case.observations, ObservationType.DATA_GAP)

    if case.marking_ids:
        observed.append(f"{summarize_count('marking record', len(case.marking_ids))} attached to this case")
    else:
        missing.append("Mark or field-reality status is unknown because no marking record is attached")

    if case.field_report_ids:
        observed.append(f"{summarize_count('field report', len(case.field_report_ids))} attached to this case")
    else:
        missing.append("Current mark visibility or field conditions are unknown because no field report is attached")

    add_unique_text(observed, observation_summaries(case, ObservationType.MARKING_STATE_REPORTED))
    add_unique_text(observed, observation_summaries(case, ObservationType.FIELD_REPORT_PRESENT))
    add_unique_text(derived, observation_summaries(case, ObservationType.NEAR_ASSET))

    if near_asset and not case.marking_ids and not case.field_report_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Mark and field reality are unknown near a mapped asset",
            0.34,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if (outside_area or outside_window) and case.marking_ids:
        return responsibility_layer(
            ResponsibilityLayerState.CONFLICTED,
            "Mark support exists but the ticket context around the work is misaligned",
            0.58,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if not case.marking_ids or not case.field_report_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Mark and field reality support is unknown or only partially observed",
            0.44,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if data_gap:
        return responsibility_layer(
            ResponsibilityLayerState.WEAK,
            "Mark and field reality support is partial rather than directly confirmed",
            0.52,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    return responsibility_layer(
        ResponsibilityLayerState.STRONG,
        "Marking and field-report context are both attached without current contradiction",
        0.76,
        observed_facts=observed,
        derived_facts=derived,
        missing_facts=missing,
        assumptions=assumptions,
    )


def evaluate_asset_layer(
    case: CaseRecord,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityLayerAssessment:
    observed: List[str] = []
    derived: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    near_asset = has_obs(case.observations, ObservationType.NEAR_ASSET)
    far_asset = has_obs(case.observations, ObservationType.FAR_FROM_ASSET)
    data_gap = has_obs(case.observations, ObservationType.DATA_GAP)

    if case.asset_ids or case.context_asset_ids:
        observed.append(f"{summarize_count('asset', len(set(case.asset_ids + case.context_asset_ids)))} associated with this case")
    else:
        missing.append("Mapped asset context is unknown from attached case data")

    add_unique_text(derived, observation_summaries(case, ObservationType.NEAR_ASSET))
    add_unique_text(derived, observation_summaries(case, ObservationType.FAR_FROM_ASSET))

    if near_asset and far_asset:
        return responsibility_layer(
            ResponsibilityLayerState.CONFLICTED,
            "Asset proximity signals conflict across the case evidence",
            0.62,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if not case.asset_ids and not case.context_asset_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Utility records or asset context are unknown for this case",
            0.30,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if near_asset and not data_gap:
        assumptions.append("Mapped asset geometry is still a record-based proxy for field reality")
        return responsibility_layer(
            ResponsibilityLayerState.STRONG,
            "Asset records are relevant to the current activity and no asset-record conflict is present",
            0.78,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if data_gap or far_asset or not near_asset:
        assumptions.append("Asset confidence depends on mapped records rather than direct field confirmation")
        return responsibility_layer(
            ResponsibilityLayerState.WEAK,
            "Asset confidence is limited by weak proximity evidence or missing context",
            0.52,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    return responsibility_layer(
        ResponsibilityLayerState.WEAK,
        "Asset confidence is usable but not directly field-confirmed",
        0.55,
        observed_facts=observed,
        derived_facts=derived,
        missing_facts=missing,
        assumptions=assumptions,
    )


def evaluate_coordination_layer(
    case: CaseRecord,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityLayerAssessment:
    observed: List[str] = []
    derived: List[str] = []
    missing: List[str] = []
    assumptions: List[str] = []

    attachment_types = {str(observation_field(att, "record_type", "") or "") for att in case.attachments}
    if case.attachments:
        observed.append(f"{summarize_count('context attachment', len(case.attachments))} connected to this case")
    else:
        missing.append("Coordination artifacts beyond event observations are unknown")

    if case.ticket_ids and case.asset_ids:
        derived.append("Ticket and asset context are both present")
    if case.field_report_ids:
        observed.append("Field communication context is attached")
    if case.positive_response_ids:
        observed.append("Utility response context is attached")

    multi_ticket = has_obs(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    data_gap = has_obs(case.observations, ObservationType.DATA_GAP)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)

    if multi_ticket or (outside_area and outside_window):
        return responsibility_layer(
            ResponsibilityLayerState.CONFLICTED,
            "Coordination context is conflicted across candidate tickets or scope dimensions",
            0.60,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if not case.positive_response_ids or not case.field_report_ids:
        return responsibility_layer(
            ResponsibilityLayerState.UNKNOWN,
            "Coordination support is unknown across response, field, or communication artifacts",
            0.40,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if data_gap:
        return responsibility_layer(
            ResponsibilityLayerState.WEAK,
            "Coordination support is incomplete across response, field, or communication artifacts",
            0.50,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    if {"field_report", "positive_response"}.issubset(attachment_types):
        return responsibility_layer(
            ResponsibilityLayerState.STRONG,
            "Coordination artifacts connect field context and utility response without current conflict",
            0.76,
            observed_facts=observed,
            derived_facts=derived,
            missing_facts=missing,
            assumptions=assumptions,
        )

    assumptions.append("Coordination is inferred from attached identifiers rather than complete communication records")
    return responsibility_layer(
        ResponsibilityLayerState.WEAK,
        "Coordination context is present but not complete enough to treat as strong",
        0.54,
        observed_facts=observed,
        derived_facts=derived,
        missing_facts=missing,
        assumptions=assumptions,
    )


def compute_decision_support_integrity(
    layers: Dict[str, ResponsibilityLayerAssessment],
    response_posture: ResponsePosture,
    uncertainty_burden: float,
) -> DecisionSupportIntegrity:
    states = [normalize_layer_state(layer.state) for layer in layers.values()]
    conflicted = [name for name, layer in layers.items() if normalize_layer_state(layer.state) == ResponsibilityLayerState.CONFLICTED]
    missing = [name for name, layer in layers.items() if normalize_layer_state(layer.state) == ResponsibilityLayerState.MISSING]
    unknown = [name for name, layer in layers.items() if normalize_layer_state(layer.state) == ResponsibilityLayerState.UNKNOWN]
    weak = [name for name, layer in layers.items() if normalize_layer_state(layer.state) == ResponsibilityLayerState.WEAK]
    scores = [layer_state_score(state) for state in states]
    support_confidence = clamp01(avg(scores) if scores else None) or 0.0

    if conflicted:
        state = DecisionSupportState.CONFLICTED
    elif support_confidence < 0.50 or len(missing) >= 2 or len(unknown) >= 3:
        state = DecisionSupportState.DEGRADED
    elif support_confidence < 0.70 or weak or missing or unknown:
        state = DecisionSupportState.PARTIAL
    else:
        state = DecisionSupportState.SUPPORTED

    if response_posture == ResponsePosture.HOLD_WORK:
        risk = DecisionRiskLevel.CRITICAL
    elif response_posture == ResponsePosture.ESCALATE or state == DecisionSupportState.CONFLICTED:
        risk = DecisionRiskLevel.HIGH
    elif uncertainty_burden >= 0.60 or state == DecisionSupportState.DEGRADED:
        risk = DecisionRiskLevel.HIGH
    elif uncertainty_burden >= 0.40 or state == DecisionSupportState.PARTIAL:
        risk = DecisionRiskLevel.MODERATE
    else:
        risk = DecisionRiskLevel.LOW

    if conflicted:
        lead = conflicted[0]
        reason = f"{lead.title()} responsibility support is conflicted, degrading the basis for the next decision"
    elif missing:
        lead = missing[0]
        reason = f"{lead.title()} responsibility support is missing, leaving the next decision under-supported"
    elif unknown:
        lead = unknown[0]
        reason = f"{lead.title()} responsibility support is unknown, so the next decision should not treat silence as confirmation"
    elif weak:
        lead = weak[0]
        reason = f"{lead.title()} responsibility support is weak, so the next decision should not rely on procedural appearance alone"
    else:
        reason = "Responsibility support is coherent across the current case layers"

    return DecisionSupportIntegrity(
        state=state,
        decision_risk=risk,
        recommended_posture=response_posture,
        reason=reason,
        confidence=support_confidence,
    )


def build_failure_propagation(
    layers: Dict[str, ResponsibilityLayerAssessment],
    decision_support: DecisionSupportIntegrity,
) -> List[str]:
    steps: List[str] = []

    locate = layers.get("locate")
    marks = layers.get("marks")
    assets = layers.get("assets")
    coordination = layers.get("coordination")

    if locate and normalize_layer_state(locate.state) != ResponsibilityLayerState.STRONG:
        steps.append(f"Locate layer {locate.state.value.lower()} due to {locate.reason[0].lower() + locate.reason[1:] if locate.reason else 'limited support'}")

    if marks and normalize_layer_state(marks.state) != ResponsibilityLayerState.STRONG:
        steps.append("This increases uncertainty in mark and field reality")

    if assets and normalize_layer_state(assets.state) == ResponsibilityLayerState.STRONG:
        steps.append("Known nearby asset context raises the consequence of unresolved uncertainty")
    elif assets and normalize_layer_state(assets.state) != ResponsibilityLayerState.STRONG:
        steps.append("Weak asset confidence makes it harder to judge consequence reliably")

    if coordination and normalize_layer_state(coordination.state) != ResponsibilityLayerState.STRONG:
        steps.append("Coordination gaps reduce confidence that every party is working from the same support")

    steps.append(f"Decision support integrity is {decision_support.state.value.lower()}")

    deduped: List[str] = []
    add_unique_text(deduped, steps)
    return deduped


def evaluate_responsibility_integrity(
    case: CaseRecord,
    response_posture: ResponsePosture,
    uncertainty_burden: float,
    events: Sequence[Any] = (),
    tickets: Sequence[Any] = (),
    assets: Sequence[Any] = (),
) -> ResponsibilityIntegrityBundle:
    layers = {
        "excavator": evaluate_excavator_layer(case, events, tickets, assets),
        "locate": evaluate_locate_layer(case, events, tickets, assets),
        "marks": evaluate_mark_layer(case, events, tickets, assets),
        "assets": evaluate_asset_layer(case, events, tickets, assets),
        "coordination": evaluate_coordination_layer(case, events, tickets, assets),
    }
    decision_support = compute_decision_support_integrity(
        layers=layers,
        response_posture=response_posture,
        uncertainty_burden=uncertainty_burden,
    )
    return ResponsibilityIntegrityBundle(
        layers=layers,
        decision_support_integrity=decision_support,
        failure_propagation=build_failure_propagation(layers, decision_support),
    )


# ============================================================
# DECISION DEFENSIBILITY
# ============================================================

def layer_state_value(layer: Optional[ResponsibilityLayerAssessment]) -> str:
    if layer is None:
        return ResponsibilityLayerState.UNKNOWN.value
    state = getattr(layer, "state", ResponsibilityLayerState.UNKNOWN)
    return getattr(state, "value", str(state))


def evidence_statements(items: Sequence[EvidenceItem]) -> List[str]:
    return [str(item.statement) for item in items if getattr(item, "statement", None)]


def dedupe_text_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def evaluate_decision_defensibility(
    case: CaseRecord,
    evidence_layers: Optional[EvidenceLayers] = None,
    responsibility_integrity: Optional[ResponsibilityIntegrityBundle] = None,
    alignment: Optional[AlignmentAssessment] = None,
    information: Optional[InformationIntegrityAssessment] = None,
    behavior: Optional[BehavioralRiskAssessment] = None,
    temporal_change: Optional[Dict[str, Any]] = None,
    response_posture: Optional[ResponsePosture] = None,
) -> DecisionDefensibilityEvaluation:
    """
    Evaluate whether the current decision basis would hold up under scrutiny.

    This measures support quality only. It does not assign legal fault, crew
    skill, or blame.
    """
    evidence_layers = evidence_layers or build_evidence_layers(case)
    responsibility_integrity = responsibility_integrity or getattr(case, "responsibility_integrity", None) or ResponsibilityIntegrityBundle()
    alignment = alignment or evaluate_alignment(case)
    information = information or evaluate_information_integrity(case)
    behavior = behavior or evaluate_behavioral_risk(case)
    temporal_change = temporal_change or {}

    layers = responsibility_integrity.layers or {}
    dsi = responsibility_integrity.decision_support_integrity
    dsi_state = getattr(getattr(dsi, "state", None), "value", str(getattr(dsi, "state", ""))).upper()

    layer_states = {name: layer_state_value(layer).upper() for name, layer in layers.items()}
    conflicted_layers = [name for name, state in layer_states.items() if state == ResponsibilityLayerState.CONFLICTED.value]
    missing_layers = [name for name, state in layer_states.items() if state == ResponsibilityLayerState.MISSING.value]
    unknown_layers = [name for name, state in layer_states.items() if state == ResponsibilityLayerState.UNKNOWN.value]
    weak_layers = [name for name, state in layer_states.items() if state == ResponsibilityLayerState.WEAK.value]

    observed_count = len(evidence_layers.observed or [])
    derived_statements = evidence_statements(evidence_layers.derived or [])
    inferred_count = len(evidence_layers.inferred or [])
    assumed_count = len(evidence_layers.assumed or [])

    near_asset = has_obs(case.observations, ObservationType.NEAR_ASSET)
    outside_scope = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA) or has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    multi_ticket = has_obs(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    continuing_under_conflict = bool(getattr(behavior, "conflicting_signals_ignored", False))
    trend = str(temporal_change.get("trend") or "").upper()

    strong_alignment = (
        safe_float(alignment.spatial_alignment) >= 0.75
        and safe_float(alignment.temporal_alignment) >= 0.75
        and safe_float(alignment.ticket_match_strength) >= 0.75
    )
    weak_alignment = (
        safe_float(alignment.spatial_alignment, 1.0) < 0.45
        or safe_float(alignment.temporal_alignment, 1.0) < 0.45
        or safe_float(alignment.ticket_match_strength, 1.0) < 0.45
    )
    strong_process = dsi_state == DecisionSupportState.SUPPORTED.value and not conflicted_layers and not missing_layers
    complete_verification = bool(case.field_report_ids and case.marking_ids and case.positive_response_ids)
    high_assumption_load = (assumed_count >= 3 and not complete_verification) or len(unknown_layers) >= 2 or len(missing_layers) >= 1
    direct_conflict_near_asset = near_asset and (outside_scope or no_ticket or bool(conflicted_layers))
    degraded_continuation = response_posture == ResponsePosture.HOLD_WORK or continuing_under_conflict or dsi_state in {
        DecisionSupportState.DEGRADED.value,
        DecisionSupportState.CONFLICTED.value,
    }

    components: Dict[str, str] = {}
    weaknesses: List[str] = []

    if observed_count >= 2 and not missing_layers and not no_ticket:
        components["evidence_sufficiency"] = "Observed and derived evidence are sufficient for the current decision frame"
    elif missing_layers or no_ticket:
        components["evidence_sufficiency"] = "Critical support is missing from the decision record"
        weaknesses.append("Critical support is missing from the decision record")
    else:
        components["evidence_sufficiency"] = "Evidence is partial and should be verified before relying on it"
        weaknesses.append("Evidence is partial")

    if strong_alignment and strong_process:
        components["method_appropriateness"] = "Ticket timing, ticket zone, and responsibility support align with the work method"
    elif weak_alignment or outside_scope or no_ticket:
        components["method_appropriateness"] = "Ticket or zone support does not adequately cover the observed work method"
        weaknesses.append("Ticket/time/zone support is weak for the observed work")
    else:
        components["method_appropriateness"] = "Method support is usable but not strong enough to stand alone"

    if conflicted_layers or multi_ticket or (near_asset and outside_scope):
        components["consistency"] = "Signals conflict across responsibility, ticket, or asset context"
        weaknesses.append("Signals conflict across the case record")
    elif weak_layers or unknown_layers:
        components["consistency"] = "Signals are not directly contradictory, but support quality is uneven"
    else:
        components["consistency"] = "Signals are consistent across the evaluated layers"

    if complete_verification and not missing_layers and not unknown_layers:
        components["verification_depth"] = "Field report, marking, and positive-response context are attached"
    elif complete_verification:
        components["verification_depth"] = "Verification artifacts exist, but unresolved weak or conflicting layers remain"
        weaknesses.append("Verification artifacts do not resolve the weak layers")
    else:
        components["verification_depth"] = "Verification depth is limited across field report, marking, or response artifacts"
        weaknesses.append("Verification depth is limited")

    if high_assumption_load:
        components["assumption_load"] = "Decision support depends on unresolved assumptions or unknown/missing layers"
        weaknesses.append("Assumption load is high")
    elif assumed_count > 0 or inferred_count > 0:
        components["assumption_load"] = "Some assumptions remain, but they are bounded by observed support"
    else:
        components["assumption_load"] = "Assumption load is low"

    if trend == "WORSENING":
        components["temporal_context"] = "Temporal trend is worsening"
        weaknesses.append("Temporal trend is worsening")
    elif trend == "IMPROVING":
        components["temporal_context"] = "Temporal trend is improving, which supports but does not replace verification"
    elif trend:
        components["temporal_context"] = f"Temporal trend is {trend.lower()}"

    if direct_conflict_near_asset:
        state = DecisionDefensibilityState.LOW
        decision_risk = DecisionRiskLevel.HIGH
        reason = "Signals conflict or critical support is unsupported near mapped asset context, so a proceed decision would not hold under scrutiny"
        defensible_decision = "HOLD_OR_REVERIFY"
    elif degraded_continuation or missing_layers or high_assumption_load or weak_alignment:
        state = DecisionDefensibilityState.LOW
        decision_risk = DecisionRiskLevel.HIGH
        reason = "A proceed decision would rely on degraded support, unsupported facts, or unresolved assumptions"
        defensible_decision = "HOLD_OR_REVERIFY"
    elif strong_alignment and complete_verification and not conflicted_layers and not missing_layers and not unknown_layers and not weaknesses:
        state = DecisionDefensibilityState.HIGH
        decision_risk = DecisionRiskLevel.LOW
        if response_posture == ResponsePosture.VERIFY_BEFORE_PROCEEDING:
            reason = "The record strongly supports a defensible verify-before-proceeding decision"
            defensible_decision = "VERIFY_BEFORE_PROCEEDING"
        elif response_posture == ResponsePosture.VERIFY:
            reason = "The record strongly supports a defensible verification decision"
            defensible_decision = "VERIFY"
        else:
            reason = "Evidence, process support, signal consistency, and verification depth are aligned"
            defensible_decision = "CURRENT_POSTURE"
    else:
        state = DecisionDefensibilityState.MODERATE
        decision_risk = DecisionRiskLevel.MODERATE
        reason = "The decision basis is usable, but review defensibility depends on documenting verification steps"
        defensible_decision = "VERIFY_AND_DOCUMENT"

    if state == DecisionDefensibilityState.HIGH and derived_statements:
        components["bounded_concerns"] = "; ".join(derived_statements[:2])

    return DecisionDefensibilityEvaluation(
        state=state,
        decision_risk=decision_risk,
        reason=reason,
        components=components,
        key_weaknesses=dedupe_text_preserve_order(weaknesses)[:6],
        defensible_decision=defensible_decision,
    )


# ============================================================
# FAILURE LAYERS
# ============================================================

def determine_failure_layers(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
) -> List[FailureLayer]:
    layers: List[FailureLayer] = []
    match_strength = alignment.ticket_match_strength or 0.0
    info_confidence = information.overall_confidence or 0.0
    has_no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    has_outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    has_outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    has_data_gap = has_obs(case.observations, ObservationType.DATA_GAP)
    has_multi_ticket = has_obs(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS)
    has_repeated = has_obs(case.observations, ObservationType.REPEATED_ACTIVITY)
    has_escalating = has_obs(case.observations, ObservationType.ESCALATING_ACTIVITY)
    has_trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)

    if has_no_ticket or has_multi_ticket or (
        match_strength < 0.50 and (has_outside_area or has_outside_window)
    ):
        layers.append(FailureLayer.AUTHORIZATION_AMBIGUITY)

    if info_confidence < 0.45 or (
        has_data_gap and info_confidence < 0.60
    ) or (
        has_multi_ticket and has_data_gap
    ):
        layers.append(FailureLayer.CONTEXT_LIMITATION)

    if behavior.conflicting_signals_ignored or (
        behavior.habit_risk and behavior.habit_risk >= 0.60
    ):
        layers.append(FailureLayer.HABIT_CONTINUATION)

    if has_no_ticket or has_outside_window or has_data_gap:
        layers.append(FailureLayer.PROCESS_BYPASS_OR_GAP)

    if has_trenchless:
        layers.append(FailureLayer.LIMITED_VISIBILITY_WORK)

    if has_escalating or (
        has_repeated and match_strength < 0.50
    ):
        layers.append(FailureLayer.CHANGING_SITE_CONDITIONS)

    deduped: List[FailureLayer] = []
    seen = set()
    for layer in layers:
        if layer not in seen:
            deduped.append(layer)
            seen.add(layer)

    return deduped


# ============================================================
# DECISION / URGENCY / RESPONSE
# ============================================================

def compute_uncertainty_burden(
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    case: CaseRecord,
) -> float:
    burden = 0.0

    match_strength = alignment.ticket_match_strength or 0.0
    info_conf = information.overall_confidence or 0.0
    habit_risk = behavior.habit_risk or 0.0

    burden += (1.0 - match_strength) * 0.35
    burden += (1.0 - info_conf) * 0.45
    burden += habit_risk * 0.20

    if has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR):
        burden += 0.08
    if has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR):
        burden += 0.07
    if has_obs(case.observations, ObservationType.NO_MATCHING_TICKET):
        burden += 0.10

    return clamp01(burden) or 0.0


def determine_decision_state(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    uncertainty_burden: float,
) -> DecisionState:
    match_strength = alignment.ticket_match_strength or 0.0
    info_conf = information.overall_confidence or 0.0
    habit_risk = behavior.habit_risk or 0.0

    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)

    if no_ticket and (heavy or trenchless or behavior.repeated_activity or behavior.escalating_activity):
        return DecisionState.STOP_WORK

    if (outside_area or outside_window) and (heavy or trenchless) and habit_risk >= 0.45:
        return DecisionState.STOP_WORK

    # Strong contradiction plus consequential work should escalate even when it
    # is not severe enough to force an outright stop.
    if (outside_area or outside_window) and (heavy or trenchless):
        return DecisionState.HIGH_RISK_OF_MISJUDGMENT

    if uncertainty_burden >= 0.70:
        return DecisionState.HIGH_RISK_OF_MISJUDGMENT

    if match_strength < 0.45 and info_conf < 0.55:
        return DecisionState.HIGH_RISK_OF_MISJUDGMENT

    if habit_risk >= 0.60 and (outside_area or outside_window or no_ticket):
        return DecisionState.HIGH_RISK_OF_MISJUDGMENT

    if uncertainty_burden >= 0.40:
        return DecisionState.PROCEED_WITH_VERIFICATION

    if match_strength >= 0.70 and info_conf >= 0.70 and habit_risk < 0.35:
        return DecisionState.SAFE_TO_PROCEED

    return DecisionState.PROCEED_WITH_VERIFICATION


def determine_urgency(
    case: CaseRecord,
    decision_state: DecisionState,
    behavior: BehavioralRiskAssessment,
    uncertainty_burden: float,
) -> UrgencyLevel:
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)

    if decision_state == DecisionState.STOP_WORK:
        return UrgencyLevel.CRITICAL

    if decision_state == DecisionState.HIGH_RISK_OF_MISJUDGMENT:
        if heavy or trenchless or behavior.escalating_activity:
            return UrgencyLevel.CRITICAL
        return UrgencyLevel.HIGH

    if decision_state == DecisionState.PROCEED_WITH_VERIFICATION:
        if uncertainty_burden >= 0.60 or heavy:
            return UrgencyLevel.HIGH
        return UrgencyLevel.MODERATE

    return UrgencyLevel.LOW


def determine_response_posture(
    decision_state: DecisionState,
    urgency: UrgencyLevel,
) -> ResponsePosture:
    if decision_state == DecisionState.STOP_WORK:
        return ResponsePosture.HOLD_WORK

    if decision_state == DecisionState.HIGH_RISK_OF_MISJUDGMENT:
        return ResponsePosture.ESCALATE

    if decision_state == DecisionState.PROCEED_WITH_VERIFICATION:
        return ResponsePosture.VERIFY_BEFORE_PROCEEDING

    if urgency == UrgencyLevel.MODERATE:
        return ResponsePosture.VERIFY

    return ResponsePosture.MONITOR
