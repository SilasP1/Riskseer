from __future__ import annotations

from pathlib import Path
from typing import Any
import csv
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Riskseer API", version="1.0.0")

# Allow the local frontend dev server to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
REGISTRY_PATH = OUTPUT_DIR / "case_registry.json"
REPORT_PATH = OUTPUT_DIR / "case_report.csv"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to float without crashing on bad input."""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to int without crashing on bad input."""
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def read_json_file(path: Path) -> dict[str, Any]:
    """Load a JSON file or return an empty dict if missing."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    """Load CSV rows safely. Returns an empty list if the file is missing."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def pick_first_nonempty(*values: Any) -> Any:
    """Return the first value that is meaningfully populated."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def normalize_list(value: Any) -> list[Any]:
    """Ensure a field is always a list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def build_report_index(report_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index report rows by case_id."""
    by_id: dict[str, dict[str, Any]] = {}
    for row in report_rows:
        case_id = str(row.get("case_id", "")).strip()
        if case_id:
            by_id[case_id] = row
    return by_id


def extract_raw_cases(registry: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Pull the case list from the registry.

    Expected structure:
    {
        "generated_at": "...",
        "case_count": N,
        "cases": [ ... ]
    }
    """
    raw_cases = registry.get("cases", [])
    return raw_cases if isinstance(raw_cases, list) else []


def normalize_case(case: dict[str, Any], report_row: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Convert a raw case from the registry into the API contract the frontend uses.
    Keep backend richness; do not strip fields unless they are clearly internal noise.
    """
    report_row = report_row or {}
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}

    evaluation = case.get("evaluation") if isinstance(case.get("evaluation"), dict) else {}

    event_ids = normalize_list(case.get("event_ids"))
    ticket_ids = normalize_list(case.get("ticket_ids"))
    asset_ids = normalize_list(case.get("asset_ids"))

    observations = normalize_list(case.get("observations"))
    attachments = normalize_list(case.get("attachments"))
    failure_layers = normalize_list(
        pick_first_nonempty(case.get("failure_layers"), evaluation.get("failure_layers"))
    )
    why_now = normalize_list(pick_first_nonempty(case.get("why_now"), evaluation.get("why_now")))
    what_changed = normalize_list(
        pick_first_nonempty(case.get("what_changed"), evaluation.get("what_changed"))
    )
    recommended_actions = normalize_list(
        pick_first_nonempty(
            case.get("recommended_actions"),
            evaluation.get("recommended_actions"),
        )
    )

    identity = case.get("identity") if isinstance(case.get("identity"), dict) else {}
    alignment_assessment = (
        case.get("alignment_assessment")
        if isinstance(case.get("alignment_assessment"), dict)
        else (
            evaluation.get("alignment")
            if isinstance(evaluation.get("alignment"), dict)
            else {}
        )
    )
    information_integrity_assessment = (
        case.get("information_integrity_assessment")
        if isinstance(case.get("information_integrity_assessment"), dict)
        else (
            evaluation.get("information_integrity")
            if isinstance(evaluation.get("information_integrity"), dict)
            else {}
        )
    )
    behavioral_risk_assessment = (
        case.get("behavioral_risk_assessment")
        if isinstance(case.get("behavioral_risk_assessment"), dict)
        else (
            evaluation.get("behavioral_risk")
            if isinstance(evaluation.get("behavioral_risk"), dict)
            else {}
        )
    )
    evidence_layers = (
        evaluation.get("evidence_layers")
        if isinstance(evaluation.get("evidence_layers"), dict)
        else {}
    )
    responsibility_integrity = (
        evaluation.get("responsibility_integrity")
        if isinstance(evaluation.get("responsibility_integrity"), dict)
        else (
            metadata.get("responsibility_integrity")
            if isinstance(metadata.get("responsibility_integrity"), dict)
            else {}
        )
    )
    decision_defensibility = (
        evaluation.get("decision_defensibility")
        if isinstance(evaluation.get("decision_defensibility"), dict)
        else (
            metadata.get("decision_defensibility")
            if isinstance(metadata.get("decision_defensibility"), dict)
            else {}
        )
    )
    conflicts = normalize_list(
        pick_first_nonempty(case.get("conflicts"), evaluation.get("conflicts"))
    )

    # Preserve backend values first. Use report row only as fallback.
    decision_state = pick_first_nonempty(
        case.get("decision_state"),
        evaluation.get("decision_state"),
        report_row.get("decision_state"),
    )
    urgency = pick_first_nonempty(
        case.get("urgency"),
        evaluation.get("urgency"),
        report_row.get("urgency"),
    )
    response_posture = pick_first_nonempty(
        case.get("response_posture"),
        evaluation.get("response_posture"),
        report_row.get("response_posture"),
    )
    trend = pick_first_nonempty(
        case.get("trend"),
        evaluation.get("trend"),
        report_row.get("trend"),
    )

    operator_summary = pick_first_nonempty(
        case.get("operator_summary"),
        evaluation.get("operator_summary"),
        report_row.get("operator_summary"),
        report_row.get("summary"),
    )
    internal_summary = pick_first_nonempty(
        case.get("internal_summary"),
        evaluation.get("internal_summary"),
        report_row.get("internal_summary"),
    )

    roi = safe_float(
        pick_first_nonempty(
            case.get("investigation_roi"),
            report_row.get("investigation_roi"),
            report_row.get("roi"),
        ),
        default=0.0,
    )

    evaluation_confidence = safe_float(
        pick_first_nonempty(
            case.get("evaluation_confidence"),
            evaluation.get("evaluation_confidence"),
            evaluation.get("confidence"),
            report_row.get("evaluation_confidence"),
            report_row.get("confidence"),
        ),
        default=0.0,
    )

    uncertainty_burden = safe_float(
        pick_first_nonempty(
            case.get("uncertainty_burden"),
            evaluation.get("uncertainty_burden"),
            report_row.get("uncertainty_burden"),
            report_row.get("uncertainty"),
        ),
        default=0.0,
    )

    alignment_score = safe_float(
        pick_first_nonempty(
            case.get("alignment_score"),
            evaluation.get("alignment_score"),
            report_row.get("alignment_score"),
        ),
        default=0.0,
    )

    # Count fallbacks in case older registry objects don't include arrays.
    event_count = len(event_ids) if event_ids else safe_int(report_row.get("event_count"), 0)
    ticket_count = len(ticket_ids) if ticket_ids else safe_int(report_row.get("ticket_count"), 0)
    asset_count = len(asset_ids) if asset_ids else safe_int(report_row.get("asset_count"), 0)

    primary_failure_layer = None
    if "HABIT_CONTINUATION" in failure_layers:
        primary_failure_layer = "HABIT_CONTINUATION"
    elif "AUTHORIZATION_AMBIGUITY" in failure_layers:
        primary_failure_layer = "AUTHORIZATION_AMBIGUITY"
    elif "PROCESS_BYPASS_OR_GAP" in failure_layers:
        primary_failure_layer = "PROCESS_BYPASS_OR_GAP"
    elif "CONTEXT_LIMITATION" in failure_layers:
        primary_failure_layer = "CONTEXT_LIMITATION"
    elif "LIMITED_VISIBILITY_WORK" in failure_layers:
        primary_failure_layer = "LIMITED_VISIBILITY_WORK"
    elif "CHANGING_SITE_CONDITIONS" in failure_layers:
        primary_failure_layer = "CHANGING_SITE_CONDITIONS"

    return {
        "case_id": str(case.get("case_id", "")).strip(),
        "created_at": case.get("created_at"),
        "updated_at": case.get("updated_at"),
        "status": case.get("status"),
        "decision_state": decision_state,
        "urgency": urgency,
        "response_posture": response_posture,
        "trend": trend,
        "roi": roi,
        "operator_summary": operator_summary,
        "internal_summary": internal_summary,
        "evaluation_confidence": evaluation_confidence,
        "uncertainty_burden": uncertainty_burden,
        "alignment_score": alignment_score,
        "event_count": event_count,
        "ticket_count": ticket_count,
        "asset_count": asset_count,
        "event_ids": event_ids,
        "ticket_ids": ticket_ids,
        "asset_ids": asset_ids,
        "context_ticket_ids": normalize_list(case.get("context_ticket_ids")),
        "context_asset_ids": normalize_list(case.get("context_asset_ids")),
        "field_report_ids": normalize_list(case.get("field_report_ids")),
        "marking_ids": normalize_list(case.get("marking_ids")),
        "positive_response_ids": normalize_list(case.get("positive_response_ids")),
        "parent_case_id": pick_first_nonempty(case.get("parent_case_id"), metadata.get("parent_case_id")),
        "forked_from_case_id": pick_first_nonempty(case.get("forked_from_case_id"), metadata.get("branch_from_case_id")),
        "lineage_notes": normalize_list(case.get("lineage_notes")),
        "related_case_ids": normalize_list(metadata.get("related_case_ids")),
        "sibling_case_ids": normalize_list(metadata.get("sibling_case_ids")),
        "branch_reason": pick_first_nonempty(metadata.get("branch_reason"), metadata.get("last_branch_reason")),
        "case_family_role": metadata.get("case_family_role"),
        "identity": identity,
        "attachments": attachments,
        "observations": observations,
        "primary_failure_layer": primary_failure_layer,
        "failure_layers": failure_layers,
        "conflicts": conflicts,
        "why_now": why_now,
        "what_changed": what_changed,
        "recommended_actions": recommended_actions,
        "alignment_assessment": alignment_assessment,
        "information_integrity_assessment": information_integrity_assessment,
        "behavioral_risk_assessment": behavioral_risk_assessment,
        "responsibility_integrity": responsibility_integrity,
        "decision_defensibility": decision_defensibility,
        "evidence_layers": evidence_layers,
        "state_snapshot": metadata.get("state_snapshot"),
        "prior_state_snapshot": metadata.get("prior_state_snapshot"),
        "temporal_change": metadata.get("temporal_change"),
        "hidden_risk": metadata.get("hidden_risk"),
        "ui_summary": metadata.get("ui_summary"),
        "metadata": metadata,
        # Keep raw report context for debugging if needed by the UI later.
        "report_row": report_row,
    }


def load_cases() -> list[dict[str, Any]]:
    """Load and normalize all cases from output files."""
    registry = read_json_file(REGISTRY_PATH)
    report_rows = read_csv_rows(REPORT_PATH)
    report_index = build_report_index(report_rows)

    raw_cases = extract_raw_cases(registry)
    normalized_cases: list[dict[str, Any]] = []

    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            continue

        case_id = str(raw_case.get("case_id", "")).strip()
        report_row = report_index.get(case_id, {})
        normalized_cases.append(normalize_case(raw_case, report_row))

    # Sort actionable cases first, then by ROI descending, then urgency buckets.
    status_rank = {"ACTIVE": 3, "INACTIVE": 2, "CLOSED": 1}
    urgency_rank = {"CRITICAL": 4, "HIGH": 3, "MODERATE": 2, "LOW": 1}

    normalized_cases.sort(
        key=lambda c: (
            status_rank.get(str(c.get("status", "")).upper(), 0),
            safe_float(c.get("roi"), 0.0),
            urgency_rank.get(str(c.get("urgency", "")).upper(), 0),
            c.get("case_id", ""),
        ),
        reverse=True,
    )

    return normalized_cases


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Riskseer API is running"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "registry_exists": REGISTRY_PATH.exists(),
        "report_exists": REPORT_PATH.exists(),
        "registry_path": str(REGISTRY_PATH),
        "report_path": str(REPORT_PATH),
    }


@app.get("/api/cases")
def get_cases() -> dict[str, Any]:
    cases = load_cases()
    return {
        "case_count": len(cases),
        "cases": cases,
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    cases = load_cases()
    for case in cases:
        if case.get("case_id") == case_id:
            return case
    raise HTTPException(status_code=404, detail=f"Case {case_id} not found")
