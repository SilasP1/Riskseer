"""
case_audit.py

Backend audit helpers for validating temporal transitions and summary integrity.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from schemas import CaseRecord


ALLOWED_TRANSITION_RULES: List[Dict[str, Any]] = [
    {
        "name": "worsening_from_timing_or_posture",
        "if": "posture upgraded OR timing degraded materially OR support weakened materially OR operational consequence escalated",
        "then": "trend may be WORSENING",
    },
    {
        "name": "improving_from_support_or_posture",
        "if": "posture downgraded AND support improved materially",
        "then": "trend may be IMPROVING",
    },
    {
        "name": "stable_when_dimensions_stable",
        "if": "spatial unchanged AND timing unchanged AND operational none AND uncertainty stable AND posture same",
        "then": "trend should be STABLE",
    },
    {
        "name": "posture_upgrade_requires_driver",
        "if": "posture upgraded",
        "then": "at least one of timing degraded, operational escalated, uncertainty increased, or spatial shift should also be present",
    },
]


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def get_dimensions(case: CaseRecord) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    metadata = case.metadata or {}
    temporal_change = metadata.get("temporal_change") or {}
    state_dimensions = temporal_change.get("state_dimensions") or {}
    current_dims = state_dimensions.get("current") or {}
    prior_dims = state_dimensions.get("prior") or {}
    return temporal_change, current_dims, prior_dims


def get_ui_summary(case: CaseRecord) -> Dict[str, Any]:
    return (case.metadata or {}).get("ui_summary") or {}


def summarize_case_row(case: CaseRecord) -> Dict[str, Any]:
    temporal_change, current_dims, prior_dims = get_dimensions(case)
    change_summary = temporal_change.get("change_summary") or {}
    current_temporal = current_dims.get("temporal") or {}
    prior_temporal = prior_dims.get("temporal") or {}
    current_spatial = current_dims.get("spatial") or {}
    prior_spatial = prior_dims.get("spatial") or {}
    current_operational = current_dims.get("operational") or {}
    prior_operational = prior_dims.get("operational") or {}
    current_support = current_dims.get("support") or {}
    prior_support = prior_dims.get("support") or {}
    current_decision = current_dims.get("decision") or {}
    prior_decision = prior_dims.get("decision") or {}
    ui_summary = get_ui_summary(case)

    hidden_risk = (case.metadata or {}).get("hidden_risk") or {}
    hidden_current = hidden_risk.get("current") or {}
    hidden_prior = hidden_risk.get("prior") or {}
    hidden_components = hidden_current.get("components") or {}
    hidden_component_delta = hidden_risk.get("component_delta") or {}

    return {
        "case_id": case.case_id,
        "status": case.status,
        "trend": temporal_change.get("trend", (case.metadata or {}).get("trend", "UNKNOWN")),
        "posture_prior": safe_str(prior_decision.get("posture_current"), "unknown"),
        "posture_current": safe_str(current_decision.get("posture_current"), "unknown"),
        "urgency_prior": safe_str(prior_decision.get("urgency_current"), "unknown"),
        "urgency_current": safe_str(current_decision.get("urgency_current"), "unknown"),
        "timing_support_prior": round(safe_float(prior_temporal.get("timing_support_current"), 0.0), 4),
        "timing_support_current": round(safe_float(current_temporal.get("timing_support_current"), 0.0), 4),
        "area_support_prior": round(safe_float(prior_spatial.get("area_support_current"), 0.0), 4),
        "area_support_current": round(safe_float(current_spatial.get("area_support_current"), 0.0), 4),
        "support_strength_prior": round(safe_float(prior_support.get("support_strength_current"), 0.0), 4),
        "support_strength_current": round(safe_float(current_support.get("support_strength_current"), 0.0), 4),
        "confidence_prior": safe_str(prior_support.get("confidence_current"), "unknown"),
        "confidence_current": safe_str(current_support.get("confidence_current"), "unknown"),
        "asset_proximity_prior": safe_str(prior_spatial.get("asset_proximity_current"), "unknown"),
        "asset_proximity_current": safe_str(current_spatial.get("asset_proximity_current"), "unknown"),
        "activity_type_prior": safe_str(prior_operational.get("activity_type_current"), "unknown"),
        "activity_type_current": safe_str(current_operational.get("activity_type_current"), "unknown"),
        "equipment_class_prior": safe_str(prior_operational.get("equipment_class_current"), "unknown"),
        "equipment_class_current": safe_str(current_operational.get("equipment_class_current"), "unknown"),
        "spatial_shift": safe_str(change_summary.get("spatial_shift"), "unknown"),
        "timing_shift": safe_str(change_summary.get("timing_shift"), "unknown"),
        "operational_shift": safe_str(change_summary.get("operational_shift"), "unknown"),
        "uncertainty_shift": safe_str(change_summary.get("uncertainty_shift"), "unknown"),
        "posture_shift": safe_str(change_summary.get("posture_shift"), "unknown"),
        "reason": safe_str(ui_summary.get("reason")),
        "consequence": safe_str(ui_summary.get("consequence")),
        "action": safe_str(ui_summary.get("action")),
        "confidence_level": safe_str((ui_summary.get("confidence") or {}).get("level")),
        "confidence_basis": safe_str((ui_summary.get("confidence") or {}).get("basis")),
        "hidden_risk_band_current": safe_str(hidden_current.get("band"), "unknown"),
        "hidden_risk_band_prior": safe_str(hidden_prior.get("band"), "unknown"),
        "hidden_risk_prior": safe_float(hidden_prior.get("score"), 0.0),
        "hidden_risk_current": safe_float(hidden_current.get("score"), 0.0),
        "hidden_risk_delta": safe_float(hidden_risk.get("delta"), 0.0),
        "hidden_risk_component_delta": hidden_component_delta,
        "routine_appearance_current": safe_float(hidden_components.get("routine_appearance_score"), 0.0),
        "support_weakness_current": safe_float(hidden_components.get("support_weakness_score"), 0.0),
        "consequence_current": safe_float(hidden_components.get("consequence_if_waved_through_score"), 0.0),
        "intervention_gap_current": safe_float(hidden_components.get("intervention_gap_score"), 0.0),
    }


def audit_case(case: CaseRecord) -> Dict[str, Any]:
    row = summarize_case_row(case)
    flags: List[str] = []
    trend = row["trend"].upper()

    if trend == "NEW":
        return {
            "case_id": case.case_id,
            "trend": trend,
            "severity": "info",
            "flags": [],
            "row": row,
        }

    if (
        row["posture_shift"] == "upgraded"
        and row["uncertainty_shift"] == "decreased"
        and row["operational_shift"] == "deescalated"
        and row["timing_shift"] == "improved"
    ):
        flags.append("posture upgraded while support improved and operations deescalated")

    if (
        trend == "STABLE"
        and (row["timing_shift"] == "degraded" or row["operational_shift"] == "escalated" or row["uncertainty_shift"] == "increased")
    ):
        flags.append("trend is stable even though one or more worsening dimensions are present")

    if (
        row["spatial_shift"] == "none"
        and row["timing_shift"] == "unchanged"
        and row["operational_shift"] == "none"
        and row["uncertainty_shift"] == "stable"
        and row["posture_shift"] == "upgraded"
    ):
        flags.append("posture upgraded without any dimensional driver")

    if (
        row["confidence_current"] == "high"
        and row["support_strength_current"] < row["support_strength_prior"]
        and row["timing_shift"] == "degraded"
    ):
        flags.append("confidence increased or stayed high while support weakened")

    reason_lower = row["reason"].lower()

    if (
        ("timing support is only" in reason_lower or "timing is weak" in reason_lower or "timing does not" in reason_lower)
        and row["timing_support_current"] >= 0.8
    ):
        flags.append("reason claims timing is weak but current timing support is aligned")

    if (
        ("area support is only" in reason_lower or "area is weak" in reason_lower or "area does not" in reason_lower)
        and row["area_support_current"] >= 0.8
    ):
        flags.append("reason claims area is weak but current area support is aligned")

    action_lower = row["action"].lower()

    if "escalate" in action_lower and row["posture_current"] not in {"ESCALATE", "HOLD_WORK"}:
        flags.append("action says escalate but posture does not")

    if (
        (action_lower.startswith("stop") or action_lower.startswith("pause work"))
        and row["posture_current"] != "HOLD_WORK"
    ):
        flags.append("action says stop but posture is not hold_work")

    if "ticket signals conflict on timing" in row["confidence_basis"].lower() and row["timing_shift"] not in {"degraded", "unchanged"} and row["timing_support_current"] >= 0.8:
        flags.append("confidence basis claims timing conflict without timing weakness")

    if (
        row["posture_current"] == "MONITOR"
        and row["timing_support_current"] >= 0.8
        and row["area_support_current"] >= 0.8
        and row["confidence_level"] != "high"
    ):
        flags.append("monitor case has aligned support but backend confidence is not high")

    if (
        row["posture_current"] == "MONITOR"
        and row["timing_support_current"] >= 0.8
        and row["area_support_current"] >= 0.8
        and "weaker than it looks" in row["reason"].lower()
    ):
        flags.append("monitor case uses generic weak-support reason despite aligned support")

    if (
        abs(row["hidden_risk_delta"]) >= 15
        and row["spatial_shift"] == "none"
        and row["timing_shift"] == "unchanged"
        and row["operational_shift"] == "none"
        and row["uncertainty_shift"] == "stable"
        and row["posture_shift"] == "same"
    ):
        flags.append("hidden risk jumped sharply while all other state dimensions stayed stable")

    if (
        row["hidden_risk_delta"] < -10
        and (row["trend"] == "WORSENING" or row["posture_shift"] == "upgraded")
    ):
        flags.append("hidden risk dropped despite worsening posture or trend")

    if (
        row["posture_current"] == "HOLD_WORK"
        and row["hidden_risk_current"] >= 80
    ):
        flags.append("hidden risk remains very high on a case that is already obvious stop-work")

    if (
        row["hidden_risk_current"] <= 20
        and row["routine_appearance_current"] >= 50
        and row["support_weakness_current"] >= 45
        and row["consequence_current"] >= 35
    ):
        flags.append("hidden risk is too low for a routine-looking case with weak support and meaningful consequence")

    if (
        row["hidden_risk_current"] >= 70
        and row["posture_current"] == "MONITOR"
        and row["routine_appearance_current"] < 35
    ):
        flags.append("hidden risk is high even though the case does not look routine enough to be easily waved through")

    if (
        row["hidden_risk_delta"] > 10
        and row["routine_appearance_current"] < 30
        and row["posture_shift"] == "same"
        and row["timing_shift"] == "unchanged"
    ):
        flags.append("hidden risk rose sharply without stronger routine appearance or a decision-state change")

    severity = "error" if flags else "ok"
    return {
        "case_id": case.case_id,
        "trend": trend,
        "severity": severity,
        "flags": flags,
        "row": row,
    }


def sort_audit_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    trend_rank = {"WORSENING": 4, "REACTIVATED": 3, "IMPROVING": 2, "STABLE": 1, "NEW": 0}
    severity_rank = {"error": 2, "ok": 1, "info": 0}
    return sorted(
        records,
        key=lambda item: (
            item["trend"] != "NEW",
            severity_rank.get(item["severity"], 0),
            trend_rank.get(item["trend"], 0),
            item["row"].get("posture_shift") == "upgraded",
            item["case_id"],
        ),
        reverse=True,
    )


def build_audit_payload(cases: Sequence[CaseRecord]) -> Dict[str, Any]:
    records = [audit_case(case) for case in cases]
    sorted_records = sort_audit_records(records)
    flagged = [record for record in sorted_records if record["flags"]]
    return {
        "allowed_transition_rules": ALLOWED_TRANSITION_RULES,
        "case_count": len(sorted_records),
        "non_new_case_count": sum(1 for record in sorted_records if record["trend"] != "NEW"),
        "flagged_case_count": len(flagged),
        "flagged_case_ids": [record["case_id"] for record in flagged],
        "records": sorted_records,
    }


def build_audit_text(payload: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("RISKSEER CONTRADICTION AUDIT")
    lines.append("=" * 80)
    lines.append(f"Cases audited: {payload.get('case_count', 0)}")
    lines.append(f"Non-new cases: {payload.get('non_new_case_count', 0)}")
    lines.append(f"Flagged cases: {payload.get('flagged_case_count', 0)}")
    lines.append("")
    lines.append("Allowed transition rules:")
    for rule in payload.get("allowed_transition_rules", []):
        lines.append(f"- {rule.get('name')}: IF {rule.get('if')} THEN {rule.get('then')}")
    lines.append("")

    for record in payload.get("records", []):
        row = record["row"]
        lines.append(f"Case {record['case_id']} | trend={record['trend']} | severity={record['severity']}")
        lines.append(
            f"  posture {row['posture_prior']} -> {row['posture_current']} | "
            f"timing {row['timing_support_prior']} -> {row['timing_support_current']} | "
            f"area {row['area_support_prior']} -> {row['area_support_current']}"
        )
        lines.append(
            f"  operational {row['activity_type_prior']}/{row['equipment_class_prior']} -> "
            f"{row['activity_type_current']}/{row['equipment_class_current']}"
        )
        lines.append(
            f"  shifts spatial={row['spatial_shift']} timing={row['timing_shift']} "
            f"operational={row['operational_shift']} uncertainty={row['uncertainty_shift']} "
            f"posture={row['posture_shift']}"
        )
        lines.append(
            f"  ui reason='{row['reason']}' | confidence={row['confidence_level']} ({row['confidence_basis']})"
        )
        lines.append(
            f"  hidden risk {row['hidden_risk_prior']} -> {row['hidden_risk_current']} "
            f"(delta {row['hidden_risk_delta']}, band {row['hidden_risk_band_current']}) | "
            f"routine={row['routine_appearance_current']} support_weakness={row['support_weakness_current']} "
            f"consequence={row['consequence_current']} intervention_gap={row['intervention_gap_current']}"
        )
        if record["flags"]:
            for flag in record["flags"]:
                lines.append(f"  FLAG: {flag}")
        lines.append("")
    return "\n".join(lines)
