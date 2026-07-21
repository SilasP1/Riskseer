"""
case_temporal.py

GOAL
----
This file interprets how a CaseRecord changes over time relative to prior
saved state.

Riskseer is not just trying to label a current case. It must also detect
whether a case is new, stable, worsening, improving, or reactivated so that
operators do not treat changing situations like static snapshots.

WHAT case_temporal.py DOES
--------------------------
1. Builds compact state snapshots from current case evaluation outputs.
2. Extracts prior snapshots from saved case data when available.
3. Compares current and prior state.
4. Classifies temporal change:
   - NEW
   - WORSENING
   - STABLE
   - IMPROVING
   - REACTIVATED
5. Produces structured change deltas.
6. Computes investigation ROI using current state plus temporal context.

WHAT case_temporal.py MUST NOT DO
---------------------------------
1. It must not group events into cases. case.py owns that.
2. It must not parse raw CSV inputs. main.py / normalization layers own that.
3. It must not evaluate current alignment, information integrity, or behavioral risk from scratch.
   case_evaluation.py owns that.
4. It must not generate polished operator prose. explanations.py / orchestration layers own that.
5. It must not fabricate change when no prior state exists.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from schemas import (
    AlignmentAssessment,
    BehavioralRiskAssessment,
    CaseRecord,
    DecisionState,
    InformationIntegrityAssessment,
    ResponsePosture,
    UrgencyLevel,
)

MAX_SCORE = 1.0
MIN_SCORE = 0.0
TREND_DELTA_EPSILON = 0.05


def avg(values: Sequence[float]) -> Optional[float]:
    cleaned = [v for v in values if v is not None]
    if not cleaned:
        return None
    return sum(cleaned) / len(cleaned)


def clamp01(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(MIN_SCORE, min(MAX_SCORE, value))


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


def safe_str(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def observation_field(obs: object, field: str, default: object = None) -> object:
    if isinstance(obs, dict):
        return obs.get(field, default)
    return getattr(obs, field, default)


def observation_type_value(obs: object) -> str:
    raw_type = observation_field(obs, "observation_type")
    return str(getattr(raw_type, "value", raw_type) or "")


def normalize_shift_label(value: Any, default: str = "unchanged") -> str:
    text = safe_str(value, default).lower()
    if text in {"improved", "degraded", "unchanged", "none", "minor", "major", "increased", "stable", "decreased", "upgraded", "downgraded", "same", "escalated", "deescalated"}:
        return text
    return default


def classify_support_band(score: float) -> str:
    if score >= 0.8:
        return "aligned"
    if score >= 0.5:
        return "partial"
    return "weak"


def classify_confidence_level(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def latest_event_observation(case: CaseRecord) -> Dict[str, Any]:
    latest: Optional[Dict[str, Any]] = None
    latest_time = ""
    for obs in case.observations:
        if observation_type_value(obs) != "EVENT_SEEN":
            continue
        metadata = observation_field(obs, "metadata", {}) or {}
        when = safe_str(metadata.get("event_time"), "")
        if when >= latest_time:
            latest_time = when
            latest = {
                "activity_type": safe_str(observation_field(obs, "value"), "unknown"),
                "equipment_type": safe_str(metadata.get("equipment_type"), "unknown"),
            }
    return latest or {"activity_type": "unknown", "equipment_type": "unknown"}


def classify_equipment_class(equipment_type: str) -> str:
    normalized = safe_str(equipment_type).lower()
    if normalized in {"hdd rig", "directional drill", "drill"}:
        return "trenchless"
    if normalized in {"backhoe", "excavator", "trackhoe"}:
        return "heavy_machine"
    if normalized in {"mini excavator", "vac truck", "skid steer"}:
        return "light_machine"
    if normalized in {"hand crew", "hand tools", "inspection"}:
        return "hand_crew"
    return "unknown"


def equipment_rank(equipment_class: str) -> int:
    return {
        "unknown": 0,
        "hand_crew": 1,
        "light_machine": 2,
        "heavy_machine": 3,
        "trenchless": 4,
    }.get(equipment_class, 0)


def classify_asset_proximity(case: CaseRecord) -> str:
    near_asset = any(observation_type_value(obs) == "NEAR_ASSET" for obs in case.observations)
    if near_asset:
        return "near"
    return "far"


def classify_ticket_time_conflict(case: CaseRecord, temporal_alignment: float) -> str:
    outside_window = any(observation_type_value(obs) == "OUTSIDE_TICKET_WINDOW" for obs in case.observations)
    inside_window = any(observation_type_value(obs) == "INSIDE_TICKET_WINDOW" for obs in case.observations)
    multi_ticket = any(observation_type_value(obs) == "MULTIPLE_POSSIBLE_TICKETS" for obs in case.observations)

    if outside_window and inside_window:
        return "conflicting"
    if outside_window or (multi_ticket and temporal_alignment < 0.8):
        return "partial"
    return "none"


def derive_spatial_shift(current_area: float, prior_area: float, current_proximity: str, prior_proximity: str) -> str:
    delta = current_area - prior_area
    if current_proximity != prior_proximity and abs(delta) >= 0.1:
        return "major"
    if abs(delta) >= 0.2:
        return "major"
    if abs(delta) >= 0.05:
        return "minor"
    return "none"


def derive_timing_shift(current_timing: float, prior_timing: float, current_conflict: str, prior_conflict: str) -> str:
    delta = current_timing - prior_timing
    if current_conflict != prior_conflict and current_conflict == "conflicting":
        return "degraded"
    if delta <= -TREND_DELTA_EPSILON:
        return "degraded"
    if delta >= TREND_DELTA_EPSILON:
        return "improved"
    return "unchanged"


def derive_operational_shift(
    current_activity: str,
    prior_activity: str,
    current_equipment_class: str,
    prior_equipment_class: str,
) -> str:
    current_rank = equipment_rank(current_equipment_class)
    prior_rank = equipment_rank(prior_equipment_class)
    excavation_terms = {"excavation", "digging", "boring", "inspection"}
    if current_rank > prior_rank:
        return "escalated"
    if current_rank < prior_rank:
        return "deescalated"
    if current_activity != prior_activity:
        if safe_str(current_activity).lower() in excavation_terms and safe_str(prior_activity).lower() not in excavation_terms:
            return "escalated"
        if safe_str(prior_activity).lower() in excavation_terms and safe_str(current_activity).lower() not in excavation_terms:
            return "deescalated"
    return "none"


def derive_uncertainty_shift(current_support: float, prior_support: float) -> str:
    delta = current_support - prior_support
    if delta <= -TREND_DELTA_EPSILON:
        return "increased"
    if delta >= TREND_DELTA_EPSILON:
        return "decreased"
    return "stable"


def derive_posture_shift(current_posture: str, prior_posture: str) -> str:
    posture_rank = {
        "MONITOR": 1,
        "VERIFY": 2,
        "VERIFY_BEFORE_PROCEEDING": 3,
        "ESCALATE": 4,
        "HOLD_WORK": 5,
    }
    current_rank = posture_rank.get(safe_str(current_posture, "MONITOR").upper(), 1)
    prior_rank = posture_rank.get(safe_str(prior_posture, "MONITOR").upper(), 1)
    if current_rank > prior_rank:
        return "upgraded"
    if current_rank < prior_rank:
        return "downgraded"
    return "same"


def build_hidden_risk_assessment(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    response_posture: ResponsePosture,
) -> Dict[str, Any]:
    active = safe_str(case.status, "ACTIVE").upper() == "ACTIVE"
    posture = safe_str(getattr(response_posture, "value", response_posture), "MONITOR").upper()
    ticket_count = len(case.ticket_ids or []) + len(case.context_ticket_ids or [])
    routine_appearance_score = 0
    if ticket_count > 0:
        routine_appearance_score += 35
    if (alignment.spatial_alignment or 0.0) >= 0.75:
        routine_appearance_score += 25
    if (alignment.temporal_alignment or 0.0) >= 0.75:
        routine_appearance_score += 20
    if posture in {"MONITOR", "VERIFY_BEFORE_PROCEEDING"}:
        routine_appearance_score += 20

    support_weakness_score = 0
    if (alignment.temporal_alignment or 1.0) < 0.8:
        support_weakness_score += 30
    if (alignment.spatial_alignment or 1.0) < 0.8:
        support_weakness_score += 20
    if (information.overall_confidence or 1.0) < 0.55:
        support_weakness_score += 25
    if any("conflict" in item.lower() or "ambig" in item.lower() for item in (information.concerns or [])):
        support_weakness_score += 25

    consequence_score = 0
    near_asset = any(observation_type_value(obs) == "NEAR_ASSET" for obs in case.observations)
    far_asset = any(observation_type_value(obs) == "FAR_FROM_ASSET" for obs in case.observations)
    heavy = any(observation_type_value(obs) == "HEAVY_EQUIPMENT_INDICATOR" for obs in case.observations)
    trenchless = any(observation_type_value(obs) == "TRENCHLESS_INDICATOR" for obs in case.observations)
    if near_asset:
        consequence_score += 35
    if near_asset and far_asset:
        consequence_score += 20
    if heavy:
        consequence_score += 35
    if trenchless:
        consequence_score += 30

    intervention_gap_score = 0
    if posture == "MONITOR":
        intervention_gap_score += 45
    elif posture == "VERIFY_BEFORE_PROCEEDING":
        intervention_gap_score += 30
    elif posture == "ESCALATE":
        intervention_gap_score += 15
    elif posture == "HOLD_WORK":
        intervention_gap_score += 0

    score = round(
        min(
            100.0,
            max(
                0.0,
                (routine_appearance_score * 0.30)
                + (support_weakness_score * 0.30)
                + (consequence_score * 0.25)
                + (intervention_gap_score * 0.15),
            ),
        ),
        2,
    )

    if not active or posture == "HOLD_WORK":
        score = min(score, 35.0)

    if score >= 80:
        band = "most_missable"
    elif score >= 60:
        band = "meaningful_candidate"
    elif score >= 30:
        band = "worth_awareness"
    else:
        band = "low_missability"

    return {
        "score": score,
        "band": band,
        "components": {
            "routine_appearance_score": min(routine_appearance_score, 100),
            "support_weakness_score": min(support_weakness_score, 100),
            "consequence_if_waved_through_score": min(consequence_score, 100),
            "intervention_gap_score": min(intervention_gap_score, 100),
        },
        "eligible": active and posture != "HOLD_WORK",
    }


def build_case_state_snapshot(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    decision_state: DecisionState,
    urgency: UrgencyLevel,
    response_posture: ResponsePosture,
    uncertainty_burden: float,
    confidence: Optional[float],
    hidden_risk: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    latest_event = latest_event_observation(case)
    activity_type_current = latest_event["activity_type"]
    equipment_type_current = latest_event["equipment_type"]
    equipment_class_current = classify_equipment_class(equipment_type_current)
    area_support_current = clamp01(alignment.spatial_alignment) or 0.0
    timing_support_current = clamp01(alignment.temporal_alignment) or 0.0
    asset_proximity_current = classify_asset_proximity(case)
    support_strength_current = clamp01(
        avg([
            alignment.ticket_match_strength,
            information.overall_confidence,
        ])
    ) or 0.0

    return {
        "decision_state": decision_state.value,
        "urgency": urgency.value,
        "response_posture": response_posture.value,
        "confidence": clamp01(confidence) or 0.0,
        "uncertainty_burden": clamp01(uncertainty_burden) or 0.0,
        "alignment_score": clamp01(alignment.ticket_match_strength) or 0.0,
        "spatial_alignment": clamp01(alignment.spatial_alignment) or 0.0,
        "temporal_alignment": clamp01(alignment.temporal_alignment) or 0.0,
        "asset_relevance": clamp01(alignment.asset_relevance) or 0.0,
        "information_confidence": clamp01(information.overall_confidence) or 0.0,
        "behavioral_risk": clamp01(behavior.habit_risk) or 0.0,
        "event_count": len(case.event_ids),
        "ticket_count": len(case.ticket_ids),
        "asset_count": len(case.asset_ids),
        "repeated_activity": bool(behavior.repeated_activity),
        "escalating_activity": bool(behavior.escalating_activity),
        "status": str(case.status or ""),
        "dimensions": {
            "spatial": {
                "spatial_shift": "none",
                "area_support_current": area_support_current,
                "asset_proximity_current": asset_proximity_current,
            },
            "temporal": {
                "timing_support_current": timing_support_current,
                "ticket_time_conflict_current": classify_ticket_time_conflict(case, timing_support_current),
                "timing_shift": "unchanged",
            },
            "operational": {
                "activity_type_current": activity_type_current,
                "equipment_type_current": equipment_type_current,
                "equipment_class_current": equipment_class_current,
                "operational_shift": "none",
            },
            "support": {
                "support_strength_current": support_strength_current,
                "confidence_current": classify_confidence_level(clamp01(confidence) or 0.0),
                "uncertainty_shift": "stable",
            },
            "decision": {
                "posture_current": response_posture.value,
                "urgency_current": urgency.value,
                "posture_shift": "same",
            },
            "hidden_risk": {
                "current": hidden_risk or {"score": 0.0, "band": "low_missability", "components": {}, "eligible": False},
                "prior": None,
                "delta": 0.0,
            },
        },
    }


def extract_prior_snapshot(prior_case_data: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not prior_case_data:
        return None

    metadata = prior_case_data.get("metadata", {}) or {}
    snapshot = metadata.get("state_snapshot")
    if isinstance(snapshot, dict):
        return snapshot

    evaluation = prior_case_data.get("evaluation", {}) or {}
    alignment = evaluation.get("alignment", {}) or {}
    info = evaluation.get("information_integrity", {}) or {}
    behavior = evaluation.get("behavioral_risk", {}) or {}

    event_observations = prior_case_data.get("observations", []) or []
    latest_observation = None
    latest_time = ""
    for obs in event_observations:
        if obs.get("observation_type") != "EVENT_SEEN":
            continue
        when = safe_str((obs.get("metadata") or {}).get("event_time"), "")
        if when >= latest_time:
            latest_time = when
            latest_observation = obs

    prior_activity_type = safe_str((latest_observation or {}).get("value"), "unknown")
    prior_equipment_type = safe_str(((latest_observation or {}).get("metadata") or {}).get("equipment_type"), "unknown")
    prior_equipment_class = classify_equipment_class(prior_equipment_type)
    prior_spatial = safe_float(alignment.get("spatial_alignment"), 0.0)
    prior_temporal = safe_float(alignment.get("temporal_alignment"), 0.0)
    prior_support = safe_float(avg([
        safe_float(alignment.get("ticket_match_strength"), 0.0),
        safe_float(info.get("overall_confidence"), 0.0),
    ]), 0.0)
    prior_asset_proximity = "near" if any(obs.get("observation_type") == "NEAR_ASSET" for obs in event_observations) else "far"

    return {
        "decision_state": normalize_decision_state(evaluation.get("decision_state")),
        "urgency": normalize_decision_state(evaluation.get("urgency")),
        "response_posture": normalize_decision_state(evaluation.get("response_posture")),
        "confidence": safe_float(evaluation.get("confidence"), 0.0),
        "uncertainty_burden": safe_float(evaluation.get("uncertainty_burden"), 0.0),
        "alignment_score": safe_float(alignment.get("ticket_match_strength"), 0.0),
        "spatial_alignment": safe_float(alignment.get("spatial_alignment"), 0.0),
        "temporal_alignment": safe_float(alignment.get("temporal_alignment"), 0.0),
        "asset_relevance": safe_float(alignment.get("asset_relevance"), 0.0),
        "information_confidence": safe_float(info.get("overall_confidence"), 0.0),
        "behavioral_risk": safe_float(behavior.get("habit_risk"), 0.0),
        "event_count": len(prior_case_data.get("event_ids", [])),
        "ticket_count": len(prior_case_data.get("ticket_ids", [])),
        "asset_count": len(prior_case_data.get("asset_ids", [])),
        "repeated_activity": bool(behavior.get("repeated_activity")),
        "escalating_activity": bool(behavior.get("escalating_activity")),
        "status": str(prior_case_data.get("status") or ""),
        "dimensions": {
            "spatial": {
                "area_support_current": prior_spatial,
                "asset_proximity_current": prior_asset_proximity,
                "spatial_shift": "none",
            },
            "temporal": {
                "timing_support_current": prior_temporal,
                "ticket_time_conflict_current": "partial" if prior_temporal < 0.8 else "none",
                "timing_shift": "unchanged",
            },
            "operational": {
                "activity_type_current": prior_activity_type,
                "equipment_type_current": prior_equipment_type,
                "equipment_class_current": prior_equipment_class,
                "operational_shift": "none",
            },
            "support": {
                "support_strength_current": prior_support,
                "confidence_current": classify_confidence_level(safe_float(evaluation.get("confidence"), 0.0)),
                "uncertainty_shift": "stable",
            },
            "decision": {
                "posture_current": normalize_decision_state(evaluation.get("response_posture")),
                "urgency_current": normalize_decision_state(evaluation.get("urgency")),
                "posture_shift": "same",
            },
            "hidden_risk": {
                "current": (metadata.get("hidden_risk") or {}).get("current")
                or metadata.get("hidden_risk")
                or {"score": 0.0, "band": "low_missability", "components": {}, "eligible": False},
                "prior": None,
                "delta": 0.0,
            },
        },
    }


def classify_decision_worsening(current_decision_state: str, prior_decision_state: str) -> int:
    priority = {
        "STOP_WORK": 4,
        "HIGH_RISK_OF_MISJUDGMENT": 3,
        "PROCEED_WITH_VERIFICATION": 2,
        "SAFE_TO_PROCEED": 1,
        "NEEDS_REVIEW": 0,
        "UNKNOWN": 0,
    }
    return priority.get(current_decision_state, 0) - priority.get(prior_decision_state, 0)


def build_temporal_change_summary(
    current_snapshot: Dict[str, Any],
    prior_snapshot: Optional[Dict[str, Any]],
    case: CaseRecord,
) -> Dict[str, Any]:
    if not prior_snapshot:
        current_dims = current_snapshot.get("dimensions", {})
        return {
            "trend": "NEW",
            "decision_shift": "NEW",
            "confidence_delta": 0.0,
            "uncertainty_delta": 0.0,
            "alignment_delta": 0.0,
            "event_count_delta": 0,
            "status_changed": False,
            "change_summary": {
                "spatial_shift": "none",
                "timing_shift": "unchanged",
                "operational_shift": "none",
                "uncertainty_shift": "stable",
                "posture_shift": "same",
            },
            "state_dimensions": {
                "current": current_dims,
                "prior": None,
            },
            "true_what_changed": ["This is a newly created case"],
        }

    confidence_delta = current_snapshot["confidence"] - safe_float(prior_snapshot.get("confidence"), 0.0)
    uncertainty_delta = current_snapshot["uncertainty_burden"] - safe_float(prior_snapshot.get("uncertainty_burden"), 0.0)
    alignment_delta = current_snapshot["alignment_score"] - safe_float(prior_snapshot.get("alignment_score"), 0.0)
    event_count_delta = int(current_snapshot["event_count"]) - int(prior_snapshot.get("event_count", 0))
    decision_shift_score = classify_decision_worsening(
        current_snapshot["decision_state"],
        normalize_decision_state(prior_snapshot.get("decision_state")),
    )

    current_status = str(current_snapshot.get("status") or "").upper()
    prior_status = str(prior_snapshot.get("status") or "").upper()
    status_changed = current_status != prior_status and bool(prior_status or current_status)

    current_dimensions = current_snapshot.get("dimensions", {}) or {}
    prior_dimensions = prior_snapshot.get("dimensions", {}) or {}
    current_spatial = current_dimensions.get("spatial", {}) or {}
    prior_spatial = prior_dimensions.get("spatial", {}) or {}
    current_temporal = current_dimensions.get("temporal", {}) or {}
    prior_temporal = prior_dimensions.get("temporal", {}) or {}
    current_operational = current_dimensions.get("operational", {}) or {}
    prior_operational = prior_dimensions.get("operational", {}) or {}
    current_support = current_dimensions.get("support", {}) or {}
    prior_support = prior_dimensions.get("support", {}) or {}
    current_decision = current_dimensions.get("decision", {}) or {}
    prior_decision = prior_dimensions.get("decision", {}) or {}
    current_hidden = (current_dimensions.get("hidden_risk", {}) or {}).get("current") or {}
    prior_hidden = (prior_dimensions.get("hidden_risk", {}) or {}).get("current") or {}

    spatial_shift = derive_spatial_shift(
        safe_float(current_spatial.get("area_support_current"), 0.0),
        safe_float(prior_spatial.get("area_support_current"), 0.0),
        safe_str(current_spatial.get("asset_proximity_current"), "far"),
        safe_str(prior_spatial.get("asset_proximity_current"), "far"),
    )
    timing_shift = derive_timing_shift(
        safe_float(current_temporal.get("timing_support_current"), 0.0),
        safe_float(prior_temporal.get("timing_support_current"), 0.0),
        safe_str(current_temporal.get("ticket_time_conflict_current"), "none"),
        safe_str(prior_temporal.get("ticket_time_conflict_current"), "none"),
    )
    operational_shift = derive_operational_shift(
        safe_str(current_operational.get("activity_type_current"), "unknown"),
        safe_str(prior_operational.get("activity_type_current"), "unknown"),
        safe_str(current_operational.get("equipment_class_current"), "unknown"),
        safe_str(prior_operational.get("equipment_class_current"), "unknown"),
    )
    uncertainty_shift = derive_uncertainty_shift(
        safe_float(current_support.get("support_strength_current"), 0.0),
        safe_float(prior_support.get("support_strength_current"), 0.0),
    )
    posture_shift = derive_posture_shift(
        safe_str(current_decision.get("posture_current"), "MONITOR"),
        safe_str(prior_decision.get("posture_current"), "MONITOR"),
    )

    change_summary = {
        "spatial_shift": spatial_shift,
        "timing_shift": timing_shift,
        "operational_shift": operational_shift,
        "uncertainty_shift": uncertainty_shift,
        "posture_shift": posture_shift,
    }
    hidden_risk_delta = round(safe_float(current_hidden.get("score"), 0.0) - safe_float(prior_hidden.get("score"), 0.0), 2)
    hidden_component_delta = {
        key: round(safe_float((current_hidden.get("components") or {}).get(key), 0.0) - safe_float((prior_hidden.get("components") or {}).get(key), 0.0), 2)
        for key in {
            "routine_appearance_score",
            "support_weakness_score",
            "consequence_if_waved_through_score",
            "intervention_gap_score",
        }
    }

    worsening_signals = 0
    improving_signals = 0

    if alignment_delta < -TREND_DELTA_EPSILON:
        worsening_signals += 1
    elif alignment_delta > TREND_DELTA_EPSILON:
        improving_signals += 1

    if confidence_delta < -TREND_DELTA_EPSILON:
        worsening_signals += 1
    elif confidence_delta > TREND_DELTA_EPSILON:
        improving_signals += 1

    if uncertainty_delta > TREND_DELTA_EPSILON:
        worsening_signals += 1
    elif uncertainty_delta < -TREND_DELTA_EPSILON:
        improving_signals += 1

    if decision_shift_score > 0 or posture_shift == "upgraded":
        worsening_signals += 2
    elif decision_shift_score < 0 or posture_shift == "downgraded":
        improving_signals += 2

    if timing_shift == "degraded":
        worsening_signals += 1
    elif timing_shift == "improved":
        improving_signals += 1

    if uncertainty_shift == "increased":
        worsening_signals += 1
    elif uncertainty_shift == "decreased":
        improving_signals += 1

    if operational_shift == "escalated":
        worsening_signals += 1
    elif operational_shift == "deescalated":
        improving_signals += 1

    if hidden_risk_delta >= 10:
        worsening_signals += 1
    elif hidden_risk_delta <= -10:
        improving_signals += 1

    current_posture = safe_str(current_decision.get("posture_current"), "MONITOR").upper()
    current_area_support = safe_float(current_spatial.get("area_support_current"), 0.0)
    current_timing_support = safe_float(current_temporal.get("timing_support_current"), 0.0)
    support_still_critically_weak = current_area_support < 0.45 or current_timing_support < 0.45
    support_or_posture_improved = (
        alignment_delta > TREND_DELTA_EPSILON
        or confidence_delta > TREND_DELTA_EPSILON
        or uncertainty_delta < -TREND_DELTA_EPSILON
        or posture_shift == "downgraded"
        or timing_shift == "improved"
        or uncertainty_shift == "decreased"
    )

    if event_count_delta > 0 and (alignment_delta < -TREND_DELTA_EPSILON or uncertainty_delta > TREND_DELTA_EPSILON):
        worsening_signals += 1

    if prior_status == "CLOSED" and current_status in {"ACTIVE", "INACTIVE"} and event_count_delta > 0:
        trend = "REACTIVATED"
    elif worsening_signals >= 2:
        trend = "WORSENING"
    elif (
        improving_signals >= 2
        and worsening_signals == 0
        and support_or_posture_improved
        and not (current_posture == "HOLD_WORK" and support_still_critically_weak)
    ):
        trend = "IMPROVING"
    else:
        trend = "STABLE"

    true_what_changed = []

    if event_count_delta > 0:
        true_what_changed.append(f"{event_count_delta} new event(s) attached to this case")

    true_what_changed.append(f"Spatial shift: {spatial_shift}")
    true_what_changed.append(
        f"Timing support: {classify_support_band(safe_float(prior_temporal.get('timing_support_current'), 0.0))} -> {classify_support_band(safe_float(current_temporal.get('timing_support_current'), 0.0))}"
        if timing_shift != "unchanged"
        else "Timing support: unchanged"
    )
    if operational_shift != "none":
        true_what_changed.append(
            f"Operational shift: {safe_str(prior_operational.get('activity_type_current'), 'unknown')} -> {safe_str(current_operational.get('activity_type_current'), 'unknown')}"
        )
        true_what_changed.append(
            f"Equipment shift: {safe_str(prior_operational.get('equipment_class_current'), 'unknown')} -> {safe_str(current_operational.get('equipment_class_current'), 'unknown')}"
        )
    else:
        true_what_changed.append("Operational shift: none")
    true_what_changed.append(f"Uncertainty shift: {uncertainty_shift}")
    true_what_changed.append(
        f"Decision posture: {safe_str(prior_decision.get('posture_current'), 'unknown').lower()} -> {safe_str(current_decision.get('posture_current'), 'unknown').lower()}"
        if posture_shift != "same"
        else "Decision posture: unchanged"
    )

    if status_changed:
        true_what_changed.append(f"Case status changed from {prior_status or 'UNKNOWN'} to {current_status or 'UNKNOWN'}")

    if trend == "REACTIVATED":
        true_what_changed.append("Previously closed case appears active again")

    if not true_what_changed:
        true_what_changed.append("No significant change detected since the prior case state")

    return {
        "trend": trend,
        "decision_shift": "WORSENED" if decision_shift_score > 0 else "IMPROVED" if decision_shift_score < 0 else "UNCHANGED",
        "confidence_delta": round(confidence_delta, 4),
        "uncertainty_delta": round(uncertainty_delta, 4),
        "alignment_delta": round(alignment_delta, 4),
        "event_count_delta": event_count_delta,
        "status_changed": status_changed,
        "change_summary": change_summary,
        "state_dimensions": {
            "current": current_dimensions,
            "prior": prior_dimensions,
        },
        "hidden_risk": {
            "current": current_hidden,
            "prior": prior_hidden,
            "delta": hidden_risk_delta,
            "component_delta": hidden_component_delta,
        },
        "true_what_changed": true_what_changed,
    }


def compute_investigation_roi(
    case: CaseRecord,
    decision_state: DecisionState,
    uncertainty_burden: float,
    temporal_change: Dict[str, Any],
    behavior: BehavioralRiskAssessment,
) -> float:
    score = 0.0
    status = str(case.status or "").upper().strip()

    if decision_state == DecisionState.STOP_WORK:
        score += 3.0
    elif decision_state == DecisionState.HIGH_RISK_OF_MISJUDGMENT:
        score += 2.2
    elif decision_state == DecisionState.PROCEED_WITH_VERIFICATION:
        score += 1.2
    else:
        score += 0.5

    score += (clamp01(uncertainty_burden) or 0.0) * 2.0

    trend = temporal_change.get("trend", "STABLE")
    if trend == "WORSENING":
        score += 2.0
    elif trend == "NEW":
        score += 1.0
    elif trend == "REACTIVATED":
        score += 1.5
    elif trend == "IMPROVING":
        score -= 0.5

    if temporal_change.get("event_count_delta", 0) > 0:
        score += 0.8

    if behavior.repeated_activity:
        score += 0.4
    if behavior.conflicting_signals_ignored:
        score += 0.8

    if status == "CLOSED":
        score -= 2.0
    elif status == "INACTIVE":
        score -= 0.8

    return round(max(0.0, score), 4)
