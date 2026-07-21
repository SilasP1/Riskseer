"""
main.py

GOAL
----
This file orchestrates the Riskseer pipeline from input loading to output writing.

It exists to connect the system modules without owning business logic.

WHAT main.py DOES
-----------------
1. Loads input CSVs.
2. Normalizes raw rows into schema records.
3. Runs event-level analysis.
4. Builds/updates the case registry.
5. Evaluates each case.
6. Loads prior saved case state when available.
7. Seeds prior saved cases back into the registry builder when available.
8. Produces output tables and explanation files.
9. Writes artifacts to disk.

WHAT main.py MUST NOT DO
------------------------
1. It must not define case scoring or decision logic.
2. It must not interpret operator meaning beyond calling the proper modules.
3. It must not duplicate logic from:
   - event_logic.py
   - case.py
   - case_logic.py
   - explanations.py
4. It must not become a dumping ground for one-off rules.
5. It must stay orchestration-only.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from case import attach_context_records_to_registry, build_case_registry_from_analyses
from case_audit import build_audit_payload, build_audit_text
from case_logic import evaluate_registry_in_place
from event_logic import (
    analyze_events,
    normalize_asset_records,
    normalize_event_records,
    normalize_field_report_records,
    normalize_marking_records,
    normalize_positive_response_records,
    normalize_ticket_records,
)
from explanations import (
    build_case_report_rows,
    build_internal_explanation,
    build_operator_explanation,
    build_case_snapshot,
)
from schemas import (
    AssetRecord,
    CaseRecord,
    EventRecord,
    FieldReportRecord,
    MarkingRecord,
    PositiveResponseRecord,
    TicketRecord,
)


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
ARCHIVE_DIR = DATA_DIR / "archive"

EVENTS_FILE = DATA_DIR / "events.csv"
TICKETS_FILE = DATA_DIR / "tickets.csv"
ASSETS_FILE = DATA_DIR / "assets.csv"
FIELD_REPORTS_FILE = DATA_DIR / "field_reports.csv"
MARKINGS_FILE = DATA_DIR / "markings.csv"
POSITIVE_RESPONSES_FILE = DATA_DIR / "positive_responses.csv"

CASE_REPORT_FILE = OUTPUT_DIR / "case_report.csv"
CASE_REGISTRY_JSON = OUTPUT_DIR / "case_registry.json"
CASE_TREND_HISTORY_JSON = OUTPUT_DIR / "case_trend_history.json"
CASE_AUDIT_JSON = OUTPUT_DIR / "case_contradiction_audit.json"
CASE_AUDIT_TXT = OUTPUT_DIR / "case_contradiction_audit.txt"
CASE_SUMMARY_TXT = OUTPUT_DIR / "case_summary.txt"
OPERATOR_EXPLANATIONS_DIR = OUTPUT_DIR / "operator_cases"
INTERNAL_EXPLANATIONS_DIR = OUTPUT_DIR / "internal_cases"
MAX_EVENT_FUTURE_SKEW_MIN = 5.0


# ============================================================
# GENERIC HELPERS
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def remove_file_if_exists(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def clear_directory_files(path: Path) -> None:
    if not path.exists():
        return

    for child in path.iterdir():
        if child.is_file():
            child.unlink()


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input file: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def write_csv_rows(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    ensure_directory(path.parent)

    if not rows:
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write("")
        return

    fieldnames: List[str] = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)


def write_json(path: Path, payload: Any) -> None:
    ensure_directory(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def reset_generated_outputs() -> None:
    remove_file_if_exists(CASE_REPORT_FILE)
    remove_file_if_exists(CASE_REGISTRY_JSON)
    remove_file_if_exists(CASE_AUDIT_JSON)
    remove_file_if_exists(CASE_AUDIT_TXT)
    remove_file_if_exists(CASE_SUMMARY_TXT)
    clear_directory_files(OPERATOR_EXPLANATIONS_DIR)
    clear_directory_files(INTERNAL_EXPLANATIONS_DIR)


def clear_processed_csv_rows(path: Path) -> None:
    if not path.exists():
        return

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        if header:
            writer.writerow(header)


def archive_processed_csv(path: Path, batch_stamp: str) -> Optional[Path]:
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    if not rows:
        return None

    header, *data_rows = rows
    if not data_rows:
        return None

    ensure_directory(ARCHIVE_DIR)
    archive_name = f"{path.stem}_{batch_stamp}{path.suffix}"
    archive_path = ARCHIVE_DIR / archive_name

    with archive_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(data_rows)

    return archive_path


def archive_processed_input_data() -> List[Path]:
    batch_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    archived_paths: List[Path] = []

    for path in (
        EVENTS_FILE,
        TICKETS_FILE,
        ASSETS_FILE,
        FIELD_REPORTS_FILE,
        MARKINGS_FILE,
        POSITIVE_RESPONSES_FILE,
    ):
        archived_path = archive_processed_csv(path, batch_stamp)
        if archived_path is not None:
            archived_paths.append(archived_path)

    return archived_paths


def clear_processed_input_data() -> None:
    clear_processed_csv_rows(EVENTS_FILE)
    clear_processed_csv_rows(TICKETS_FILE)
    clear_processed_csv_rows(ASSETS_FILE)
    clear_processed_csv_rows(FIELD_REPORTS_FILE)
    clear_processed_csv_rows(MARKINGS_FILE)
    clear_processed_csv_rows(POSITIVE_RESPONSES_FILE)


def read_json_if_exists(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_case_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def first_nonempty_text(values: Any) -> str:
    if not isinstance(values, (list, tuple)):
        return ""
    for value in values:
        text = normalize_case_text(value)
        if text:
            return text
    return ""


def compute_case_trend_keys_from_plain(case_data: Dict[str, Any]) -> List[str]:
    metadata = dict(case_data.get("metadata") or {})
    identity = dict(case_data.get("identity") or {})
    lat = metadata.get("recent_centroid_lat", identity.get("anchor_lat"))
    lon = metadata.get("recent_centroid_lon", identity.get("anchor_lon"))

    def normalize_coord(value: Any) -> str:
        try:
            return f"{float(value):.4f}"
        except (TypeError, ValueError):
            return "na"

    asset_ids = sorted(str(x) for x in (case_data.get("asset_ids") or metadata.get("thread_hint_asset_ids") or []) if x)
    ticket_ids = sorted(str(x) for x in (case_data.get("ticket_ids") or metadata.get("thread_hint_ticket_ids") or []) if x)
    dominant_work_type = normalize_case_text(
        metadata.get("dominant_work_type")
        or first_nonempty_text(metadata.get("observed_work_types"))
    )
    dominant_contractor = normalize_case_text(
        metadata.get("dominant_contractor")
        or first_nonempty_text(metadata.get("observed_contractors"))
    )

    exact_key = "|".join(
        [
            f"lat:{normalize_coord(lat)}",
            f"lon:{normalize_coord(lon)}",
            f"assets:{','.join(asset_ids[:2]) or 'none'}",
            f"tickets:{','.join(ticket_ids[:2]) or 'none'}",
            f"work:{dominant_work_type or 'unknown'}",
            f"contractor:{dominant_contractor or 'unknown'}",
        ]
    )
    identity_key = "|".join(
        [
            f"assets:{','.join(asset_ids[:2]) or 'none'}",
            f"tickets:{','.join(ticket_ids[:2]) or 'none'}",
            f"work:{dominant_work_type or 'unknown'}",
            f"contractor:{dominant_contractor or 'unknown'}",
        ]
    )
    loose_key = "|".join(
        [
            f"lat:{normalize_coord(lat)}",
            f"lon:{normalize_coord(lon)}",
            f"assets:{','.join(asset_ids[:1]) or 'none'}",
        ]
    )
    keys = [exact_key]
    if asset_ids or ticket_ids:
        keys.append(identity_key)
    keys.append(loose_key)
    return keys


def compute_case_trend_key(case: CaseRecord) -> str:
    plain = dataclass_to_plain(case)
    keys = compute_case_trend_keys_from_plain(plain if isinstance(plain, dict) else {})
    return keys[0] if keys else ""


def load_prior_trend_history() -> Dict[str, Dict[str, Any]]:
    payload = read_json_if_exists(CASE_TREND_HISTORY_JSON) or {}
    cases = payload.get("cases", []) if isinstance(payload, dict) else []
    prior_index: Dict[str, Dict[str, Any]] = {}

    for raw_case in cases:
        if not isinstance(raw_case, dict):
            continue
        saved_keys = raw_case.get("trend_keys")
        candidate_keys = (
            [str(x).strip() for x in saved_keys if str(x).strip()]
            if isinstance(saved_keys, list)
            else []
        )
        if not candidate_keys:
            primary = str(raw_case.get("trend_key") or "").strip()
            candidate_keys = [primary] if primary else compute_case_trend_keys_from_plain(raw_case)

        for trend_key in candidate_keys:
            if trend_key:
                prior_index[trend_key] = raw_case

    return prior_index


def build_prior_case_index_for_cases(
    cases: Sequence[CaseRecord],
    prior_trend_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    prior_case_index: Dict[str, Dict[str, Any]] = {}

    for case in cases:
        trend_keys = compute_case_trend_keys_from_plain(dataclass_to_plain(case))
        trend_key = trend_keys[0] if trend_keys else ""
        case.metadata["trend_lookup_key"] = trend_key
        case.metadata["trend_lookup_keys"] = trend_keys
        prior_match = None
        for candidate_key in trend_keys:
            prior_match = prior_trend_index.get(candidate_key)
            if prior_match is not None:
                break
        if prior_match is not None:
            prior_case_index[case.case_id] = prior_match

    return prior_case_index


def dataclass_to_plain(value: Any) -> Any:
    """
    Convert nested dataclasses / enums / collections into JSON-safe plain values.
    """
    if is_dataclass(value):
        return {k: dataclass_to_plain(v) for k, v in asdict(value).items()}

    if hasattr(value, "value"):
        return getattr(value, "value")

    if isinstance(value, dict):
        return {str(k): dataclass_to_plain(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [dataclass_to_plain(v) for v in value]

    return value


# ============================================================
# LOAD + NORMALIZE
# ============================================================

def load_events(path: Path = EVENTS_FILE) -> List[EventRecord]:
    rows = read_csv_rows(path)
    events = normalize_event_records(rows)
    now = datetime.now(UTC)
    filtered: List[EventRecord] = []

    for event in events:
        event_dt = parse_datetime(event.event_time)
        if event_dt is None:
            filtered.append(event)
            continue

        future_delta_min = (event_dt - now).total_seconds() / 60.0
        if future_delta_min > MAX_EVENT_FUTURE_SKEW_MIN:
            print(
                f"[main.py] Skipping event {event.event_id} with future timestamp "
                f"{event.event_time} ({round(future_delta_min, 1)} min ahead of ingest time)."
            )
            continue

        filtered.append(event)

    return sorted(filtered, key=lambda e: (e.event_time, e.event_id))


def load_tickets(path: Path = TICKETS_FILE) -> List[TicketRecord]:
    rows = read_csv_rows(path)
    tickets = normalize_ticket_records(rows)
    return sorted(tickets, key=lambda t: (t.start_time, t.ticket_id))


def load_assets(path: Path = ASSETS_FILE) -> List[AssetRecord]:
    rows = read_csv_rows(path)
    assets = normalize_asset_records(rows)
    return sorted(assets, key=lambda a: a.asset_id)


def load_field_reports(path: Path = FIELD_REPORTS_FILE) -> List[FieldReportRecord]:
    rows = read_csv_rows(path)
    reports = normalize_field_report_records(rows)
    return sorted(reports, key=lambda r: (r.observed_at or "", r.report_id))


def load_markings(path: Path = MARKINGS_FILE) -> List[MarkingRecord]:
    rows = read_csv_rows(path)
    markings = normalize_marking_records(rows)
    return sorted(markings, key=lambda m: (m.observed_at or "", m.marking_id))


def load_positive_responses(path: Path = POSITIVE_RESPONSES_FILE) -> List[PositiveResponseRecord]:
    rows = read_csv_rows(path)
    responses = normalize_positive_response_records(rows)
    return sorted(responses, key=lambda r: (r.observed_at or "", r.response_id))


# ============================================================
# PRIOR STATE LOADING
# ============================================================

def load_prior_registry_payload(path: Path = CASE_REGISTRY_JSON) -> Optional[Dict[str, Any]]:
    payload = read_json_if_exists(path)
    if not isinstance(payload, dict):
        return None
    return payload


def build_prior_case_index(prior_registry_payload: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    if not prior_registry_payload:
        return {}

    cases = prior_registry_payload.get("cases", [])
    if not isinstance(cases, list):
        return {}

    index: Dict[str, Dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        if case_id:
            index[str(case_id)] = case

    return index


def build_prior_case_records(prior_registry_payload: Optional[Dict[str, Any]]) -> List[CaseRecord]:
    """
    Rehydrate prior saved cases into shallow CaseRecord objects.

    Nested fields such as identity / attachments / observations may still be plain
    dicts at this stage. That is acceptable because case.py owns normalization of
    seeded prior cases before registry matching begins.
    """
    if not prior_registry_payload:
        return []

    raw_cases = prior_registry_payload.get("cases", [])
    if not isinstance(raw_cases, list):
        return []

    prior_cases: List[CaseRecord] = []

    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            continue

        try:
            prior_case = CaseRecord(
                case_id=str(raw_case.get("case_id") or ""),
                created_at=str(raw_case.get("created_at") or ""),
                updated_at=str(raw_case.get("updated_at") or raw_case.get("created_at") or ""),
                status=str(raw_case.get("status") or "ACTIVE"),
                identity=raw_case.get("identity"),
                event_ids=list(raw_case.get("event_ids") or []),
                ticket_ids=list(raw_case.get("ticket_ids") or []),
                asset_ids=list(raw_case.get("asset_ids") or []),
                context_ticket_ids=list(raw_case.get("context_ticket_ids") or []),
                context_asset_ids=list(raw_case.get("context_asset_ids") or []),
                field_report_ids=list(raw_case.get("field_report_ids") or []),
                marking_ids=list(raw_case.get("marking_ids") or []),
                positive_response_ids=list(raw_case.get("positive_response_ids") or []),
                attachments=list(raw_case.get("attachments") or []),
                observations=list(raw_case.get("observations") or []),
                tags=list(raw_case.get("tags") or []),
                metadata=dict(raw_case.get("metadata") or {}),
            )
        except Exception:
            continue

        if not prior_case.case_id:
            continue

        prior_cases.append(prior_case)

    return prior_cases


# ============================================================
# PIPELINE
# ============================================================

def run_pipeline(
    events: Sequence[EventRecord],
    tickets: Sequence[TicketRecord],
    assets: Sequence[AssetRecord],
    field_reports: Sequence[FieldReportRecord] = (),
    markings: Sequence[MarkingRecord] = (),
    positive_responses: Sequence[PositiveResponseRecord] = (),
    prior_trend_index: Optional[Dict[str, Dict[str, Any]]] = None,
    prior_cases: Optional[Sequence[CaseRecord]] = None,
) -> tuple[List[CaseRecord], Dict[str, Dict[str, Any]]]:
    analyses = analyze_events(
        events=events,
        tickets=tickets,
        assets=assets,
    )

    registry = build_case_registry_from_analyses(
        analyses=analyses,
        events=events,
        prior_cases=prior_cases or [],
    )

    attach_context_records_to_registry(
        registry,
        field_reports=field_reports,
        markings=markings,
        positive_responses=positive_responses,
    )

    matched_prior_case_index = build_prior_case_index_for_cases(
        registry.cases,
        prior_trend_index or {},
    )

    evaluate_registry_in_place(
        registry,
        prior_case_index=matched_prior_case_index,
    )

    registry.cases.sort(
        key=lambda case: getattr(case, "updated_at", "") or "",
        reverse=True,
    )

    return registry.cases, matched_prior_case_index


# ============================================================
# OUTPUT BUILDERS
# ============================================================

def build_case_registry_payload(cases: Sequence[CaseRecord]) -> Dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "case_count": len(cases),
        "cases": [dataclass_to_plain(case) for case in cases],
    }


def build_case_trend_history_payload(cases: Sequence[CaseRecord]) -> Dict[str, Any]:
    history_cases: List[Dict[str, Any]] = []
    for case in cases:
        plain = dataclass_to_plain(case)
        if not isinstance(plain, dict):
            continue
        history_cases.append(
            {
                **plain,
                "trend_key": compute_case_trend_key(case),
                "trend_keys": compute_case_trend_keys_from_plain(plain),
            }
        )

    return {
        "generated_at": utc_now_iso(),
        "case_count": len(history_cases),
        "cases": history_cases,
    }


def build_summary_text(cases: Sequence[CaseRecord]) -> str:
    lines: List[str] = []
    lines.append("RISKSEER CASE SUMMARY")
    lines.append("=" * 80)
    lines.append(f"Generated at: {utc_now_iso()}")
    lines.append(f"Total cases: {len(cases)}")
    lines.append("")

    if not cases:
        lines.append("No cases generated.")
        return "\n".join(lines)

    for case in cases:
        lines.append(build_case_snapshot(case))
        lines.append("-" * 80)

    return "\n".join(lines)


def write_case_explanations(cases: Sequence[CaseRecord]) -> None:
    ensure_directory(OPERATOR_EXPLANATIONS_DIR)
    ensure_directory(INTERNAL_EXPLANATIONS_DIR)

    for case in cases:
        operator_path = OPERATOR_EXPLANATIONS_DIR / f"case_{case.case_id}.txt"
        internal_path = INTERNAL_EXPLANATIONS_DIR / f"case_{case.case_id}.txt"

        write_text(operator_path, build_operator_explanation(case))
        write_text(internal_path, build_internal_explanation(case))


def write_outputs(cases: Sequence[CaseRecord]) -> None:
    ensure_directory(OUTPUT_DIR)

    report_rows = build_case_report_rows(cases)
    write_csv_rows(CASE_REPORT_FILE, report_rows)

    registry_payload = build_case_registry_payload(cases)
    write_json(CASE_REGISTRY_JSON, registry_payload)

    trend_history_payload = build_case_trend_history_payload(cases)
    write_json(CASE_TREND_HISTORY_JSON, trend_history_payload)

    audit_payload = build_audit_payload(cases)
    write_json(CASE_AUDIT_JSON, audit_payload)
    write_text(CASE_AUDIT_TXT, build_audit_text(audit_payload))

    summary_text = build_summary_text(cases)
    write_text(CASE_SUMMARY_TXT, summary_text)

    write_case_explanations(cases)


# ============================================================
# USER-FACING CONSOLE OUTPUT
# ============================================================

def print_run_summary(
    events: Sequence[EventRecord],
    tickets: Sequence[TicketRecord],
    assets: Sequence[AssetRecord],
    cases: Sequence[CaseRecord],
    field_reports: Sequence[FieldReportRecord] = (),
    markings: Sequence[MarkingRecord] = (),
    positive_responses: Sequence[PositiveResponseRecord] = (),
    prior_case_index: Optional[Dict[str, Dict[str, Any]]] = None,
    prior_cases: Optional[Sequence[CaseRecord]] = None,
    archived_inputs: Optional[Sequence[Path]] = None,
) -> None:
    print("\n" + "=" * 80)
    print("RISKSEER PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Events loaded:  {len(events)}")
    print(f"Tickets loaded: {len(tickets)}")
    print(f"Assets loaded:  {len(assets)}")
    print(f"Field reports:  {len(field_reports)}")
    print(f"Markings loaded:{len(markings)}")
    print(f"Responses loaded: {len(positive_responses)}")
    print(f"Cases built:    {len(cases)}")
    print(f"Prior cases loaded (index): {len(prior_case_index or {})}")
    print(f"Prior cases seeded into registry: {len(prior_cases or [])}")
    print("")
    print(f"Case report:            {CASE_REPORT_FILE}")
    print(f"Case registry JSON:     {CASE_REGISTRY_JSON}")
    print(f"Trend history JSON:     {CASE_TREND_HISTORY_JSON}")
    print(f"Contradiction audit:    {CASE_AUDIT_JSON}")
    print(f"Audit summary text:     {CASE_AUDIT_TXT}")
    print(f"Case summary text:      {CASE_SUMMARY_TXT}")
    print(f"Operator explanations:  {OPERATOR_EXPLANATIONS_DIR}")
    print(f"Internal explanations:  {INTERNAL_EXPLANATIONS_DIR}")
    if archived_inputs:
        print("Archived input batches:")
        for archived_path in archived_inputs:
            print(f"  - {archived_path}")
    print("=" * 80)

    if cases:
        print("\nTop case snapshots:\n")
        for case in cases[:5]:
            print(build_case_snapshot(case))
            print("-" * 80)


# ============================================================
# MAIN ENTRY
# ============================================================

def main() -> None:
    ensure_directory(DATA_DIR)
    ensure_directory(OUTPUT_DIR)
    prior_registry_payload = load_prior_registry_payload()
    prior_trend_index = load_prior_trend_history()
    prior_case_index: Dict[str, Dict[str, Any]] = build_prior_case_index(prior_registry_payload)
    prior_cases: List[CaseRecord] = build_prior_case_records(prior_registry_payload)

    reset_generated_outputs()

    events = load_events()
    tickets = load_tickets()
    assets = load_assets()
    field_reports = load_field_reports()
    markings = load_markings()
    positive_responses = load_positive_responses()

    cases, prior_case_index = run_pipeline(
        events=events,
        tickets=tickets,
        assets=assets,
        field_reports=field_reports,
        markings=markings,
        positive_responses=positive_responses,
        prior_trend_index=prior_trend_index,
        prior_cases=prior_cases,
    )

    write_outputs(cases)
    archived_inputs = archive_processed_input_data()
    clear_processed_input_data()
    print_run_summary(
        events=events,
        tickets=tickets,
        assets=assets,
        field_reports=field_reports,
        markings=markings,
        positive_responses=positive_responses,
        cases=cases,
        prior_case_index=prior_case_index,
        prior_cases=prior_cases,
        archived_inputs=archived_inputs,
    )


if __name__ == "__main__":
    main()
