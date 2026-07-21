"""
lookup_case.py

GOAL
----
This file provides a read-only inspection interface for Riskseer case outputs.

It is meant to help a human inspect:
- what cases exist
- which cases deserve investigation first
- how cases are trending
- what changed over time
- why a case was evaluated the way it was
- what evidence layers support it
- what action posture is recommended

WHAT lookup_case.py DOES
------------------------
1. Loads existing Riskseer output artifacts.
2. Displays case lists, rankings, and detailed case views.
3. Supports basic search/filter workflows across saved case outputs.
4. Surfaces:
   - decision state
   - urgency
   - response posture
   - trend
   - investigation ROI
   - evidence layers
   - failure layers
   - why_now
   - what_changed
   - recommended actions

WHAT lookup_case.py MUST NOT DO
-------------------------------
1. It must not re-evaluate cases.
2. It must not score or rank using new business logic.
3. It must not group events into cases.
4. It must not mutate saved output files.
5. It must not invent explanations beyond what was already produced upstream.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

CASE_REPORT_FILE = OUTPUT_DIR / "case_report.csv"
CASE_REGISTRY_JSON = OUTPUT_DIR / "case_registry.json"
CASE_SUMMARY_TXT = OUTPUT_DIR / "case_summary.txt"
OPERATOR_EXPLANATIONS_DIR = OUTPUT_DIR / "operator_cases"
INTERNAL_EXPLANATIONS_DIR = OUTPUT_DIR / "internal_cases"


# ============================================================
# IO HELPERS
# ============================================================

def read_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def read_text_if_exists(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


# ============================================================
# LOADERS
# ============================================================

def load_registry_payload() -> Dict[str, Any]:
    return read_json(CASE_REGISTRY_JSON)


def load_cases() -> List[Dict[str, Any]]:
    payload = load_registry_payload()
    return payload.get("cases", [])


def load_case_report_rows() -> List[Dict[str, str]]:
    return read_csv_rows(CASE_REPORT_FILE)


def load_case_report_index() -> Dict[str, Dict[str, str]]:
    rows = load_case_report_rows()
    return {row["case_id"]: row for row in rows if row.get("case_id")}


def load_case_index() -> Dict[str, Dict[str, Any]]:
    cases = load_cases()
    return {case["case_id"]: case for case in cases if case.get("case_id")}


# ============================================================
# SAFE ACCESS HELPERS
# ============================================================

def get_nested(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_case_status(value: Any) -> str:
    status = normalize_text(value).upper()
    if status == "OPEN":
        return "ACTIVE"
    if status in {"ACTIVE", "INACTIVE", "CLOSED"}:
        return status
    return "UNKNOWN"


def contains_text(value: Any, needle: str) -> bool:
    return needle.lower() in normalize_text(value).lower()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# FORMATTING HELPERS
# ============================================================

def hr(char: str = "=", width: int = 100) -> str:
    return char * width


def bullet_lines(items: Sequence[str], prefix: str = "- ") -> str:
    if not items:
        return f"{prefix}None"
    return "\n".join(f"{prefix}{item}" for item in items)


def section(title: str, body: str) -> str:
    return f"{title}\n{body}"


def format_confidence(value: Any) -> str:
    text = normalize_text(value)
    return text if text else "unknown"


def format_float(value: Any, digits: int = 2, fallback: str = "unknown") -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return fallback


def first_nonempty(*values: Any, fallback: str = "") -> str:
    for value in values:
        text = normalize_text(value)
        if text:
            return text
    return fallback


# ============================================================
# CASE EXTRACTION
# ============================================================

def get_case_status(case: Dict[str, Any]) -> str:
    metadata_status = get_nested(case, "metadata", "normalized_status")
    if normalize_text(metadata_status):
        return normalize_case_status(metadata_status)
    return normalize_case_status(case.get("status"))


def get_case_headline(case: Dict[str, Any]) -> str:
    evaluation = case.get("evaluation", {}) or {}
    decision_state = first_nonempty(evaluation.get("decision_state"), fallback="UNKNOWN")
    urgency = first_nonempty(evaluation.get("urgency"), fallback="UNKNOWN")
    posture = first_nonempty(evaluation.get("response_posture"), fallback="UNKNOWN")
    case_id = first_nonempty(case.get("case_id"), fallback="NO_ID")
    return f"{case_id} | {decision_state} | {urgency} | {posture}"


def get_case_counts(case: Dict[str, Any]) -> str:
    events = len(as_list(case.get("event_ids")))
    tickets = len(as_list(case.get("ticket_ids")))
    assets = len(as_list(case.get("asset_ids")))
    return f"Events={events} Tickets={tickets} Assets={assets}"


def get_case_operator_summary(case: Dict[str, Any]) -> str:
    return first_nonempty(
        get_nested(case, "evaluation", "operator_summary"),
        get_nested(case, "evaluation", "internal_summary"),
        fallback="No summary available",
    )


def get_case_failure_layers(case: Dict[str, Any]) -> List[str]:
    return [normalize_text(x) for x in as_list(get_nested(case, "evaluation", "failure_layers")) if normalize_text(x)]


def get_case_why_now(case: Dict[str, Any]) -> List[str]:
    return [normalize_text(x) for x in as_list(get_nested(case, "evaluation", "why_now")) if normalize_text(x)]


def get_case_what_changed(case: Dict[str, Any]) -> List[str]:
    return [normalize_text(x) for x in as_list(get_nested(case, "evaluation", "what_changed")) if normalize_text(x)]


def get_case_actions(case: Dict[str, Any]) -> List[str]:
    return [normalize_text(x) for x in as_list(get_nested(case, "evaluation", "recommended_actions")) if normalize_text(x)]


def get_case_evidence(case: Dict[str, Any], layer_name: str) -> List[Dict[str, Any]]:
    return [
        item for item in as_list(get_nested(case, "evaluation", "evidence_layers", layer_name))
        if isinstance(item, dict)
    ]


def get_case_trend(case: Dict[str, Any]) -> str:
    return first_nonempty(
        get_nested(case, "metadata", "trend"),
        fallback="UNKNOWN",
    )


def get_case_investigation_roi(case: Dict[str, Any]) -> float:
    return safe_float(get_nested(case, "metadata", "investigation_roi"), 0.0)


def get_case_temporal_change(case: Dict[str, Any]) -> Dict[str, Any]:
    value = get_nested(case, "metadata", "temporal_change", default={})
    return value if isinstance(value, dict) else {}


def get_case_state_snapshot(case: Dict[str, Any]) -> Dict[str, Any]:
    value = get_nested(case, "metadata", "state_snapshot", default={})
    return value if isinstance(value, dict) else {}


def get_case_prior_state_snapshot(case: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    value = get_nested(case, "metadata", "prior_state_snapshot", default=None)
    return value if isinstance(value, dict) else None


# ============================================================
# SORTING
# ============================================================

DECISION_PRIORITY = {
    "STOP_WORK": 0,
    "HIGH_RISK_OF_MISJUDGMENT": 1,
    "PROCEED_WITH_VERIFICATION": 2,
    "SAFE_TO_PROCEED": 3,
    "NEEDS_REVIEW": 4,
    "UNKNOWN": 5,
}

URGENCY_PRIORITY = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MODERATE": 2,
    "LOW": 3,
    "UNKNOWN": 4,
}

TREND_PRIORITY = {
    "WORSENING": 0,
    "NEW": 1,
    "STABLE": 2,
    "IMPROVING": 3,
    "UNKNOWN": 4,
}


def sort_cases_by_decision_priority(cases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(case: Dict[str, Any]) -> Tuple[int, int, str]:
        evaluation = case.get("evaluation", {}) or {}
        decision_state = first_nonempty(evaluation.get("decision_state"), fallback="UNKNOWN")
        urgency = first_nonempty(evaluation.get("urgency"), fallback="UNKNOWN")
        updated_at = first_nonempty(case.get("updated_at"), fallback="")
        return (
            DECISION_PRIORITY.get(decision_state, 99),
            URGENCY_PRIORITY.get(urgency, 99),
            updated_at,
        )

    return sorted(cases, key=key)


def sort_cases_by_investigation_roi(cases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(case: Dict[str, Any]) -> Tuple[float, int, int, str]:
        roi = get_case_investigation_roi(case)
        trend = get_case_trend(case)
        evaluation = case.get("evaluation", {}) or {}
        decision_state = first_nonempty(evaluation.get("decision_state"), fallback="UNKNOWN")
        updated_at = first_nonempty(case.get("updated_at"), fallback="")
        return (
            -roi,
            TREND_PRIORITY.get(trend, 99),
            DECISION_PRIORITY.get(decision_state, 99),
            updated_at,
        )

    return sorted(cases, key=key)


def sort_cases_by_trend(cases: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def key(case: Dict[str, Any]) -> Tuple[int, float, str]:
        trend = get_case_trend(case)
        roi = get_case_investigation_roi(case)
        updated_at = first_nonempty(case.get("updated_at"), fallback="")
        return (
            TREND_PRIORITY.get(trend, 99),
            -roi,
            updated_at,
        )

    return sorted(cases, key=key)


# ============================================================
# SEARCH
# ============================================================

def search_cases(cases: Sequence[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return list(cases)

    results: List[Dict[str, Any]] = []

    for case in cases:
        temporal_change = get_case_temporal_change(case)
        haystacks = [
            case.get("case_id"),
            case.get("updated_at"),
            case.get("status"),
            get_nested(case, "metadata", "normalized_status"),
            *as_list(case.get("event_ids")),
            *as_list(case.get("ticket_ids")),
            *as_list(case.get("asset_ids")),
            get_nested(case, "evaluation", "decision_state"),
            get_nested(case, "evaluation", "urgency"),
            get_nested(case, "evaluation", "response_posture"),
            get_nested(case, "evaluation", "operator_summary"),
            get_nested(case, "evaluation", "internal_summary"),
            get_case_trend(case),
            get_nested(case, "metadata", "investigation_roi"),
            temporal_change.get("decision_shift"),
            temporal_change.get("trend"),
            *get_case_failure_layers(case),
            *get_case_why_now(case),
            *get_case_what_changed(case),
            *get_case_actions(case),
        ]

        matched = any(q in normalize_text(item).lower() for item in haystacks)
        if matched:
            results.append(case)
            continue

        for layer_name in ["observed", "derived", "inferred", "assumed"]:
            layer = get_case_evidence(case, layer_name)
            if any(q in normalize_text(item.get("statement")).lower() for item in layer):
                results.append(case)
                break

    return results


def search_by_ticket_id(cases: Sequence[Dict[str, Any]], ticket_id: str) -> List[Dict[str, Any]]:
    needle = ticket_id.strip().lower()
    return [
        case for case in cases
        if any(needle == normalize_text(t).lower() for t in as_list(case.get("ticket_ids")))
    ]


def search_by_event_id(cases: Sequence[Dict[str, Any]], event_id: str) -> List[Dict[str, Any]]:
    needle = event_id.strip().lower()
    return [
        case for case in cases
        if any(needle == normalize_text(e).lower() for e in as_list(case.get("event_ids")))
    ]


def search_by_asset_id(cases: Sequence[Dict[str, Any]], asset_id: str) -> List[Dict[str, Any]]:
    needle = asset_id.strip().lower()
    return [
        case for case in cases
        if any(needle == normalize_text(a).lower() for a in as_list(case.get("asset_ids")))
    ]


# ============================================================
# DISPLAY
# ============================================================

def render_case_list(cases: Sequence[Dict[str, Any]], limit: Optional[int] = None) -> str:
    rows = list(cases[:limit] if limit is not None else cases)

    if not rows:
        return "No cases found."

    lines: List[str] = []
    for idx, case in enumerate(rows, start=1):
        status = get_case_status(case)
        trend = get_case_trend(case)
        roi = get_case_investigation_roi(case)
        lines.append(
            f"{idx}. {get_case_headline(case)} | STATUS={status} | TREND={trend} | ROI={format_float(roi, 2, '0.00')}"
        )
        lines.append(f"   {get_case_counts(case)}")
        lines.append(f"   {get_case_operator_summary(case)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_evidence_layer(case: Dict[str, Any], layer_name: str, heading: str) -> str:
    items = get_case_evidence(case, layer_name)
    if not items:
        return f"{heading}\n- None"

    lines: List[str] = []
    for item in items:
        statement = normalize_text(item.get("statement"))
        confidence = normalize_text(item.get("confidence"))
        if confidence:
            lines.append(f"- {statement} (confidence: {confidence})")
        else:
            lines.append(f"- {statement}")

    return f"{heading}\n" + "\n".join(lines)


def render_temporal_change(case: Dict[str, Any]) -> str:
    temporal_change = get_case_temporal_change(case)
    current_snapshot = get_case_state_snapshot(case)
    prior_snapshot = get_case_prior_state_snapshot(case)

    lines: List[str] = []
    lines.append(f"Trend: {get_case_trend(case)}")
    lines.append(f"Investigation ROI: {format_float(get_case_investigation_roi(case), 2, '0.00')}")

    if temporal_change:
        lines.append(f"Decision shift: {first_nonempty(temporal_change.get('decision_shift'), fallback='UNKNOWN')}")
        lines.append(f"Confidence delta: {format_float(temporal_change.get('confidence_delta'), 4)}")
        lines.append(f"Uncertainty delta: {format_float(temporal_change.get('uncertainty_delta'), 4)}")
        lines.append(f"Alignment delta: {format_float(temporal_change.get('alignment_delta'), 4)}")
        lines.append(f"Event count delta: {normalize_text(temporal_change.get('event_count_delta')) or '0'}")

    if current_snapshot:
        lines.append("")
        lines.append("Current snapshot")
        lines.append(f"- Decision state: {first_nonempty(current_snapshot.get('decision_state'), fallback='UNKNOWN')}")
        lines.append(f"- Confidence: {format_float(current_snapshot.get('confidence'), 4)}")
        lines.append(f"- Uncertainty burden: {format_float(current_snapshot.get('uncertainty_burden'), 4)}")
        lines.append(f"- Alignment score: {format_float(current_snapshot.get('alignment_score'), 4)}")
        lines.append(f"- Event count: {normalize_text(current_snapshot.get('event_count')) or '0'}")

    if prior_snapshot:
        lines.append("")
        lines.append("Prior snapshot")
        lines.append(f"- Decision state: {first_nonempty(prior_snapshot.get('decision_state'), fallback='UNKNOWN')}")
        lines.append(f"- Confidence: {format_float(prior_snapshot.get('confidence'), 4)}")
        lines.append(f"- Uncertainty burden: {format_float(prior_snapshot.get('uncertainty_burden'), 4)}")
        lines.append(f"- Alignment score: {format_float(prior_snapshot.get('alignment_score'), 4)}")
        lines.append(f"- Event count: {normalize_text(prior_snapshot.get('event_count')) or '0'}")

    return "\n".join(lines)


def render_case_detail(case: Dict[str, Any]) -> str:
    evaluation = case.get("evaluation", {}) or {}

    header_lines = [
        hr(),
        "RISKSEER CASE DETAIL",
        hr(),
        f"Case ID: {first_nonempty(case.get('case_id'), fallback='UNKNOWN')}",
        f"Created at: {first_nonempty(case.get('created_at'), fallback='UNKNOWN')}",
        f"Updated at: {first_nonempty(case.get('updated_at'), fallback='UNKNOWN')}",
        f"Status: {get_case_status(case)}",
        "",
        f"Decision state: {first_nonempty(evaluation.get('decision_state'), fallback='UNKNOWN')}",
        f"Urgency: {first_nonempty(evaluation.get('urgency'), fallback='UNKNOWN')}",
        f"Response posture: {first_nonempty(evaluation.get('response_posture'), fallback='UNKNOWN')}",
        f"Evaluation confidence: {format_confidence(evaluation.get('confidence'))}",
        f"Uncertainty burden: {format_confidence(evaluation.get('uncertainty_burden'))}",
        f"Trend: {get_case_trend(case)}",
        f"Investigation ROI: {format_float(get_case_investigation_roi(case), 2, '0.00')}",
        "",
        f"Operator summary: {first_nonempty(evaluation.get('operator_summary'), fallback='None')}",
        f"Internal summary: {first_nonempty(evaluation.get('internal_summary'), fallback='None')}",
        "",
        get_case_counts(case),
        f"Event IDs: {', '.join(as_list(case.get('event_ids'))) if as_list(case.get('event_ids')) else 'None'}",
        f"Ticket IDs: {', '.join(as_list(case.get('ticket_ids'))) if as_list(case.get('ticket_ids')) else 'None'}",
        f"Asset IDs: {', '.join(as_list(case.get('asset_ids'))) if as_list(case.get('asset_ids')) else 'None'}",
    ]

    temporal_section = section(
        "Temporal change",
        render_temporal_change(case)
    )

    failure_layers = section(
        "Failure layers",
        bullet_lines(get_case_failure_layers(case))
    )

    why_now = section(
        "Why now",
        bullet_lines(get_case_why_now(case))
    )

    what_changed = section(
        "What changed",
        bullet_lines(get_case_what_changed(case))
    )

    actions = section(
        "Recommended actions",
        bullet_lines(get_case_actions(case))
    )

    alignment = get_nested(case, "evaluation", "alignment", default={}) or {}
    information = get_nested(case, "evaluation", "information_integrity", default={}) or {}
    behavior = get_nested(case, "evaluation", "behavioral_risk", default={}) or {}

    assessments = "\n\n".join([
        section(
            "Alignment assessment",
            "\n".join([
                f"Summary: {first_nonempty(alignment.get('summary'), fallback='None')}",
                f"Spatial alignment: {format_confidence(alignment.get('spatial_alignment'))}",
                f"Temporal alignment: {format_confidence(alignment.get('temporal_alignment'))}",
                f"Ticket match strength: {format_confidence(alignment.get('ticket_match_strength'))}",
                f"Asset relevance: {format_confidence(alignment.get('asset_relevance'))}",
                "Concerns:",
                bullet_lines(as_list(alignment.get('concerns'))),
            ])
        ),
        section(
            "Information integrity assessment",
            "\n".join([
                f"Summary: {first_nonempty(information.get('summary'), fallback='None')}",
                f"Overall confidence: {format_confidence(information.get('overall_confidence'))}",
                f"Ticket quality confidence: {format_confidence(get_nested(information, 'ticket_quality', 'confidence'))}",
                f"Asset quality confidence: {format_confidence(get_nested(information, 'asset_quality', 'confidence'))}",
                f"Event quality confidence: {format_confidence(get_nested(information, 'event_quality', 'confidence'))}",
                "Concerns:",
                bullet_lines(as_list(information.get('concerns'))),
            ])
        ),
        section(
            "Behavioral risk assessment",
            "\n".join([
                f"Summary: {first_nonempty(behavior.get('summary'), fallback='None')}",
                f"Habit risk: {format_confidence(behavior.get('habit_risk'))}",
                f"Repeated activity: {first_nonempty(behavior.get('repeated_activity'), fallback='False')}",
                f"Escalating activity: {first_nonempty(behavior.get('escalating_activity'), fallback='False')}",
                f"Conflicting signals ignored: {first_nonempty(behavior.get('conflicting_signals_ignored'), fallback='False')}",
                "Concerns:",
                bullet_lines(as_list(behavior.get('concerns'))),
            ])
        ),
    ])

    evidence = "\n\n".join([
        render_evidence_layer(case, "observed", "Observed facts"),
        render_evidence_layer(case, "derived", "Derived facts"),
        render_evidence_layer(case, "inferred", "Inferences"),
        render_evidence_layer(case, "assumed", "Assumptions"),
    ])

    return "\n\n".join([
        "\n".join(header_lines),
        temporal_section,
        failure_layers,
        why_now,
        what_changed,
        actions,
        assessments,
        evidence,
    ])


# ============================================================
# EXPLANATION FILE ACCESS
# ============================================================

def operator_explanation_path(case_id: str) -> Path:
    return OPERATOR_EXPLANATIONS_DIR / f"case_{case_id}.txt"


def internal_explanation_path(case_id: str) -> Path:
    return INTERNAL_EXPLANATIONS_DIR / f"case_{case_id}.txt"


def open_saved_explanations(case_id: str) -> Tuple[Optional[str], Optional[str]]:
    return (
        read_text_if_exists(operator_explanation_path(case_id)),
        read_text_if_exists(internal_explanation_path(case_id)),
    )


# ============================================================
# MENU ACTIONS
# ============================================================

def prompt(text: str) -> str:
    return input(text).strip()


def resolve_case_selection(cases: Sequence[Dict[str, Any]], raw: str) -> Optional[Dict[str, Any]]:
    """
    Accept either:
    - displayed list number: 1, 2, 3, ...
    - exact case ID: 00023
    """
    value = raw.strip()
    if not value:
        print("No selection entered.")
        return None

    for case in cases:
        if normalize_text(case.get("case_id")) == value:
            return case

    try:
        idx = int(value)
    except ValueError:
        print("Invalid selection. Enter a displayed row number or exact case ID.")
        return None

    if idx < 1 or idx > len(cases):
        print("Out of range.")
        return None

    return cases[idx - 1]


def choose_case(cases: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not cases:
        print("No cases available.")
        return None

    print(render_case_list(cases))
    raw = prompt("\nEnter displayed row number or exact case ID: ")
    return resolve_case_selection(cases, raw)


def show_case_detail(case: Dict[str, Any]) -> None:
    print("\n" + render_case_detail(case) + "\n")


def show_saved_explanations(case: Dict[str, Any]) -> None:
    case_id = normalize_text(case.get("case_id"))
    operator_text, internal_text = open_saved_explanations(case_id)

    print("\n" + hr())
    print(f"SAVED EXPLANATIONS FOR CASE {case_id}")
    print(hr())

    print("\nOPERATOR EXPLANATION\n")
    print(operator_text if operator_text else "No saved operator explanation found.")

    print("\n" + hr("-"))
    print("\nINTERNAL EXPLANATION\n")
    print(internal_text if internal_text else "No saved internal explanation found.")
    print("")


def list_top_cases_by_roi(cases: Sequence[Dict[str, Any]]) -> None:
    ranked = sort_cases_by_investigation_roi(cases)
    print("\n" + render_case_list(ranked, limit=20) + "\n")


def list_cases_by_trend(cases: Sequence[Dict[str, Any]]) -> None:
    ranked = sort_cases_by_trend(cases)
    print("\n" + render_case_list(ranked, limit=50) + "\n")


def search_menu(cases: Sequence[Dict[str, Any]]) -> None:
    print("\nSearch options")
    print("1. General text search")
    print("2. Search by ticket ID")
    print("3. Search by event ID")
    print("4. Search by asset ID")

    choice = prompt("Choose: ")

    if choice == "1":
        q = prompt("Search text: ")
        results = search_cases(cases, q)
    elif choice == "2":
        q = prompt("Ticket ID: ")
        results = search_by_ticket_id(cases, q)
    elif choice == "3":
        q = prompt("Event ID: ")
        results = search_by_event_id(cases, q)
    elif choice == "4":
        q = prompt("Asset ID: ")
        results = search_by_asset_id(cases, q)
    else:
        print("Invalid choice.")
        return

    print("")
    print(render_case_list(results, limit=50))
    print("")

    if results:
        open_detail = prompt("Open one of these cases? (y/n): ").lower()
        if open_detail == "y":
            case = choose_case(results)
            if case:
                show_case_detail(case)


def inspect_case_menu(cases: Sequence[Dict[str, Any]]) -> None:
    case = choose_case(cases)
    if not case:
        return

    while True:
        print("\nCase inspection menu")
        print("1. View structured case detail")
        print("2. View saved explanation files")
        print("3. Back")

        choice = prompt("Choose: ")
        if choice == "1":
            show_case_detail(case)
        elif choice == "2":
            show_saved_explanations(case)
        elif choice == "3":
            return
        else:
            print("Invalid choice.")


# ============================================================
# MAIN PROGRAM
# ============================================================

def ensure_outputs_exist() -> None:
    missing: List[Path] = []
    for path in [CASE_REGISTRY_JSON, CASE_REPORT_FILE]:
        if not path.exists():
            missing.append(path)

    if missing:
        missing_list = "\n".join(f"- {path}" for path in missing)
        raise FileNotFoundError(
            "Riskseer output files are missing.\n"
            "Run main.py first so the pipeline generates outputs.\n"
            f"Missing:\n{missing_list}"
        )


def main() -> None:
    ensure_outputs_exist()

    cases = load_cases()

    print("\n" + hr())
    print("RISKSEER CASE LOOKUP")
    print(hr())
    print(f"Cases loaded: {len(cases)}")
    print(f"Registry source: {CASE_REGISTRY_JSON}")
    print(f"Report source:   {CASE_REPORT_FILE}")

    while True:
        print("\nMenu")
        print("1. List top cases by investigation priority (ROI)")
        print("2. List cases by trend")
        print("3. Open case")
        print("4. Search cases")
        print("5. Show case summary file")
        print("6. Exit")

        choice = prompt("Choose: ")

        if choice == "1":
            list_top_cases_by_roi(cases)
        elif choice == "2":
            list_cases_by_trend(cases)
        elif choice == "3":
            inspect_case_menu(sort_cases_by_investigation_roi(cases))
        elif choice == "4":
            search_menu(cases)
        elif choice == "5":
            summary = read_text_if_exists(CASE_SUMMARY_TXT)
            print("")
            print(summary if summary else "No summary file found.")
            print("")
        elif choice == "6":
            print("Exiting lookup.")
            return
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()