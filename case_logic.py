"""
case_logic.py

GOAL
----
This file is the orchestration layer for case evaluation.

Riskseer is not a generic event severity engine.
Its goal is to identify when a field team or operator is at risk of making
the wrong decision under uncertainty before that decision turns into damage.

This file preserves the existing workflow while delegating work to:
- case_evaluation.py for current-state interpretation
- case_temporal.py for change-over-time interpretation

WHAT case_logic.py DOES
-----------------------
1. Orchestrates full case evaluation using the current-state and temporal layers.
2. Builds final evaluation outputs expected by the rest of the workflow.
3. Preserves the existing entry points:
   - evaluate_case
   - evaluate_cases
   - evaluate_registry_in_place
4. Stores snapshots and temporal metadata back onto the case.

WHAT case_logic.py MUST NOT DO
------------------------------
1. It must not group events into cases. case.py owns that.
2. It must not parse raw CSV inputs. main.py / normalization layers own that.
3. It must not duplicate the core current-state logic from case_evaluation.py.
4. It must not duplicate the core temporal logic from case_temporal.py.
5. It must not pretend uncertainty is resolved when it is not.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from case_evaluation import (
    add_unique_text,
    build_evidence_layers,
    evaluate_alignment,
    evaluate_behavioral_risk,
    evaluate_decision_defensibility,
    evaluate_information_integrity,
    evaluate_responsibility_integrity,
    compute_uncertainty_burden,
    determine_decision_state,
    determine_failure_layers,
    determine_response_posture,
    determine_urgency,
    has_obs,
    reconcile_decision_with_support,
)
from case_temporal import (
    build_hidden_risk_assessment,
    build_case_state_snapshot,
    build_temporal_change_summary,
    compute_investigation_roi,
    extract_prior_snapshot,
)
from schemas import (
    AlignmentAssessment,
    BehavioralRiskAssessment,
    CaseEvaluation,
    CaseRecord,
    DecisionState,
    InformationIntegrityAssessment,
    ObservationType,
    ResponsePosture,
    UrgencyLevel,
)


# ============================================================
# ORCHESTRATION-SIDE OUTPUT BUILDERS
# ============================================================

def normalize_lifecycle_status(case: CaseRecord) -> str:
    status = str(case.status or "").upper().strip()
    if status == "OPEN":
        return "ACTIVE"
    if status in {"ACTIVE", "INACTIVE", "CLOSED"}:
        return status
    return "ACTIVE"


def apply_lifecycle_actionability(
    case: CaseRecord,
    urgency: UrgencyLevel,
    response_posture: ResponsePosture,
) -> tuple[UrgencyLevel, ResponsePosture]:
    status = normalize_lifecycle_status(case)

    if status == "CLOSED":
        return (UrgencyLevel.LOW, ResponsePosture.MONITOR)

    if status == "INACTIVE":
        if response_posture in {ResponsePosture.HOLD_WORK, ResponsePosture.ESCALATE}:
            return (UrgencyLevel.MODERATE, ResponsePosture.VERIFY)
        if response_posture == ResponsePosture.VERIFY_BEFORE_PROCEEDING:
            return (UrgencyLevel.MODERATE, ResponsePosture.VERIFY)

    return (urgency, response_posture)


def apply_lifecycle_decision_state(
    case: CaseRecord,
    decision_state: DecisionState,
    response_posture: ResponsePosture,
) -> DecisionState:
    status = normalize_lifecycle_status(case)

    if status == "CLOSED":
        return DecisionState.SAFE_TO_PROCEED

    if status == "INACTIVE":
        if response_posture == ResponsePosture.VERIFY:
            return DecisionState.PROCEED_WITH_VERIFICATION
        if response_posture == ResponsePosture.MONITOR:
            return DecisionState.SAFE_TO_PROCEED

    return decision_state


def has_mixed_spatial_scope(case: CaseRecord) -> bool:
    return has_obs(case.observations, ObservationType.INSIDE_TICKET_AREA) and has_obs(
        case.observations, ObservationType.OUTSIDE_TICKET_AREA
    )


def has_mixed_temporal_scope(case: CaseRecord) -> bool:
    return has_obs(case.observations, ObservationType.INSIDE_TICKET_WINDOW) and has_obs(
        case.observations, ObservationType.OUTSIDE_TICKET_WINDOW
    )

def build_why_now(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    decision_state: DecisionState,
    temporal_change: Optional[Dict[str, Any]] = None,
) -> List[str]:
    why_now: List[str] = []
    lifecycle_status = normalize_lifecycle_status(case)

    if lifecycle_status == "INACTIVE":
        add_unique_text(why_now, [
            "This case is currently inactive, so treat it as a watchpoint unless activity resumes",
        ])

    if lifecycle_status == "CLOSED":
        add_unique_text(why_now, [
            "This case is currently closed, so it is not a live interruption unless new activity reopens it",
        ])
        return why_now

    if lifecycle_status == "ACTIVE" and decision_state == DecisionState.STOP_WORK:
        add_unique_text(why_now, [
            "The current basis for proceeding is too weak to justify continued work without intervention",
        ])

    if has_obs(case.observations, ObservationType.NO_MATCHING_TICKET):
        add_unique_text(why_now, [
            "Activity is occurring without a plausible matching ticket in context",
        ])

    if has_mixed_spatial_scope(case):
        add_unique_text(why_now, [
            "Authorization context conflicts across overlapping ticket areas",
        ])
    elif has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA):
        add_unique_text(why_now, [
            "Available ticket context does not support confidence that current work stays within the intended area",
        ])

    if has_mixed_temporal_scope(case):
        add_unique_text(why_now, [
            "Ticket time coverage conflicts across candidate tickets",
        ])
    elif has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW):
        add_unique_text(why_now, [
            "Available ticket timing does not support confidence that current work stays within the intended window",
        ])

    scope_conflict = (
        has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
        or has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
        or has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
        or has_mixed_spatial_scope(case)
        or has_mixed_temporal_scope(case)
    )

    if behavior.repeated_activity and scope_conflict:
        add_unique_text(why_now, [
            "Work is continuing while authorization remains unresolved",
        ])

    if behavior.escalating_activity:
        add_unique_text(why_now, [
            "The observed activity pattern is intensifying",
        ])

    if (information.overall_confidence or 0.0) < 0.55:
        add_unique_text(why_now, [
            "What the crew would rely on here is weaker or messier than it looks",
        ])

    if has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR) and scope_conflict:
        add_unique_text(why_now, [
            "Reduced-visibility work methods may leave less time to catch bad assumptions",
        ])

    if has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR) and scope_conflict:
        add_unique_text(why_now, [
            "Mechanized work raises the consequence of continuing under weak assumptions",
        ])

    if temporal_change:
        if temporal_change.get("trend") == "WORSENING":
            add_unique_text(why_now, [
                "This case is worsening relative to its prior state",
            ])
        if temporal_change.get("trend") == "REACTIVATED":
            add_unique_text(why_now, [
                "This case appears active again after previously being closed",
            ])
        if temporal_change.get("event_count_delta", 0) > 0:
            add_unique_text(why_now, [
                "New activity has been added to an already active case",
            ])

    if not why_now:
        if len(case.ticket_ids) > 0 and len(case.asset_ids) > 0:
            why_now.append("Activity remains near a mapped asset, but ticket support still lines up")
        elif len(case.ticket_ids) > 0:
            why_now.append("Ticket support remains in place and no conflicting signals are showing")
        elif len(case.asset_ids) > 0:
            why_now.append("Activity is near a mapped asset, but no new contradiction is present")
        elif temporal_change and temporal_change.get("trend") == "IMPROVING":
            why_now.append("Recent changes are making the current picture easier to trust")
        else:
            why_now.append("No recent changes are weakening decision confidence")

    return why_now


def build_what_changed(
    case: CaseRecord,
    behavior: BehavioralRiskAssessment,
    temporal_change: Optional[Dict[str, Any]] = None,
) -> List[str]:
    if temporal_change and temporal_change.get("true_what_changed"):
        return list(temporal_change["true_what_changed"])

    changed: List[str] = []

    if behavior.repeated_activity:
        changed.append("More than one nearby activity signal is now part of this case")

    if behavior.escalating_activity:
        changed.append("Activity intensity increased relative to prior nearby observations")

    if has_obs(case.observations, ObservationType.MULTIPLE_POSSIBLE_TICKETS):
        changed.append("Ticket ambiguity increased")

    if has_obs(case.observations, ObservationType.DATA_GAP):
        changed.append("Missing or incomplete context is now affecting evaluation confidence")

    if has_mixed_spatial_scope(case):
        changed.append("Authorization boundaries now conflict across candidate tickets")
    elif has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA):
        changed.append("Spatial scope conflict is present in current case evidence")

    if has_mixed_temporal_scope(case):
        changed.append("Temporal coverage now conflicts across candidate tickets")
    elif has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW):
        changed.append("Time scope conflict is present in current case evidence")

    if not changed:
        changed.append("No significant change detected")

    return changed


def build_ui_summary(
    case: CaseRecord,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    response_posture: ResponsePosture,
    recommended_actions: Sequence[str],
) -> Dict[str, Any]:
    def support_reason(prefix: str, value: float) -> str:
        if value <= 0.15:
            strength = "No"
        elif value < 0.5:
            strength = "Weak"
        elif value < 0.8:
            strength = "Partial"
        else:
            strength = "Strong"
        return f"{strength} {prefix.lower()} for this activity."

    no_ticket = has_obs(case.observations, ObservationType.NO_MATCHING_TICKET)
    mixed_spatial = has_mixed_spatial_scope(case)
    mixed_temporal = has_mixed_temporal_scope(case)
    outside_area = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_AREA)
    outside_window = has_obs(case.observations, ObservationType.OUTSIDE_TICKET_WINDOW)
    heavy = has_obs(case.observations, ObservationType.HEAVY_EQUIPMENT_INDICATOR)
    trenchless = has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR)
    near_asset = has_obs(case.observations, ObservationType.NEAR_ASSET)
    info_conf = information.overall_confidence or 0.0
    spatial = alignment.spatial_alignment or 0.0
    temporal = alignment.temporal_alignment or 0.0
    support_aligned = spatial >= 0.8 and temporal >= 0.8 and info_conf >= 0.7

    if no_ticket:
        reason = "No active ticket covers this location and time."
        confidence_basis = "no active ticket covers this location and time"
        confidence_level = "high"
    elif mixed_temporal or outside_window:
        reason = support_reason("timing support", temporal)
        confidence_basis = "ticket signals conflict on timing"
        confidence_level = "medium"
    elif mixed_spatial or outside_area:
        reason = support_reason("area support", spatial)
        confidence_basis = "ticket signals conflict on area"
        confidence_level = "medium"
    elif response_posture == ResponsePosture.MONITOR and support_aligned:
        reason = "Ticket timing and area still line up with current activity."
        confidence_basis = "timing, area, and support are all aligned"
        confidence_level = "high"
    else:
        reason = "Current support is weaker than it looks."
        confidence_basis = "available support is incomplete"
        confidence_level = "low" if info_conf < 0.55 else "medium"

    if heavy and near_asset:
        consequence = "Crew is operating without confirmed support near mapped assets."
    elif trenchless:
        consequence = "Reduced-visibility work can go wrong before anyone gets a second chance."
    elif near_asset:
        consequence = (
            "Nearby mapped assets would raise the downside if support weakens."
            if response_posture == ResponsePosture.MONITOR and support_aligned
            else "Crew could strike a mapped asset before anything obvious looks wrong."
        )
    else:
        consequence = (
            "Nothing here justifies an interruption right now, but changes in timing or scope would matter quickly."
            if response_posture == ResponsePosture.MONITOR and support_aligned
            else "The crew could keep moving on support that does not hold up."
        )

    action = recommended_actions[0] if recommended_actions else "Verify before continuing."

    return {
        "reason": reason,
        "consequence": consequence,
        "action": action,
        "confidence": {
            "level": confidence_level,
            "basis": confidence_basis,
        },
    }


def build_recommended_actions(
    case: CaseRecord,
    decision_state: DecisionState,
    response_posture: ResponsePosture,
    information: InformationIntegrityAssessment,
    temporal_change: Optional[Dict[str, Any]] = None,
) -> List[str]:
    actions: List[str] = []
    lifecycle_status = normalize_lifecycle_status(case)

    if lifecycle_status == "CLOSED":
        actions.extend([
            "Keep this case as historical evidence, but do not treat it as a live stop/verify interruption",
            "Reopen and reassess immediately if new field activity appears in the same context",
        ])
        return actions

    if lifecycle_status == "INACTIVE":
        actions.append("Monitor for resumed field activity before escalating this as a live operator interruption")

    if response_posture == ResponsePosture.HOLD_WORK:
        actions.extend([
            "Pause work until scope, authorization, and field conditions are re-verified",
            "Confirm whether a valid ticket exists for the observed activity area and time",
            "Reconcile field activity against known asset location and current context before resuming",
        ])
    elif response_posture == ResponsePosture.ESCALATE:
        actions.extend([
            "Escalate for active human review before relying on current assumptions",
            "Verify that field activity matches ticket scope, timing, and intended work area",
            "Check whether the current basis for proceeding is strong enough to trust",
        ])
    elif response_posture == ResponsePosture.VERIFY_BEFORE_PROCEEDING:
        actions.extend([
            "Verify scope and time alignment before treating the case as operationally safe",
            "Confirm that ticket context is sufficient and not creating false confidence",
        ])
    elif response_posture == ResponsePosture.VERIFY:
        actions.extend([
            "Perform targeted verification on the main uncertainty in this case",
        ])
    else:
        actions.extend([
            "Continue monitoring for changes in scope, repetition, or conflicting signals",
        ])

    if (information.overall_confidence or 0.0) < 0.55:
        actions.append("Do not treat procedural appearance as enough support for continuing work")

    if has_obs(case.observations, ObservationType.TRENCHLESS_INDICATOR):
        actions.append("Apply extra scrutiny to bore path assumptions and reduced-visibility work conditions")

    if temporal_change and temporal_change.get("trend") == "WORSENING":
        actions.append("Prioritize investigation because this case is degrading over time")

    if temporal_change and temporal_change.get("trend") == "REACTIVATED":
        actions.append("Treat this as a reopened operational situation and verify why activity resumed")

    deduped: List[str] = []
    seen = set()
    for action in actions:
        if action not in seen:
            deduped.append(action)
            seen.add(action)

    return deduped


def build_internal_summary(
    case: CaseRecord,
    decision_state: DecisionState,
    alignment: AlignmentAssessment,
    information: InformationIntegrityAssessment,
    behavior: BehavioralRiskAssessment,
    temporal_change: Optional[Dict[str, Any]] = None,
) -> str:
    parts: List[str] = []

    parts.append(f"Case {case.case_id} evaluated as {decision_state.value}.")
    parts.append(alignment.summary + ".")
    parts.append(information.summary + ".")
    parts.append(behavior.summary + ".")

    if temporal_change:
        trend = temporal_change.get("trend")
        if trend == "WORSENING":
            parts.append("Case trend is worsening relative to the prior saved state.")
        elif trend == "IMPROVING":
            parts.append("Case trend is improving relative to the prior saved state.")
        elif trend == "REACTIVATED":
            parts.append("Case appears reactivated relative to the prior saved state.")
        elif trend == "NEW":
            parts.append("This is a newly created case with no prior saved state.")

    return " ".join(parts)


def build_operator_summary(
    case: CaseRecord,
    decision_state: DecisionState,
    response_posture: ResponsePosture,
    urgency: UrgencyLevel,
    temporal_change: Optional[Dict[str, Any]] = None,
) -> str:
    lifecycle_status = normalize_lifecycle_status(case)

    if lifecycle_status == "CLOSED":
        base = "Case is closed. Preserve the contradiction history, but do not treat this as a live operator interruption."
    elif lifecycle_status == "INACTIVE":
        if response_posture == ResponsePosture.VERIFY:
            base = "Case is inactive. Do not interrupt now, but verify quickly if activity resumes."
        else:
            base = "Case is inactive. Keep it visible, but do not interrupt unless activity resumes."
    elif decision_state == DecisionState.STOP_WORK:
        base = "Stop work. Proceeding now would rely on assumptions the system cannot support strongly enough."
    elif decision_state == DecisionState.HIGH_RISK_OF_MISJUDGMENT:
        base = "High decision risk. Escalate before relying on the current basis for scope or context."
    elif decision_state == DecisionState.PROCEED_WITH_VERIFICATION:
        base = "Pause and verify. This may still be fine, but not enough lines up to keep moving without a check."
    elif decision_state == DecisionState.SAFE_TO_PROCEED:
        base = "Nothing here is strong enough to justify slowing the crew right now, but keep it in view."
    else:
        base = f"{response_posture.value} - {urgency.value}"

    if temporal_change:
        trend = temporal_change.get("trend")
        if trend == "WORSENING":
            return base + " The case is getting worse."
        if trend == "IMPROVING":
            return base + " The case is improving."
        if trend == "REACTIVATED":
            return base + " The case appears active again."
        if trend == "NEW":
            return base + " This is a new case."

    return base


# ============================================================
# PRIMARY EVALUATION ENTRY POINT
# ============================================================

def evaluate_case(case: CaseRecord, prior_case_data: Optional[Dict[str, Any]] = None) -> CaseEvaluation:
    evidence_layers = build_evidence_layers(case)

    alignment = evaluate_alignment(case)
    information = evaluate_information_integrity(case)
    behavior = evaluate_behavioral_risk(case)

    uncertainty_burden = compute_uncertainty_burden(
        alignment=alignment,
        information=information,
        behavior=behavior,
        case=case,
    )

    decision_state = determine_decision_state(
        case=case,
        alignment=alignment,
        information=information,
        behavior=behavior,
        uncertainty_burden=uncertainty_burden,
    )

    urgency = determine_urgency(
        case=case,
        decision_state=decision_state,
        behavior=behavior,
        uncertainty_burden=uncertainty_burden,
    )

    response_posture = determine_response_posture(
        decision_state=decision_state,
        urgency=urgency,
    )

    responsibility_integrity = evaluate_responsibility_integrity(
        case=case,
        response_posture=response_posture,
        uncertainty_burden=uncertainty_burden,
    )
    preliminary_defensibility = evaluate_decision_defensibility(
        case=case,
        evidence_layers=evidence_layers,
        responsibility_integrity=responsibility_integrity,
        alignment=alignment,
        information=information,
        behavior=behavior,
        response_posture=response_posture,
    )
    decision_state, urgency, response_posture = reconcile_decision_with_support(
        decision_state=decision_state,
        urgency=urgency,
        response_posture=response_posture,
        decision_support=responsibility_integrity.decision_support_integrity,
        defensibility=preliminary_defensibility,
    )
    urgency, response_posture = apply_lifecycle_actionability(case, urgency, response_posture)
    decision_state = apply_lifecycle_decision_state(case, decision_state, response_posture)

    failure_layers = determine_failure_layers(
        case=case,
        alignment=alignment,
        information=information,
        behavior=behavior,
    )

    confidence = information.overall_confidence
    hidden_risk = build_hidden_risk_assessment(
        case=case,
        alignment=alignment,
        information=information,
        behavior=behavior,
        response_posture=response_posture,
    )
    current_snapshot = build_case_state_snapshot(
        case=case,
        alignment=alignment,
        information=information,
        behavior=behavior,
        decision_state=decision_state,
        urgency=urgency,
        response_posture=response_posture,
        uncertainty_burden=uncertainty_burden,
        confidence=confidence,
        hidden_risk=hidden_risk,
    )

    prior_snapshot = extract_prior_snapshot(prior_case_data)
    temporal_change = build_temporal_change_summary(
        current_snapshot=current_snapshot,
        prior_snapshot=prior_snapshot,
        case=case,
    )

    investigation_roi = compute_investigation_roi(
        case=case,
        decision_state=decision_state,
        uncertainty_burden=uncertainty_burden,
        temporal_change=temporal_change,
        behavior=behavior,
    )

    why_now = build_why_now(
        case=case,
        alignment=alignment,
        information=information,
        behavior=behavior,
        decision_state=decision_state,
        temporal_change=temporal_change,
    )

    what_changed = build_what_changed(
        case=case,
        behavior=behavior,
        temporal_change=temporal_change,
    )

    recommended_actions = build_recommended_actions(
        case=case,
        decision_state=decision_state,
        response_posture=response_posture,
        information=information,
        temporal_change=temporal_change,
    )

    dsi = responsibility_integrity.decision_support_integrity
    if getattr(dsi.state, "value", dsi.state) in {"DEGRADED", "CONFLICTED"}:
        add_unique_text(why_now, [dsi.reason])
        add_unique_text(recommended_actions, [
            "Verify responsibility-chain support before treating the next decision as well supported",
        ])

    decision_defensibility = evaluate_decision_defensibility(
        case=case,
        evidence_layers=evidence_layers,
        responsibility_integrity=responsibility_integrity,
        alignment=alignment,
        information=information,
        behavior=behavior,
        temporal_change=temporal_change,
        response_posture=response_posture,
    )

    reconciled = reconcile_decision_with_support(
        decision_state=decision_state,
        urgency=urgency,
        response_posture=response_posture,
        decision_support=dsi,
        defensibility=decision_defensibility,
    )
    reconciled_urgency, reconciled_posture = apply_lifecycle_actionability(
        case,
        reconciled[1],
        reconciled[2],
    )
    reconciled_state = apply_lifecycle_decision_state(case, reconciled[0], reconciled_posture)
    if (reconciled_state, reconciled_urgency, reconciled_posture) != (
        decision_state,
        urgency,
        response_posture,
    ):
        decision_state, urgency, response_posture = (
            reconciled_state,
            reconciled_urgency,
            reconciled_posture,
        )
        hidden_risk = build_hidden_risk_assessment(
            case=case,
            alignment=alignment,
            information=information,
            behavior=behavior,
            response_posture=response_posture,
        )
        current_snapshot = build_case_state_snapshot(
            case=case,
            alignment=alignment,
            information=information,
            behavior=behavior,
            decision_state=decision_state,
            urgency=urgency,
            response_posture=response_posture,
            uncertainty_burden=uncertainty_burden,
            confidence=confidence,
            hidden_risk=hidden_risk,
        )
        temporal_change = build_temporal_change_summary(
            current_snapshot=current_snapshot,
            prior_snapshot=prior_snapshot,
            case=case,
        )
        decision_defensibility = evaluate_decision_defensibility(
            case=case,
            evidence_layers=evidence_layers,
            responsibility_integrity=responsibility_integrity,
            alignment=alignment,
            information=information,
            behavior=behavior,
            temporal_change=temporal_change,
            response_posture=response_posture,
        )
    if getattr(decision_defensibility.state, "value", decision_defensibility.state) == "LOW":
        add_unique_text(why_now, [decision_defensibility.reason])
        add_unique_text(recommended_actions, [
            "Document verification steps before relying on this decision under review",
        ])

    ui_summary = build_ui_summary(
        case=case,
        alignment=alignment,
        information=information,
        response_posture=response_posture,
        recommended_actions=recommended_actions,
    )

    operator_summary = build_operator_summary(
        case=case,
        decision_state=decision_state,
        response_posture=response_posture,
        urgency=urgency,
        temporal_change=temporal_change,
    )

    internal_summary = build_internal_summary(
        case=case,
        decision_state=decision_state,
        alignment=alignment,
        information=information,
        behavior=behavior,
        temporal_change=temporal_change,
    )

    case.metadata["state_snapshot"] = current_snapshot
    case.metadata["prior_state_snapshot"] = prior_snapshot
    case.metadata["temporal_change"] = temporal_change
    case.metadata["trend"] = temporal_change.get("trend", "STABLE")
    case.metadata["investigation_roi"] = investigation_roi
    case.metadata["ui_summary"] = ui_summary
    case.metadata["hidden_risk"] = temporal_change.get("hidden_risk") or {
        "current": hidden_risk,
        "prior": None,
        "delta": 0.0,
    }
    case.metadata["responsibility_integrity"] = responsibility_integrity
    case.metadata["decision_defensibility"] = decision_defensibility
    case.responsibility_integrity = responsibility_integrity
    case.decision_defensibility = decision_defensibility

    return CaseEvaluation(
        decision_state=decision_state,
        urgency=urgency,
        response_posture=response_posture,
        confidence=confidence,
        uncertainty_burden=uncertainty_burden,
        alignment=alignment,
        information_integrity=information,
        behavioral_risk=behavior,
        responsibility_integrity=responsibility_integrity,
        decision_defensibility=decision_defensibility,
        evidence_layers=evidence_layers,
        failure_layers=failure_layers,
        why_now=why_now,
        what_changed=what_changed,
        recommended_actions=recommended_actions,
        operator_summary=operator_summary,
        internal_summary=internal_summary,
    )


def evaluate_cases(
    cases: Sequence[CaseRecord],
    prior_case_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> List[CaseRecord]:
    evaluated: List[CaseRecord] = []
    prior_case_index = prior_case_index or {}

    for case in cases:
        prior_case_data = prior_case_index.get(case.case_id)
        case.evaluation = evaluate_case(case, prior_case_data=prior_case_data)
        evaluated.append(case)

    return evaluated


def evaluate_registry_in_place(
    registry,
    prior_case_index: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    prior_case_index = prior_case_index or {}
    for case in registry.cases:
        prior_case_data = prior_case_index.get(case.case_id)
        case.evaluation = evaluate_case(case, prior_case_data=prior_case_data)
