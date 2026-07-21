"""
explanations.py

GOAL
----
This file converts structured case evaluations into readable explanations.

It exists to separate:
- evaluation logic (case_logic.py)
from
- human-readable output (this file)

WHAT explanations.py DOES
-------------------------
1. Formats CaseRecord / CaseEvaluation data into readable summaries.
2. Renders evidence layers clearly:
   - observed
   - derived
   - inferred
   - assumed
3. Produces:
   - short operator summaries
   - full operator explanations
   - internal analyst explanations
   - compact table/report rows
4. Preserves uncertainty instead of hiding it.

WHAT explanations.py MUST NOT DO
--------------------------------
1. It must not evaluate cases.
2. It must not assign decision_state, urgency, or response_posture.
3. It must not change scores, logic, or failure layers.
4. It must not invent evidence not present in the case evaluation.
5. It must not blur the distinction between observed, derived, inferred, and assumed.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence

from schemas import (
    CaseEvaluation,
    CaseRecord,
    DecisionState,
    EvidenceItem,
    EvidenceLayers,
    FailureLayer,
    Observation,
    ResponsePosture,
    UrgencyLevel,
)


# ============================================================
# SMALL HELPERS
# ============================================================

def _fmt_pct(value: Optional[float]) -> str:
    if value is None:
        return "unknown"
    return f"{round(value * 100)}%"


def _fmt_list(items: Sequence[str], bullet: str = "- ") -> str:
    if not items:
        return ""
    return "\n".join(f"{bullet}{item}" for item in items)


def _join_nonempty(parts: Sequence[str], sep: str = "\n") -> str:
    return sep.join(part for part in parts if part and part.strip())


def _title(text: str) -> str:
    return text.replace("_", " ").title()


def _enum_value(value) -> str:
    return getattr(value, "value", str(value))


def _section(title: str, body: str) -> str:
    if not body.strip():
        return ""
    return f"{title}\n{body}"


def _dedupe_preserve(items: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            out.append(item)
            seen.add(item)
    return out


def _authorization_clarity_label(evaluation: CaseEvaluation) -> str:
    why_now = evaluation.why_now or []
    alignment = evaluation.alignment
    mixed_signals = any(
        "conflict" in item.lower()
        or "unresolved" in item.lower()
        or "ambigu" in item.lower()
        or "no plausible matching ticket" in item.lower()
        for item in why_now
    )
    partial_alignment = (
        (alignment.spatial_alignment or 0.0) < 0.65
        or (alignment.temporal_alignment or 0.0) < 0.65
    )

    if mixed_signals or partial_alignment:
        return "LOW"
    if (alignment.ticket_match_strength or 0.0) < 0.8:
        return "MEDIUM"
    return "HIGH"


# ============================================================
# EVIDENCE RENDERING
# ============================================================

def format_evidence_item(item: EvidenceItem, include_confidence: bool = False) -> str:
    text = item.statement
    if include_confidence and item.confidence is not None:
        text += f" (confidence: {_fmt_pct(item.confidence)})"
    return text


def format_evidence_block(
    items: Sequence[EvidenceItem],
    heading: str,
    include_confidence: bool = False,
) -> str:
    if not items:
        return f"{heading}\n- None"

    lines = [format_evidence_item(item, include_confidence=include_confidence) for item in items]
    return f"{heading}\n{_fmt_list(lines)}"


def format_evidence_layers(
    layers: EvidenceLayers,
    include_confidence: bool = False,
) -> str:
    parts = [
        format_evidence_block(layers.observed, "Observed facts", include_confidence=include_confidence),
        format_evidence_block(layers.derived, "Derived facts", include_confidence=include_confidence),
        format_evidence_block(layers.inferred, "Inferences", include_confidence=include_confidence),
        format_evidence_block(layers.assumed, "Assumptions", include_confidence=include_confidence),
    ]
    return _join_nonempty(parts, sep="\n\n")


# ============================================================
# ASSESSMENT RENDERING
# ============================================================

def format_alignment_summary(evaluation: CaseEvaluation) -> str:
    alignment = evaluation.alignment

    lines = [
        f"Summary: {alignment.summary}",
        f"Spatial alignment: {_fmt_pct(alignment.spatial_alignment)}",
        f"Temporal alignment: {_fmt_pct(alignment.temporal_alignment)}",
        f"Ticket match strength: {_fmt_pct(alignment.ticket_match_strength)}",
        f"Asset relevance: {_fmt_pct(alignment.asset_relevance)}",
    ]

    if alignment.concerns:
        lines.append("Concerns:")
        lines.extend(f"- {item}" for item in alignment.concerns)

    return "\n".join(lines)


def format_information_integrity_summary(evaluation: CaseEvaluation) -> str:
    info = evaluation.information_integrity

    lines = [
        f"Summary: {info.summary}",
        f"Overall confidence: {_fmt_pct(info.overall_confidence)}",
        f"Ticket quality confidence: {_fmt_pct(info.ticket_quality.confidence)}",
        f"Asset quality confidence: {_fmt_pct(info.asset_quality.confidence)}",
        f"Event quality confidence: {_fmt_pct(info.event_quality.confidence)}",
    ]

    if info.concerns:
        lines.append("Concerns:")
        lines.extend(f"- {item}" for item in info.concerns)

    return "\n".join(lines)


def format_behavioral_risk_summary(evaluation: CaseEvaluation) -> str:
    behavior = evaluation.behavioral_risk

    lines = [
        f"Summary: {behavior.summary}",
        f"Habit risk: {_fmt_pct(behavior.habit_risk)}",
        f"Repeated activity: {'yes' if behavior.repeated_activity else 'no'}",
        f"Escalating activity: {'yes' if behavior.escalating_activity else 'no'}",
        f"Conflicting signals ignored: {'yes' if behavior.conflicting_signals_ignored else 'no'}",
    ]

    if behavior.concerns:
        lines.append("Concerns:")
        lines.extend(f"- {item}" for item in behavior.concerns)

    return "\n".join(lines)


def format_failure_layers(evaluation: CaseEvaluation) -> str:
    if not evaluation.failure_layers:
        return "Failure layers\n- None identified"

    lines = [_title(_enum_value(layer)) for layer in evaluation.failure_layers]
    return f"Failure layers\n{_fmt_list(lines)}"


def format_responsibility_integrity_summary(
    evaluation: CaseEvaluation,
    *,
    internal: bool = False,
) -> str:
    rim = evaluation.responsibility_integrity
    if rim is None or not rim.layers:
        return "Responsibility integrity\n- Not evaluated"

    dsi = rim.decision_support_integrity
    lines = [
        f"Decision support: {_title(_enum_value(dsi.state))}",
        f"Decision risk: {_title(_enum_value(dsi.decision_risk))}",
        f"Recommended posture: {_title(_enum_value(dsi.recommended_posture))}",
        f"Reason: {dsi.reason}",
    ]

    lines.append("Layers:")
    for name, layer in rim.layers.items():
        lines.append(f"- {_title(name)}: {_title(_enum_value(layer.state))} - {layer.reason}")
        if internal:
            for fact in (layer.observed_facts or [])[:3]:
                lines.append(f"  observed: {fact}")
            for fact in (layer.derived_facts or [])[:3]:
                lines.append(f"  derived: {fact}")
            for fact in (layer.missing_facts or [])[:3]:
                lines.append(f"  missing: {fact}")

    if internal and rim.failure_propagation:
        lines.append("Failure propagation:")
        lines.extend(f"- {item}" for item in rim.failure_propagation)

    return "Responsibility integrity\n" + "\n".join(lines)


def format_decision_defensibility_summary(
    evaluation: CaseEvaluation,
    *,
    internal: bool = False,
) -> str:
    defensibility = getattr(evaluation, "decision_defensibility", None)
    if defensibility is None:
        return "Decision defensibility\n- Not evaluated"

    lines = [
        f"State: {_title(_enum_value(defensibility.state))}",
        f"Decision risk: {_title(_enum_value(defensibility.decision_risk))}",
        f"Defensible decision: {_title(_enum_value(getattr(defensibility, 'defensible_decision', '')))}",
        f"Reason: {defensibility.reason}",
    ]

    weaknesses = list(getattr(defensibility, "key_weaknesses", []) or [])
    if weaknesses:
        lines.append("Key weaknesses:")
        lines.extend(f"- {item}" for item in weaknesses[:5])

    components = dict(getattr(defensibility, "components", {}) or {})
    if internal and components:
        lines.append("Components:")
        for key, value in components.items():
            lines.append(f"- {_title(key)}: {value}")

    return "Decision defensibility\n" + "\n".join(lines)


# ============================================================
# TOP-LEVEL EXPLANATIONS
# ============================================================

def build_short_operator_summary(case: CaseRecord) -> str:
    evaluation = case.evaluation
    if evaluation is None:
        return f"Case {case.case_id}: no evaluation available."

    return (
        f"Case {case.case_id}: "
        f"{evaluation.operator_summary} "
        f"[state={_enum_value(evaluation.decision_state)}, "
        f"urgency={_enum_value(evaluation.urgency)}, "
        f"posture={_enum_value(evaluation.response_posture)}]"
    )


def build_operator_explanation(case: CaseRecord) -> str:
    evaluation = case.evaluation
    if evaluation is None:
        return f"Case {case.case_id}\nNo evaluation available."

    overview = _join_nonempty([
        f"Case {case.case_id}",
        f"Decision state: {_enum_value(evaluation.decision_state)}",
        f"Urgency: {_enum_value(evaluation.urgency)}",
        f"Recommended posture: {_enum_value(evaluation.response_posture)}",
        f"Data confidence: {_fmt_pct(evaluation.confidence)}",
        f"Authorization clarity: {_authorization_clarity_label(evaluation)}",
        f"Summary: {evaluation.operator_summary}",
    ])

    why_now = "Why this matters now\n" + (
        _fmt_list(evaluation.why_now) if evaluation.why_now else "- No immediate trigger stated"
    )

    actions = "Recommended actions\n" + (
        _fmt_list(evaluation.recommended_actions) if evaluation.recommended_actions else "- No action provided"
    )

    evidence = format_evidence_layers(evaluation.evidence_layers, include_confidence=False)

    return _join_nonempty([
        overview,
        format_decision_defensibility_summary(evaluation),
        format_responsibility_integrity_summary(evaluation),
        why_now,
        actions,
        evidence,
    ], sep="\n\n")


def build_internal_explanation(case: CaseRecord) -> str:
    evaluation = case.evaluation
    if evaluation is None:
        return f"Case {case.case_id}\nNo evaluation available."

    header = _join_nonempty([
        f"Case {case.case_id}",
        f"Internal summary: {evaluation.internal_summary}",
        f"Decision state: {_enum_value(evaluation.decision_state)}",
        f"Urgency: {_enum_value(evaluation.urgency)}",
        f"Response posture: {_enum_value(evaluation.response_posture)}",
        f"Data confidence: {_fmt_pct(evaluation.confidence)}",
        f"Authorization clarity: {_authorization_clarity_label(evaluation)}",
        f"Events: {len(case.event_ids)}",
        f"Tickets: {len(case.ticket_ids)}",
        f"Assets: {len(case.asset_ids)}",
    ])

    what_changed = "What changed\n" + (
        _fmt_list(evaluation.what_changed) if evaluation.what_changed else "- No explicit change markers"
    )

    sections = [
        header,
        format_failure_layers(evaluation),
        _section("Alignment assessment", format_alignment_summary(evaluation)),
        _section("Information integrity assessment", format_information_integrity_summary(evaluation)),
        _section("Behavioral risk assessment", format_behavioral_risk_summary(evaluation)),
        format_responsibility_integrity_summary(evaluation, internal=True),
        format_decision_defensibility_summary(evaluation, internal=True),
        "Why now\n" + (_fmt_list(evaluation.why_now) if evaluation.why_now else "- No immediate trigger stated"),
        what_changed,
        "Recommended actions\n" + (_fmt_list(evaluation.recommended_actions) if evaluation.recommended_actions else "- None"),
        format_evidence_layers(evaluation.evidence_layers, include_confidence=True),
    ]

    return _join_nonempty(sections, sep="\n\n")


# ============================================================
# REPORT / EXPORT SHAPES
# ============================================================

def build_case_report_row(case: CaseRecord) -> Dict[str, str]:
    evaluation = case.evaluation

    if evaluation is None:
        return {
            "case_id": case.case_id,
            "decision_state": "UNEVALUATED",
            "urgency": "UNEVALUATED",
            "response_posture": "UNEVALUATED",
            "confidence": "",
            "uncertainty_burden": "",
            "responsibility_integrity_state": "",
            "responsibility_decision_risk": "",
            "responsibility_reason": "",
            "decision_defensibility_state": "",
            "decision_defensibility_risk": "",
            "decision_defensibility_reason": "",
            "operator_summary": "No evaluation available",
            "failure_layers": "",
            "why_now": "",
            "recommended_actions": "",
            "event_count": str(len(case.event_ids)),
            "ticket_count": str(len(case.ticket_ids)),
            "asset_count": str(len(case.asset_ids)),
            "updated_at": case.updated_at,
        }

    return {
        "case_id": case.case_id,
        "decision_state": _enum_value(evaluation.decision_state),
        "urgency": _enum_value(evaluation.urgency),
        "response_posture": _enum_value(evaluation.response_posture),
        "confidence": _fmt_pct(evaluation.confidence),
        "uncertainty_burden": _fmt_pct(evaluation.uncertainty_burden),
        "responsibility_integrity_state": _enum_value(evaluation.responsibility_integrity.decision_support_integrity.state),
        "responsibility_decision_risk": _enum_value(evaluation.responsibility_integrity.decision_support_integrity.decision_risk),
        "responsibility_reason": evaluation.responsibility_integrity.decision_support_integrity.reason,
        "decision_defensibility_state": _enum_value(evaluation.decision_defensibility.state),
        "decision_defensibility_risk": _enum_value(evaluation.decision_defensibility.decision_risk),
        "decision_defensibility_reason": evaluation.decision_defensibility.reason,
        "operator_summary": evaluation.operator_summary,
        "failure_layers": "; ".join(_title(_enum_value(layer)) for layer in evaluation.failure_layers),
        "why_now": " | ".join(evaluation.why_now),
        "recommended_actions": " | ".join(evaluation.recommended_actions),
        "event_count": str(len(case.event_ids)),
        "ticket_count": str(len(case.ticket_ids)),
        "asset_count": str(len(case.asset_ids)),
        "updated_at": case.updated_at,
    }


def build_case_report_rows(cases: Sequence[CaseRecord]) -> List[Dict[str, str]]:
    return [build_case_report_row(case) for case in cases]


# ============================================================
# COMPACT DISPLAY HELPERS
# ============================================================

def build_case_headline(case: CaseRecord) -> str:
    evaluation = case.evaluation
    if evaluation is None:
        return f"{case.case_id} | UNEVALUATED"

    return (
        f"{case.case_id} | "
        f"{_enum_value(evaluation.decision_state)} | "
        f"{_enum_value(evaluation.urgency)} | "
        f"{_enum_value(evaluation.response_posture)}"
    )


def build_case_snapshot(case: CaseRecord) -> str:
    evaluation = case.evaluation
    if evaluation is None:
        return (
            f"{build_case_headline(case)}\n"
            f"Events={len(case.event_ids)} Tickets={len(case.ticket_ids)} Assets={len(case.asset_ids)}\n"
            f"No evaluation available."
        )

    lines = [
        build_case_headline(case),
        f"Events={len(case.event_ids)} Tickets={len(case.ticket_ids)} Assets={len(case.asset_ids)}",
        f"Confidence={_fmt_pct(evaluation.confidence)} Uncertainty={_fmt_pct(evaluation.uncertainty_burden)}",
        evaluation.operator_summary,
    ]

    if evaluation.why_now:
        lines.append("Why now: " + " | ".join(evaluation.why_now[:2]))

    return "\n".join(lines)


# ============================================================
# OPTIONAL SEARCH / FILTER PRESENTATION HELPERS
# ============================================================

def build_case_search_result(case: CaseRecord) -> Dict[str, str]:
    evaluation = case.evaluation

    return {
        "case_id": case.case_id,
        "headline": build_case_headline(case),
        "summary": (
            evaluation.operator_summary
            if evaluation is not None
            else "No evaluation available"
        ),
        "updated_at": case.updated_at,
    }
