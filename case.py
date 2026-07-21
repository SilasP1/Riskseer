"""
case.py

GOAL
----
This file owns case containers, registry behavior, identity/continuity
mechanics, and attachment decisions.

A case is a bounded operational situation assembled from available records.
This file groups conservatively, tolerates missing fields, and preserves
continuity without turning every nearby record into the same case.

WHAT THIS FILE DOES
-------------------
1. Creates and updates CaseRecord containers.
2. Preserves stable case identity anchors.
3. Evaluates whether a new analyzed event should:
   - attach to an existing case
   - weakly attach under degraded evidence
   - branch into a related child case
   - create a new unrelated case
4. Distinguishes identity references from contextual references.
5. Maintains newest-first case ordering.
6. Generates next case IDs.
7. Seeds a new registry from prior cases so evolving cases can persist
   across runs instead of being rebuilt from scratch every time.
8. Tracks ambiguity, missing-field effects, and attachment rationale.
9. Maintains case family / parent-child branching metadata.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not assign decision_state, urgency, or response posture.
2. It does not evaluate operational risk.
3. It does not produce operator-facing explanations.
4. It does not interpret human failure or behavioral meaning.
5. It does not require complete data to function.

GROUPING PHILOSOPHY
-------------------
Prefer:
- stable grouping
- explicit ambiguity
- continuity-first attachment
- identity preservation over convenience
- branching when related activity stops being the same case
- graceful degradation when fields are missing

Avoid:
- magical clustering
- behavior-heavy heuristics
- hidden assumptions from missing data
- casual identity drift
- immortal cases that absorb unrelated later activity
- collapsing all evidence into one opaque fit score

A case should stay open while the underlying operational situation still looks
meaningfully the same in space, time, and available context. When continuity
is present but identity begins to drift, prefer a related branch over forced
attachment.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from schemas import (
    AttachmentAssessment,
    CaseAttachment,
    CaseIdentity,
    CaseRecord,
    CaseRegistry,
    EventRecord,
    FieldReportRecord,
    MarkingRecord,
    Observation,
    ObservationType,
    PositiveResponseRecord,
)
from event_logic import EventAnalysis, parse_datetime


# ============================================================
# CASE LIFECYCLE PARAMETERS
# ============================================================

CASE_CONTINUITY_GAP_MIN = 240           # 4 hours
CASE_INACTIVITY_TIMEOUT_MIN = 1440      # 24 hours
CASE_REOPEN_AFTER_CLOSE_MIN = 3 * 1440  # 3 days
CASE_MAX_MATCH_AGE_MIN = 21 * 24 * 60   # 21 days


# ============================================================
# IDENTITY / CONTINUITY PARAMETERS
# ============================================================

RECENT_CASE_EVENT_COUNT = 8
MAX_PRIMARY_TICKET_IDS = 2
MAX_PRIMARY_ASSET_IDS = 2

# Spatial / temporal continuity bands
STRONG_SPATIAL_DISTANCE_M = 90.0
WEAK_SPATIAL_DISTANCE_M = 180.0
BRANCH_SPATIAL_DISTANCE_M = 320.0
UNRELATED_SPATIAL_DISTANCE_M = 500.0

STRONG_TEMPORAL_WINDOW_MIN = 24 * 60
WEAK_TEMPORAL_WINDOW_MIN = 7 * 24 * 60
BRANCH_TEMPORAL_WINDOW_MIN = 14 * 24 * 60
UNRELATED_TEMPORAL_WINDOW_MIN = 21 * 24 * 60

# Context guidance
IDENTITY_TICKET_MATCH_DISTANCE_M = 250.0
IDENTITY_ASSET_MATCH_DISTANCE_M = 220.0

# Hard drift checks
MAX_ANCHOR_DRIFT_DISTANCE_M = 280.0
MAX_CENTROID_DRIFT_DISTANCE_M = 260.0

# Metadata history caps
MAX_ATTACHMENT_HISTORY = 100
MAX_REJECTION_HISTORY = 100


# ============================================================
# BASIC HELPERS
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0

    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)

    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    ordered: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def sequence_overlap_count(values_a: Iterable[str], values_b: Iterable[str]) -> int:
    return len(set(v for v in values_a if v) & set(v for v in values_b if v))


def case_sort_key(case: CaseRecord) -> datetime:
    return parse_datetime(case.updated_at) or datetime.min.replace(tzinfo=UTC)


def next_case_id(registry: CaseRegistry) -> str:
    case_id = f"{registry.next_case_number:05d}"
    registry.next_case_number += 1
    return case_id


def minutes_between(dt1: Optional[datetime], dt2: Optional[datetime]) -> Optional[float]:
    if dt1 is None or dt2 is None:
        return None
    return abs((dt1 - dt2).total_seconds()) / 60.0


def signed_minutes_between(dt1: Optional[datetime], dt2: Optional[datetime]) -> Optional[float]:
    if dt1 is None or dt2 is None:
        return None
    return (dt2 - dt1).total_seconds() / 60.0


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def safe_round(value: Optional[float], ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except (TypeError, ValueError):
        return None


def extract_case_number(case_id: str) -> Optional[int]:
    try:
        return int(case_id)
    except (TypeError, ValueError):
        return None


def next_case_number_from_cases(cases: Sequence[CaseRecord]) -> int:
    max_seen = 0
    for case in cases:
        number = extract_case_number(case.case_id)
        if number is not None and number > max_seen:
            max_seen = number
    return max_seen + 1


def normalize_text(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text.lower() if text else None


def safe_getattr(obj: object, *names: str) -> object:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return None


# ============================================================
# OBSERVATION NORMALIZATION HELPERS
# ============================================================

def observation_field(obs: object, field: str, default: object = None) -> object:
    if isinstance(obs, dict):
        return obs.get(field, default)
    return getattr(obs, field, default)


def normalize_observation_key(
    obs: object,
) -> Tuple[
    str,
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    Optional[str],
    str,
]:
    observation_type = observation_field(obs, "observation_type")
    observation_type_value = getattr(observation_type, "value", observation_type)
    return (
        str(observation_type_value or ""),
        observation_field(obs, "event_id"),
        observation_field(obs, "ticket_id"),
        observation_field(obs, "asset_id"),
        observation_field(obs, "field_report_id"),
        observation_field(obs, "marking_id"),
        observation_field(obs, "response_id"),
        str(observation_field(obs, "summary", "") or ""),
    )


def coerce_observation(value: object) -> Optional[object]:
    if value is None:
        return None
    return value


# ============================================================
# METADATA HELPERS
# ============================================================

def ensure_case_metadata_defaults(case: CaseRecord) -> None:
    case.metadata = dict(case.metadata or {})

    defaults = {
        "family_id": case.case_id,
        "parent_case_id": None,
        "child_case_ids": [],
        "sibling_case_ids": [],
        "related_case_ids": [],
        "branch_reason": None,
        "branch_from_case_id": None,
        "branch_created_at": None,
        "attachment_history": [],
        "rejected_attachment_history": [],
        "ambiguity_flags": [],
        "dominant_contractor": None,
        "dominant_work_type": None,
        "observed_contractors": [],
        "observed_work_types": [],
        "identity_confidence": None,
        "spatial_spread_m": None,
        "recent_centroid_lat": None,
        "recent_centroid_lon": None,
        "continuity_gap_min": None,
        "longest_gap_min": None,
        "drifting_activity": False,
        "fork_suspected": False,
        "multiple_plausible_tickets": False,
        "mixed_contractors": False,
        "mixed_work_types": False,
        "degraded_identity": False,
        "missing_primary_fields": False,
        "weak_primary_continuity": False,
        "conflicting_primary_signals": False,
        "overreliance_on_secondary_signals": False,
        "multiple_candidate_cases": False,
        "last_grouping_match": None,
        "last_branch_decision": None,
        "case_family_role": "root",
    }

    for key, value in defaults.items():
        if key not in case.metadata:
            case.metadata[key] = deepcopy(value)


def set_case_family_root(case: CaseRecord) -> None:
    ensure_case_metadata_defaults(case)
    case.metadata["family_id"] = case.metadata.get("family_id") or case.case_id
    case.metadata["case_family_role"] = "root" if not case.metadata.get("parent_case_id") else "child"


def register_case_relation(case: CaseRecord, other_case_id: str, bucket: str) -> None:
    ensure_case_metadata_defaults(case)
    values = unique_preserve_order(list(case.metadata.get(bucket, []) or []) + [other_case_id])
    case.metadata[bucket] = values


def append_case_history(case: CaseRecord, bucket: str, entry: Dict[str, object], cap: int) -> None:
    ensure_case_metadata_defaults(case)
    history = list(case.metadata.get(bucket, []) or [])
    history.append(entry)
    if len(history) > cap:
        history = history[-cap:]
    case.metadata[bucket] = history


def add_ambiguity_flags(case: CaseRecord, flags: Iterable[str]) -> None:
    ensure_case_metadata_defaults(case)
    existing = list(case.metadata.get("ambiguity_flags", []) or [])
    case.metadata["ambiguity_flags"] = unique_preserve_order([*existing, *list(flags)])


def remove_ambiguity_flags(case: CaseRecord, flags: Iterable[str]) -> None:
    ensure_case_metadata_defaults(case)
    remove_set = set(flags)
    current = list(case.metadata.get("ambiguity_flags", []) or [])
    case.metadata["ambiguity_flags"] = [flag for flag in current if flag not in remove_set]


# ============================================================
# ATTACHMENT / OBSERVATION HELPERS
# ============================================================

def build_attachment_assessment(
    *,
    allowed: bool,
    reason: str,
    spatial_fit: Optional[float] = None,
    temporal_fit: Optional[float] = None,
    ticket_fit: Optional[float] = None,
    asset_fit: Optional[float] = None,
    identity_consistent: Optional[bool] = None,
    context_only: Optional[bool] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> AttachmentAssessment:
    return AttachmentAssessment(
        allowed=allowed,
        reason=reason,
        spatial_fit=safe_round(spatial_fit),
        temporal_fit=safe_round(temporal_fit),
        ticket_fit=safe_round(ticket_fit),
        asset_fit=safe_round(asset_fit),
        identity_consistent=identity_consistent,
        context_only=context_only,
        confidence=safe_round(confidence),
        metadata=metadata or {},
    )


def build_case_attachment(
    record_type: str,
    record_id: str,
    role: Optional[str] = None,
    assessment: Optional[AttachmentAssessment] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> CaseAttachment:
    return CaseAttachment(
        record_type=record_type,
        record_id=record_id,
        role=role,
        attached_at=utc_now_iso(),
        assessment=assessment,
        metadata=metadata or {},
    )


def append_attachment_if_missing(case: CaseRecord, attachment: CaseAttachment) -> None:
    for existing in case.attachments:
        if (
            existing.record_type == attachment.record_type
            and existing.record_id == attachment.record_id
            and existing.role == attachment.role
        ):
            if existing.assessment is None and attachment.assessment is not None:
                existing.assessment = attachment.assessment
            if attachment.metadata:
                existing.metadata.update(attachment.metadata)
            return
    case.attachments.append(attachment)


def append_observations_if_missing(case: CaseRecord, observations: Sequence[Observation]) -> None:
    existing_keys = {normalize_observation_key(obs) for obs in case.observations}
    for obs in observations:
        key = normalize_observation_key(obs)
        if key not in existing_keys:
            case.observations.append(obs)
            existing_keys.add(key)


def dedupe_case_attachments(case: CaseRecord) -> None:
    seen: Set[Tuple[str, str, Optional[str]]] = set()
    deduped: List[CaseAttachment] = []

    for attachment in case.attachments:
        key = (attachment.record_type, attachment.record_id, attachment.role)
        if key not in seen:
            deduped.append(attachment)
            seen.add(key)

    case.attachments = deduped


def dedupe_case_observations(case: CaseRecord) -> None:
    seen: Set[
        Tuple[
            str,
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
            Optional[str],
            str,
        ]
    ] = set()
    deduped: List[Observation] = []

    for obs in case.observations:
        key = normalize_observation_key(obs)
        if key not in seen:
            deduped.append(obs)
            seen.add(key)

    case.observations = deduped


# ============================================================
# CASE GEOMETRY / TIME HELPERS
# ============================================================

def get_case_events(case: CaseRecord, event_index: Dict[str, EventRecord]) -> List[EventRecord]:
    events: List[EventRecord] = []
    for event_id in case.event_ids:
        event = event_index.get(event_id)
        if event is not None:
            events.append(event)

    events.sort(key=lambda e: parse_datetime(e.event_time) or datetime.min.replace(tzinfo=UTC))
    return events


def get_recent_case_events(
    case: CaseRecord,
    event_index: Dict[str, EventRecord],
    count: int = RECENT_CASE_EVENT_COUNT,
) -> List[EventRecord]:
    events = get_case_events(case, event_index)
    if count <= 0:
        return []
    return events[-count:]


def get_latest_case_event_time(case: CaseRecord, event_index: Dict[str, EventRecord]) -> Optional[datetime]:
    latest: Optional[datetime] = None
    for event in get_case_events(case, event_index):
        dt = parse_datetime(event.event_time)
        if dt is None:
            continue
        if latest is None or dt > latest:
            latest = dt
    if latest is not None:
        return latest
    return parse_datetime((case.metadata or {}).get("latest_event_time"))


def get_earliest_case_event_time(case: CaseRecord, event_index: Dict[str, EventRecord]) -> Optional[datetime]:
    earliest: Optional[datetime] = None
    for event in get_case_events(case, event_index):
        dt = parse_datetime(event.event_time)
        if dt is None:
            continue
        if earliest is None or dt < earliest:
            earliest = dt
    if earliest is not None:
        return earliest
    return parse_datetime((case.metadata or {}).get("earliest_event_time"))


def get_case_centroid(case: CaseRecord, event_index: Dict[str, EventRecord]) -> Optional[Tuple[float, float]]:
    coords: List[Tuple[float, float]] = []
    for event in get_case_events(case, event_index):
        if event.lat is None or event.lon is None:
            continue
        coords.append((event.lat, event.lon))

    if not coords:
        if case.identity.anchor_lat is not None and case.identity.anchor_lon is not None:
            return case.identity.anchor_lat, case.identity.anchor_lon
        return None

    avg_lat = sum(lat for lat, _ in coords) / len(coords)
    avg_lon = sum(lon for _, lon in coords) / len(coords)
    return avg_lat, avg_lon


def nearest_case_event_distance_m(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Optional[float]:
    if analysis.event.lat is None or analysis.event.lon is None:
        return None

    distances: List[float] = []
    for event in get_case_events(case, event_index):
        if event.lat is None or event.lon is None:
            continue
        distances.append(haversine_m(event.lat, event.lon, analysis.event.lat, analysis.event.lon))
    return min(distances) if distances else None


def recent_case_event_distance_m(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Optional[float]:
    if analysis.event.lat is None or analysis.event.lon is None:
        return None

    distances: List[float] = []
    for event in get_recent_case_events(case, event_index):
        if event.lat is None or event.lon is None:
            continue
        distances.append(haversine_m(event.lat, event.lon, analysis.event.lat, analysis.event.lon))
    return min(distances) if distances else None


def recent_case_event_time_delta_min(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Optional[float]:
    incoming_dt = parse_datetime(analysis.event.event_time)
    deltas: List[float] = []

    for event in get_recent_case_events(case, event_index):
        event_dt = parse_datetime(event.event_time)
        delta = minutes_between(event_dt, incoming_dt)
        if delta is not None:
            deltas.append(delta)

    return min(deltas) if deltas else None


def get_case_anchor_distance_m(case: CaseRecord, analysis: EventAnalysis) -> Optional[float]:
    if analysis.event.lat is None or analysis.event.lon is None:
        return None
    anchor_lat = case.identity.anchor_lat
    anchor_lon = case.identity.anchor_lon
    if anchor_lat is None or anchor_lon is None:
        return None
    return haversine_m(anchor_lat, anchor_lon, analysis.event.lat, analysis.event.lon)


def get_case_anchor_time_delta_min(case: CaseRecord, analysis: EventAnalysis) -> Optional[float]:
    anchor_dt = parse_datetime(case.identity.anchor_time)
    incoming_dt = parse_datetime(analysis.event.event_time)
    return minutes_between(anchor_dt, incoming_dt)


def get_case_centroid_distance_to_analysis_m(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Optional[float]:
    if analysis.event.lat is None or analysis.event.lon is None:
        return None
    centroid = get_case_centroid(case, event_index)
    if centroid is None:
        return None
    return haversine_m(centroid[0], centroid[1], analysis.event.lat, analysis.event.lon)


def compute_case_spatial_spread_m(case: CaseRecord, event_index: Dict[str, EventRecord]) -> Optional[float]:
    centroid = get_case_centroid(case, event_index)
    if centroid is None:
        return None

    distances: List[float] = []
    for event in get_case_events(case, event_index):
        if event.lat is None or event.lon is None:
            continue
        distances.append(haversine_m(centroid[0], centroid[1], event.lat, event.lon))

    return max(distances) if distances else None


def compute_longest_case_gap_min(case: CaseRecord, event_index: Dict[str, EventRecord]) -> Optional[float]:
    event_times = [
        parse_datetime(event.event_time)
        for event in get_case_events(case, event_index)
    ]
    event_times = [dt for dt in event_times if dt is not None]
    if len(event_times) < 2:
        return None

    longest = 0.0
    for i in range(1, len(event_times)):
        gap = minutes_between(event_times[i - 1], event_times[i])
        if gap is not None and gap > longest:
            longest = gap
    return longest


# ============================================================
# FIELD EXTRACTION HELPERS
# ============================================================

def get_event_contractor(event: EventRecord) -> Optional[str]:
    from_attr = normalize_text(
        safe_getattr(event, "contractor", "contractor_name", "excavator", "company", "responsible_party")
    )
    if from_attr:
        return from_attr
    metadata = getattr(event, "metadata", {}) or {}
    if isinstance(metadata, dict):
        return normalize_text(
            metadata.get("contractor")
            or metadata.get("contractor_name")
            or metadata.get("excavator")
            or metadata.get("company")
            or metadata.get("responsible_party")
        )
    return None


def get_event_work_type(event: EventRecord) -> Optional[str]:
    from_attr = normalize_text(
        safe_getattr(event, "work_type", "job_type", "activity_type", "operation_type", "activity")
    )
    if from_attr:
        return from_attr
    metadata = getattr(event, "metadata", {}) or {}
    if isinstance(metadata, dict):
        return normalize_text(
            metadata.get("work_type")
            or metadata.get("job_type")
            or metadata.get("activity_type")
            or metadata.get("operation_type")
            or metadata.get("activity")
        )
    return None


def get_analysis_contractor(analysis: EventAnalysis) -> Optional[str]:
    from_event = get_event_contractor(analysis.event)
    if from_event:
        return from_event
    return normalize_text(
        safe_getattr(analysis, "contractor", "contractor_name", "excavator", "company")
    )


def get_analysis_work_type(analysis: EventAnalysis) -> Optional[str]:
    from_event = get_event_work_type(analysis.event)
    if from_event:
        return from_event
    return normalize_text(
        safe_getattr(analysis, "work_type", "job_type", "activity_type", "operation_type")
    )


def record_presence_map_from_analysis(analysis: EventAnalysis) -> Dict[str, bool]:
    return {
        "event_id": bool(getattr(analysis.event, "event_id", None)),
        "event_time": bool(getattr(analysis.event, "event_time", None)),
        "lat": getattr(analysis.event, "lat", None) is not None,
        "lon": getattr(analysis.event, "lon", None) is not None,
        "candidate_ticket_ids": bool(list(getattr(analysis, "candidate_ticket_ids", []) or [])),
        "candidate_asset_ids": bool(list(getattr(analysis, "candidate_asset_ids", []) or [])),
        "contractor": bool(get_analysis_contractor(analysis)),
        "work_type": bool(get_analysis_work_type(analysis)),
    }


# ============================================================
# CASE IDENTITY HELPERS
# ============================================================

def get_primary_ticket_ids(case: CaseRecord) -> List[str]:
    return unique_preserve_order(case.identity.primary_ticket_ids)


def get_primary_asset_ids(case: CaseRecord) -> List[str]:
    return unique_preserve_order(case.identity.primary_asset_ids)


def get_all_case_ticket_ids(case: CaseRecord) -> List[str]:
    return unique_preserve_order(
        [
            *case.ticket_ids,
            *case.context_ticket_ids,
            *case.identity.primary_ticket_ids,
        ]
    )


def get_all_case_asset_ids(case: CaseRecord) -> List[str]:
    return unique_preserve_order(
        [
            *case.asset_ids,
            *case.context_asset_ids,
            *case.identity.primary_asset_ids,
        ]
    )


def identity_ticket_overlap(case: CaseRecord, analysis: EventAnalysis) -> Set[str]:
    return set(get_primary_ticket_ids(case)).intersection(set(analysis.candidate_ticket_ids))


def identity_asset_overlap(case: CaseRecord, analysis: EventAnalysis) -> Set[str]:
    return set(get_primary_asset_ids(case)).intersection(set(analysis.candidate_asset_ids))


def contextual_ticket_overlap(case: CaseRecord, analysis: EventAnalysis) -> Set[str]:
    return set(get_all_case_ticket_ids(case)).intersection(set(analysis.candidate_ticket_ids))


def contextual_asset_overlap(case: CaseRecord, analysis: EventAnalysis) -> Set[str]:
    return set(get_all_case_asset_ids(case)).intersection(set(analysis.candidate_asset_ids))


def build_case_identity_from_analysis(analysis: EventAnalysis) -> CaseIdentity:
    primary_ticket_ids = unique_preserve_order(analysis.candidate_ticket_ids)[:MAX_PRIMARY_TICKET_IDS]
    primary_asset_ids = unique_preserve_order(analysis.candidate_asset_ids)[:MAX_PRIMARY_ASSET_IDS]

    summary_parts: List[str] = [f"anchored_to_event:{analysis.event.event_id}"]
    if primary_ticket_ids:
        summary_parts.append(f"primary_tickets:{','.join(primary_ticket_ids)}")
    if primary_asset_ids:
        summary_parts.append(f"primary_assets:{','.join(primary_asset_ids)}")

    confidence = 0.45
    if primary_ticket_ids and primary_asset_ids:
        confidence = 0.82
    elif primary_ticket_ids or primary_asset_ids:
        confidence = 0.67
    elif getattr(analysis.event, "lat", None) is not None and getattr(analysis.event, "lon", None) is not None:
        confidence = 0.52

    return CaseIdentity(
        anchor_event_id=analysis.event.event_id,
        anchor_time=analysis.event.event_time,
        anchor_lat=getattr(analysis.event, "lat", None),
        anchor_lon=getattr(analysis.event, "lon", None),
        primary_ticket_ids=primary_ticket_ids,
        primary_asset_ids=primary_asset_ids,
        identity_confidence=confidence,
        summary=" | ".join(summary_parts),
    )


def maybe_fill_identity_from_case_state(case: CaseRecord) -> None:
    """
    Fill empty identity slots conservatively.
    Do not aggressively overwrite established primary identity.
    """
    current_primary_tickets = unique_preserve_order(case.identity.primary_ticket_ids)
    current_primary_assets = unique_preserve_order(case.identity.primary_asset_ids)

    if len(current_primary_tickets) < MAX_PRIMARY_TICKET_IDS:
        for ticket_id in unique_preserve_order(case.ticket_ids):
            if ticket_id not in current_primary_tickets:
                current_primary_tickets.append(ticket_id)
            if len(current_primary_tickets) >= MAX_PRIMARY_TICKET_IDS:
                break

    if len(current_primary_assets) < MAX_PRIMARY_ASSET_IDS:
        for asset_id in unique_preserve_order(case.asset_ids):
            if asset_id not in current_primary_assets:
                current_primary_assets.append(asset_id)
            if len(current_primary_assets) >= MAX_PRIMARY_ASSET_IDS:
                break

    case.identity.primary_ticket_ids = current_primary_tickets[:MAX_PRIMARY_TICKET_IDS]
    case.identity.primary_asset_ids = current_primary_assets[:MAX_PRIMARY_ASSET_IDS]

    summary_parts = []
    if case.identity.anchor_event_id:
        summary_parts.append(f"anchored_to_event:{case.identity.anchor_event_id}")
    if case.identity.primary_ticket_ids:
        summary_parts.append(f"primary_tickets:{','.join(case.identity.primary_ticket_ids)}")
    if case.identity.primary_asset_ids:
        summary_parts.append(f"primary_assets:{','.join(case.identity.primary_asset_ids)}")
    case.identity.summary = " | ".join(summary_parts)


# ============================================================
# REHYDRATION / NORMALIZATION HELPERS
# ============================================================

def coerce_attachment_assessment(value: object) -> Optional[AttachmentAssessment]:
    if value is None:
        return None
    if isinstance(value, AttachmentAssessment):
        return value
    if isinstance(value, dict):
        return AttachmentAssessment(
            allowed=bool(value.get("allowed", False)),
            reason=str(value.get("reason", "")),
            spatial_fit=safe_round(value.get("spatial_fit")) if value.get("spatial_fit") is not None else None,
            temporal_fit=safe_round(value.get("temporal_fit")) if value.get("temporal_fit") is not None else None,
            ticket_fit=safe_round(value.get("ticket_fit")) if value.get("ticket_fit") is not None else None,
            asset_fit=safe_round(value.get("asset_fit")) if value.get("asset_fit") is not None else None,
            identity_consistent=value.get("identity_consistent"),
            context_only=value.get("context_only"),
            confidence=safe_round(value.get("confidence")) if value.get("confidence") is not None else None,
            metadata=dict(value.get("metadata") or {}),
        )
    return None


def coerce_case_attachment(value: object) -> Optional[CaseAttachment]:
    if value is None:
        return None
    if isinstance(value, CaseAttachment):
        return value
    if isinstance(value, dict):
        return CaseAttachment(
            record_type=str(value.get("record_type", "")),
            record_id=str(value.get("record_id", "")),
            role=value.get("role"),
            attached_at=str(value.get("attached_at") or utc_now_iso()),
            assessment=coerce_attachment_assessment(value.get("assessment")),
            metadata=dict(value.get("metadata") or {}),
        )
    return None


def coerce_case_identity(value: object) -> CaseIdentity:
    if isinstance(value, CaseIdentity):
        return value

    if isinstance(value, dict):
        return CaseIdentity(
            anchor_event_id=value.get("anchor_event_id"),
            anchor_time=value.get("anchor_time"),
            anchor_lat=value.get("anchor_lat"),
            anchor_lon=value.get("anchor_lon"),
            primary_ticket_ids=unique_preserve_order(value.get("primary_ticket_ids") or [])[:MAX_PRIMARY_TICKET_IDS],
            primary_asset_ids=unique_preserve_order(value.get("primary_asset_ids") or [])[:MAX_PRIMARY_ASSET_IDS],
            identity_confidence=float(value.get("identity_confidence", 0.0) or 0.0),
            summary=str(value.get("summary") or ""),
        )

    return CaseIdentity()


def case_status_normalized(case: CaseRecord) -> str:
    status = (case.status or "").upper().strip()
    if status in {"ACTIVE", "INACTIVE", "CLOSED"}:
        return status
    if status == "OPEN":
        return "ACTIVE"
    return "ACTIVE"


def normalize_case_record(case: CaseRecord) -> CaseRecord:
    case.identity = coerce_case_identity(case.identity)

    normalized_attachments: List[CaseAttachment] = []
    for attachment in list(case.attachments or []):
        coerced = coerce_case_attachment(attachment)
        if coerced is not None:
            normalized_attachments.append(coerced)
    case.attachments = normalized_attachments

    normalized_observations: List[object] = []
    for obs in list(case.observations or []):
        coerced = coerce_observation(obs)
        if coerced is not None:
            normalized_observations.append(coerced)
    case.observations = normalized_observations

    case.event_ids = unique_preserve_order(list(case.event_ids or []))
    case.ticket_ids = unique_preserve_order(list(case.ticket_ids or []))
    case.asset_ids = unique_preserve_order(list(case.asset_ids or []))
    case.context_ticket_ids = unique_preserve_order(list(case.context_ticket_ids or []))
    case.context_asset_ids = unique_preserve_order(list(case.context_asset_ids or []))
    case.field_report_ids = unique_preserve_order(list(case.field_report_ids or []))
    case.marking_ids = unique_preserve_order(list(case.marking_ids or []))
    case.positive_response_ids = unique_preserve_order(list(case.positive_response_ids or []))
    case.tags = unique_preserve_order(list(case.tags or []))
    case.metadata = dict(case.metadata or {})

    if not case.created_at:
        case.created_at = utc_now_iso()
    if not case.updated_at:
        case.updated_at = case.created_at

    case.status = case_status_normalized(case)
    ensure_case_metadata_defaults(case)
    set_case_family_root(case)
    maybe_fill_identity_from_case_state(case)
    return case


# ============================================================
# CASE STATUS / LIFECYCLE / REOPEN
# ============================================================

def case_is_active(case: CaseRecord) -> bool:
    return case_status_normalized(case) == "ACTIVE"


def case_is_inactive(case: CaseRecord) -> bool:
    return case_status_normalized(case) == "INACTIVE"


def case_is_closed(case: CaseRecord) -> bool:
    return case_status_normalized(case) == "CLOSED"


def update_case_lifecycle_status(
    case: CaseRecord,
    reference_time: Optional[datetime],
    event_index: Dict[str, EventRecord],
) -> None:
    if reference_time is None:
        return

    latest_case_time = get_latest_case_event_time(case, event_index)
    if latest_case_time is None:
        return

    gap_min = signed_minutes_between(latest_case_time, reference_time)
    if gap_min is None or gap_min < 0:
        return

    prior_status = case_status_normalized(case)

    if gap_min <= CASE_CONTINUITY_GAP_MIN:
        new_status = "ACTIVE"
    elif gap_min <= CASE_INACTIVITY_TIMEOUT_MIN:
        new_status = "INACTIVE"
    else:
        new_status = "CLOSED"

    case.status = new_status
    case.metadata["continuity_gap_min"] = safe_round(gap_min, 2)

    if prior_status != new_status:
        case.metadata["last_status_transition"] = {
            "from": prior_status,
            "to": new_status,
            "at": utc_now_iso(),
            "gap_min": safe_round(gap_min, 2),
        }
        if new_status == "CLOSED":
            case.metadata["closed_at"] = utc_now_iso()
            case.metadata["closure_reason"] = (
                f"inactive_for_more_than_{int(CASE_INACTIVITY_TIMEOUT_MIN)}_minutes"
            )
            case.metadata.pop("reopened_at", None)
            case.metadata.pop("reopen_event_id", None)
            case.metadata.pop("reopen_gap_min", None)
        else:
            case.metadata.pop("closed_at", None)
            case.metadata.pop("closure_reason", None)


def maybe_reopen_case_for_continuity(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> bool:
    if not case_is_closed(case):
        return False

    latest_case_time = get_latest_case_event_time(case, event_index)
    incoming_dt = parse_datetime(analysis.event.event_time)
    delta = signed_minutes_between(latest_case_time, incoming_dt)

    if delta is None or delta < 0:
        return False
    if delta > CASE_REOPEN_AFTER_CLOSE_MIN:
        return False

    prior_status = case_status_normalized(case)
    case.status = "ACTIVE"
    case.metadata["last_status_transition"] = {
        "from": prior_status,
        "to": "ACTIVE",
        "at": utc_now_iso(),
        "gap_min": safe_round(delta, 2),
    }
    case.metadata["reopened_at"] = utc_now_iso()
    case.metadata["reopen_event_id"] = analysis.event.event_id
    case.metadata["reopen_gap_min"] = safe_round(delta, 2)
    case.metadata.pop("closed_at", None)
    case.metadata.pop("closure_reason", None)
    return True


def case_is_open_for_assignment(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> bool:
    incoming_dt = parse_datetime(analysis.event.event_time)
    if incoming_dt is None:
        return False

    update_case_lifecycle_status(case, incoming_dt, event_index)

    latest_case_time = get_latest_case_event_time(case, event_index)
    age_min = signed_minutes_between(latest_case_time, incoming_dt)
    if age_min is None or age_min < 0:
        return False
    if age_min > CASE_MAX_MATCH_AGE_MIN:
        return False

    if case_is_active(case) or case_is_inactive(case):
        return True

    if case_is_closed(case):
        return maybe_reopen_case_for_continuity(case, analysis, event_index)

    return False


# ============================================================
# EVIDENCE DIMENSION HELPERS
# ============================================================

def dimension_result(kind: str, detail: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    return {"kind": kind, "detail": detail or {}}


def spatial_dimension(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Dict[str, object]:
    distances = [
        recent_case_event_distance_m(case, analysis, event_index),
        nearest_case_event_distance_m(case, analysis, event_index),
        get_case_anchor_distance_m(case, analysis),
        get_case_centroid_distance_to_analysis_m(case, analysis, event_index),
    ]
    distances = [d for d in distances if d is not None]

    if not distances:
        return dimension_result("unavailable", {"reason": "no_comparable_coordinates"})

    effective = min(distances)

    if effective <= STRONG_SPATIAL_DISTANCE_M:
        return dimension_result("supportive", {"distance_m": safe_round(effective, 2)})
    if effective <= WEAK_SPATIAL_DISTANCE_M:
        return dimension_result("weak_support", {"distance_m": safe_round(effective, 2)})
    if effective <= BRANCH_SPATIAL_DISTANCE_M:
        return dimension_result("branching_tension", {"distance_m": safe_round(effective, 2)})
    if effective <= UNRELATED_SPATIAL_DISTANCE_M:
        return dimension_result("contradictory", {"distance_m": safe_round(effective, 2)})
    return dimension_result("strong_contradiction", {"distance_m": safe_round(effective, 2)})


def temporal_dimension(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Dict[str, object]:
    deltas = [
        recent_case_event_time_delta_min(case, analysis, event_index),
        get_case_anchor_time_delta_min(case, analysis),
    ]
    deltas = [d for d in deltas if d is not None]

    if not deltas:
        return dimension_result("unavailable", {"reason": "no_comparable_time"})

    effective = min(deltas)

    if effective <= STRONG_TEMPORAL_WINDOW_MIN:
        return dimension_result("supportive", {"time_delta_min": safe_round(effective, 2)})
    if effective <= WEAK_TEMPORAL_WINDOW_MIN:
        return dimension_result("weak_support", {"time_delta_min": safe_round(effective, 2)})
    if effective <= BRANCH_TEMPORAL_WINDOW_MIN:
        return dimension_result("branching_tension", {"time_delta_min": safe_round(effective, 2)})
    if effective <= UNRELATED_TEMPORAL_WINDOW_MIN:
        return dimension_result("contradictory", {"time_delta_min": safe_round(effective, 2)})
    return dimension_result("strong_contradiction", {"time_delta_min": safe_round(effective, 2)})


def ticket_dimension(case: CaseRecord, analysis: EventAnalysis) -> Dict[str, object]:
    shared_primary = sorted(identity_ticket_overlap(case, analysis))
    shared_context = sorted(contextual_ticket_overlap(case, analysis))
    incoming = unique_preserve_order(analysis.candidate_ticket_ids)

    if not incoming:
        return dimension_result("unavailable", {"reason": "no_ticket_context"})
    if shared_primary:
        return dimension_result("supportive", {"shared_primary_ticket_ids": shared_primary})
    if shared_context:
        return dimension_result("ambiguous", {"shared_context_ticket_ids": shared_context})

    existing = get_all_case_ticket_ids(case)
    if existing:
        return dimension_result(
            "contradictory",
            {
                "incoming_ticket_ids": incoming,
                "existing_case_ticket_ids": existing,
            },
        )

    return dimension_result("unavailable", {"reason": "case_has_no_ticket_context"})


def asset_dimension(case: CaseRecord, analysis: EventAnalysis) -> Dict[str, object]:
    shared_primary = sorted(identity_asset_overlap(case, analysis))
    shared_context = sorted(contextual_asset_overlap(case, analysis))
    incoming = unique_preserve_order(analysis.candidate_asset_ids)

    if not incoming:
        return dimension_result("unavailable", {"reason": "no_asset_context"})
    if shared_primary:
        return dimension_result("supportive", {"shared_primary_asset_ids": shared_primary})
    if shared_context:
        return dimension_result("ambiguous", {"shared_context_asset_ids": shared_context})

    existing = get_all_case_asset_ids(case)
    if existing:
        return dimension_result(
            "contradictory",
            {
                "incoming_asset_ids": incoming,
                "existing_case_asset_ids": existing,
            },
        )

    return dimension_result("unavailable", {"reason": "case_has_no_asset_context"})


def contractor_dimension(case: CaseRecord, analysis: EventAnalysis) -> Dict[str, object]:
    incoming = get_analysis_contractor(analysis)
    dominant = normalize_text(case.metadata.get("dominant_contractor"))
    observed = [normalize_text(v) for v in list(case.metadata.get("observed_contractors", []) or [])]
    observed = [v for v in observed if v]

    if not incoming:
        return dimension_result("unavailable", {"reason": "no_contractor"})
    if dominant and incoming == dominant:
        return dimension_result("supportive", {"contractor": incoming, "dominant_contractor": dominant})
    if incoming in observed:
        return dimension_result("ambiguous", {"contractor": incoming, "observed_contractors": observed})
    if dominant:
        return dimension_result("contradictory", {"contractor": incoming, "dominant_contractor": dominant})
    if observed:
        return dimension_result("ambiguous", {"contractor": incoming, "observed_contractors": observed})
    return dimension_result("unavailable", {"reason": "case_has_no_contractor_history"})


def work_type_dimension(case: CaseRecord, analysis: EventAnalysis) -> Dict[str, object]:
    incoming = get_analysis_work_type(analysis)
    dominant = normalize_text(case.metadata.get("dominant_work_type"))
    observed = [normalize_text(v) for v in list(case.metadata.get("observed_work_types", []) or [])]
    observed = [v for v in observed if v]

    if not incoming:
        return dimension_result("unavailable", {"reason": "no_work_type"})
    if dominant and incoming == dominant:
        return dimension_result("supportive", {"work_type": incoming, "dominant_work_type": dominant})
    if incoming in observed:
        return dimension_result("ambiguous", {"work_type": incoming, "observed_work_types": observed})
    if dominant:
        return dimension_result("contradictory", {"work_type": incoming, "dominant_work_type": dominant})
    if observed:
        return dimension_result("ambiguous", {"work_type": incoming, "observed_work_types": observed})
    return dimension_result("unavailable", {"reason": "case_has_no_work_type_history"})


def classify_presence_map(presence_map: Dict[str, bool]) -> Tuple[List[str], List[str]]:
    present = sorted([key for key, value in presence_map.items() if value])
    missing = sorted([key for key, value in presence_map.items() if not value])
    return present, missing


def dimension_to_fit(kind: str) -> Optional[float]:
    mapping = {
        "supportive": 1.0,
        "weak_support": 0.7,
        "ambiguous": 0.5,
        "branching_tension": 0.35,
        "contradictory": 0.1,
        "strong_contradiction": 0.0,
        "unavailable": None,
    }
    return mapping.get(kind)


def is_primary_related_kind(kind: str) -> bool:
    return kind in {"supportive", "weak_support", "ambiguous", "branching_tension"}


def is_positive_primary_kind(kind: str) -> bool:
    return kind in {"supportive", "weak_support"}


def is_primary_contradiction_kind(kind: str) -> bool:
    return kind in {"contradictory", "strong_contradiction"}


def confidence_band_rank(band: str) -> int:
    order = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}
    return order.get(str(band).upper(), 0)


def confidence_band_to_value(band: str) -> float:
    mapping = {
        "HIGH": 0.9,
        "MEDIUM": 0.65,
        "LOW": 0.35,
    }
    return mapping.get(str(band).upper(), 0.35)


def dimension_name_sets(dimensions: Dict[str, Dict[str, object]]) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {
        "supportive": [],
        "weak_support": [],
        "ambiguous": [],
        "branching_tension": [],
        "contradictory": [],
        "strong_contradiction": [],
        "unavailable": [],
    }
    for name, payload in dimensions.items():
        kind = str(payload.get("kind") or "unavailable")
        result.setdefault(kind, []).append(name)
    return result


def related_axis_flags(
    spatial: Dict[str, object],
    temporal: Dict[str, object],
    ticket: Dict[str, object],
    asset: Dict[str, object],
    *,
    strong_context_shared: bool,
    any_context_shared: bool,
) -> Dict[str, bool]:
    spatial_related = is_primary_related_kind(str(spatial["kind"]))
    temporal_related = is_primary_related_kind(str(temporal["kind"]))
    context_related = bool(
        strong_context_shared
        or any_context_shared
        or is_primary_related_kind(str(ticket["kind"]))
        or is_primary_related_kind(str(asset["kind"]))
    )
    return {
        "spatial": spatial_related,
        "temporal": temporal_related,
        "context": context_related,
    }


def derive_relatedness(axis_flags: Dict[str, bool], *, strong_context_shared: bool) -> Tuple[bool, List[str]]:
    related_axes = [name for name, value in axis_flags.items() if value]

    if len(related_axes) >= 2:
        return True, related_axes

    if strong_context_shared and any(axis_flags.get(axis, False) for axis in ("spatial", "temporal")):
        return True, related_axes

    return False, related_axes


def derive_branch_reason(
    *,
    spatial_kind: str,
    temporal_kind: str,
    ticket_kind: str,
    asset_kind: str,
    strong_context_shared: bool,
    any_context_shared: bool,
    contractor_kind: str,
    work_type_kind: str,
    related_axes: Sequence[str],
) -> Optional[str]:
    if ticket_kind in {"contradictory", "strong_contradiction"} and spatial_kind in {
        "supportive",
        "weak_support",
        "branching_tension",
    }:
        return "ticket_mismatch_same_spatial_cluster"

    if asset_kind in {"contradictory", "strong_contradiction"} and spatial_kind in {
        "supportive",
        "weak_support",
        "branching_tension",
    }:
        return "asset_mismatch_same_spatial_cluster"

    if spatial_kind == "branching_tension" and any_context_shared:
        return "spatial_drift_with_context_overlap"

    if temporal_kind == "branching_tension" and any_context_shared:
        return "temporal_discontinuity_same_context"

    if spatial_kind in {"contradictory", "strong_contradiction"} and strong_context_shared:
        return "shared_identity_with_spatial_drift"

    if temporal_kind in {"contradictory", "strong_contradiction"} and strong_context_shared:
        return "shared_identity_with_temporal_discontinuity"

    if contractor_kind == "contradictory" and work_type_kind == "contradictory" and len(related_axes) >= 2:
        return "secondary_context_changed_on_related_activity"

    if len(related_axes) >= 2:
        return "related_activity_shows_identity_drift"

    return None


def derive_confidence_band(
    *,
    decision: str,
    strong_context_shared: bool,
    primary_positive_count: int,
    primary_contradiction_count: int,
    strong_primary_contradiction_count: int,
    missing_fields: Sequence[str],
    related_axes: Sequence[str],
    degraded: bool,
) -> str:
    if decision == "ATTACH":
        if (
            strong_context_shared
            and primary_positive_count >= 2
            and primary_contradiction_count == 0
            and strong_primary_contradiction_count == 0
            and len(missing_fields) <= 2
        ):
            return "HIGH"
        if primary_positive_count >= 2 and primary_contradiction_count <= 1:
            return "MEDIUM"
        return "LOW"

    if decision == "WEAK_ATTACH":
        if primary_positive_count >= 2 and primary_contradiction_count == 0 and degraded:
            return "MEDIUM"
        return "LOW"

    if decision == "BRANCH_NEW_CASE":
        if len(related_axes) >= 2 and strong_primary_contradiction_count == 0:
            return "MEDIUM"
        return "LOW"

    return "LOW"


# ============================================================
# CASE MATCH / BRANCH DECISION
# ============================================================

def assess_case_match(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Dict[str, object]:
    presence_map = record_presence_map_from_analysis(analysis)
    present_fields, missing_fields = classify_presence_map(presence_map)

    spatial = spatial_dimension(case, analysis, event_index)
    temporal = temporal_dimension(case, analysis, event_index)
    ticket = ticket_dimension(case, analysis)
    asset = asset_dimension(case, analysis)
    contractor = contractor_dimension(case, analysis)
    work_type = work_type_dimension(case, analysis)

    dimensions = {
        "spatial": spatial,
        "temporal": temporal,
        "ticket": ticket,
        "asset": asset,
        "contractor": contractor,
        "work_type": work_type,
    }

    grouped = dimension_name_sets(dimensions)

    strong_context_shared = bool(identity_ticket_overlap(case, analysis) or identity_asset_overlap(case, analysis))
    any_context_shared = bool(contextual_ticket_overlap(case, analysis) or contextual_asset_overlap(case, analysis))

    axis_flags = related_axis_flags(
        spatial,
        temporal,
        ticket,
        asset,
        strong_context_shared=strong_context_shared,
        any_context_shared=any_context_shared,
    )
    related, related_axes = derive_relatedness(axis_flags, strong_context_shared=strong_context_shared)

    primary_positive_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if is_positive_primary_kind(str(dimensions[name]["kind"]))
    ]
    primary_ambiguous_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if str(dimensions[name]["kind"]) == "ambiguous"
    ]
    primary_branching_tension_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if str(dimensions[name]["kind"]) == "branching_tension"
    ]
    primary_contradictory_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if str(dimensions[name]["kind"]) == "contradictory"
    ]
    strong_primary_contradictory_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if str(dimensions[name]["kind"]) == "strong_contradiction"
    ]
    primary_unavailable_dimensions = [
        name for name in ("spatial", "temporal", "ticket", "asset")
        if str(dimensions[name]["kind"]) == "unavailable"
    ]

    secondary_supportive_dimensions = [
        name for name in ("contractor", "work_type")
        if str(dimensions[name]["kind"]) == "supportive"
    ]
    secondary_ambiguous_dimensions = [
        name for name in ("contractor", "work_type")
        if str(dimensions[name]["kind"]) == "ambiguous"
    ]
    secondary_contradictory_dimensions = [
        name for name in ("contractor", "work_type")
        if str(dimensions[name]["kind"]) in {"contradictory", "strong_contradiction"}
    ]

    spatial_kind = str(spatial["kind"])
    temporal_kind = str(temporal["kind"])
    ticket_kind = str(ticket["kind"])
    asset_kind = str(asset["kind"])
    contractor_kind = str(contractor["kind"])
    work_type_kind = str(work_type["kind"])

    primary_positive_count = len(primary_positive_dimensions)
    primary_contradiction_count = len(primary_contradictory_dimensions)
    strong_primary_contradiction_count = len(strong_primary_contradictory_dimensions)
    degraded = len(missing_fields) > 0
    identity_consistent = bool(strong_context_shared)

    hard_reject_only_secondary = (
        primary_positive_count == 0
        and len(primary_ambiguous_dimensions) == 0
        and len(primary_branching_tension_dimensions) == 0
        and len(secondary_supportive_dimensions) > 0
    )

    hard_reject_no_primary_basis = (
        not related
        and not strong_context_shared
        and primary_positive_count == 0
        and len(primary_ambiguous_dimensions) == 0
        and len(primary_branching_tension_dimensions) == 0
    )

    hard_reject_spatial_far_no_context = (
        spatial_kind in {"contradictory", "strong_contradiction"}
        and not any_context_shared
        and temporal_kind in {"unavailable", "contradictory", "strong_contradiction"}
    )

    hard_reject_temporal_far_no_context = (
        temporal_kind in {"contradictory", "strong_contradiction"}
        and not any_context_shared
        and spatial_kind in {"unavailable", "contradictory", "strong_contradiction"}
    )

    hard_reject_both_far = (
        spatial_kind in {"contradictory", "strong_contradiction"}
        and temporal_kind in {"contradictory", "strong_contradiction"}
        and not any_context_shared
    )

    hard_reject_weak_single_axis = (
        len(related_axes) == 1
        and not strong_context_shared
        and primary_positive_count <= 1
        and len(primary_ambiguous_dimensions) == 0
        and len(primary_branching_tension_dimensions) == 0
    )

    branch_reason = derive_branch_reason(
        spatial_kind=spatial_kind,
        temporal_kind=temporal_kind,
        ticket_kind=ticket_kind,
        asset_kind=asset_kind,
        strong_context_shared=strong_context_shared,
        any_context_shared=any_context_shared,
        contractor_kind=contractor_kind,
        work_type_kind=work_type_kind,
        related_axes=related_axes,
    )

    if hard_reject_only_secondary:
        decision = "NEW_UNRELATED_CASE"
        reason = "secondary_signals_cannot_carry_identity"
    elif hard_reject_no_primary_basis:
        decision = "NEW_UNRELATED_CASE"
        reason = "no_primary_continuity_basis"
    elif hard_reject_both_far:
        decision = "NEW_UNRELATED_CASE"
        reason = "spatial_and_temporal_contradiction_without_shared_context"
    elif hard_reject_spatial_far_no_context:
        decision = "NEW_UNRELATED_CASE"
        reason = "spatial_contradiction_without_context_support"
    elif hard_reject_temporal_far_no_context:
        decision = "NEW_UNRELATED_CASE"
        reason = "temporal_contradiction_without_context_support"
    elif hard_reject_weak_single_axis:
        decision = "NEW_UNRELATED_CASE"
        reason = "single_weak_primary_axis_is_not_enough_for_continuity"
    elif (
        related
        and spatial_kind in {"supportive", "weak_support"}
        and temporal_kind in {"supportive", "weak_support"}
        and strong_primary_contradiction_count == 0
        and primary_contradiction_count == 0
        and (
            strong_context_shared
            or primary_positive_count >= 2
        )
    ):
        decision = "ATTACH"
        reason = "continuity_preserved_across_primary_axes"
    elif (
        related
        and spatial_kind in {"supportive", "weak_support"}
        and temporal_kind in {"supportive", "weak_support", "unavailable"}
        and strong_primary_contradiction_count == 0
        and primary_contradiction_count <= 1
        and primary_positive_count >= 1
        and degraded
    ):
        decision = "WEAK_ATTACH"
        reason = "continuity_supported_under_degraded_primary_evidence"
    elif (
        related
        and (
            len(primary_branching_tension_dimensions) > 0
            or primary_contradiction_count > 0
            or strong_primary_contradiction_count > 0
            or branch_reason is not None
        )
    ):
        decision = "BRANCH_NEW_CASE"
        reason = branch_reason or "related_but_identity_has_drifted"
    elif related:
        decision = "BRANCH_NEW_CASE"
        reason = branch_reason or "related_but_not_clean_enough_for_direct_attachment"
    else:
        decision = "NEW_UNRELATED_CASE"
        reason = "no_meaningful_continuity_detected"

    confidence_band = derive_confidence_band(
        decision=decision,
        strong_context_shared=strong_context_shared,
        primary_positive_count=primary_positive_count,
        primary_contradiction_count=primary_contradiction_count,
        strong_primary_contradiction_count=strong_primary_contradiction_count,
        missing_fields=missing_fields,
        related_axes=related_axes,
        degraded=degraded,
    )

    ambiguity_flags: List[str] = []
    if missing_fields:
        ambiguity_flags.append("missing_primary_fields")
    if degraded and decision == "WEAK_ATTACH":
        ambiguity_flags.append("weak_primary_continuity")
    if primary_contradiction_count > 0 or strong_primary_contradiction_count > 0:
        ambiguity_flags.append("conflicting_primary_signals")
    if (
        len(secondary_supportive_dimensions) > 0
        and primary_positive_count == 0
        and len(primary_ambiguous_dimensions) == 0
        and len(primary_branching_tension_dimensions) == 0
    ):
        ambiguity_flags.append("overreliance_on_secondary_signals")

    return {
        "decision": decision,
        "reason": reason,
        "branch_reason": branch_reason,
        "confidence_band": confidence_band,
        "confidence": confidence_band_to_value(confidence_band),
        "identity_consistent": identity_consistent,
        "degraded": degraded,
        "present_fields": present_fields,
        "missing_fields": missing_fields,
        "related": related,
        "related_axes": related_axes,
        "axis_flags": axis_flags,
        "strong_context_shared": strong_context_shared,
        "any_context_shared": any_context_shared,
        "primary_positive_count": primary_positive_count,
        "primary_contradiction_count": primary_contradiction_count,
        "strong_primary_contradiction_count": strong_primary_contradiction_count,
        "supportive_dimensions": grouped["supportive"],
        "weak_support_dimensions": grouped["weak_support"],
        "ambiguous_dimensions": grouped["ambiguous"],
        "branching_tension_dimensions": grouped["branching_tension"],
        "contradictory_dimensions": grouped["contradictory"],
        "strong_contradictory_dimensions": grouped["strong_contradiction"],
        "unavailable_dimensions": grouped["unavailable"],
        "primary_supportive_dimensions": primary_positive_dimensions,
        "primary_ambiguous_dimensions": primary_ambiguous_dimensions,
        "primary_branching_tension_dimensions": primary_branching_tension_dimensions,
        "primary_contradictory_dimensions": primary_contradictory_dimensions,
        "strong_primary_contradictory_dimensions": strong_primary_contradictory_dimensions,
        "primary_unavailable_dimensions": primary_unavailable_dimensions,
        "secondary_supportive_dimensions": secondary_supportive_dimensions,
        "secondary_ambiguous_dimensions": secondary_ambiguous_dimensions,
        "secondary_contradictory_dimensions": secondary_contradictory_dimensions,
        "ambiguity_flags": ambiguity_flags,
        "dimensions": dimensions,
    }


def assessment_priority(decision: str) -> int:
    order = {
        "ATTACH": 4,
        "WEAK_ATTACH": 3,
        "BRANCH_NEW_CASE": 2,
        "NEW_UNRELATED_CASE": 1,
        "REJECT_ATTACHMENT": 0,
    }
    return order.get(decision, 0)


def assessment_selection_key(
    assessment: Dict[str, object],
    case: CaseRecord,
) -> Tuple[int, int, int, int, int, datetime]:
    return (
        assessment_priority(str(assessment.get("decision") or "")),
        confidence_band_rank(str(assessment.get("confidence_band") or "LOW")),
        int(assessment.get("primary_positive_count") or 0),
        -int(assessment.get("primary_contradiction_count") or 0),
        len(list(assessment.get("related_axes", []) or [])),
        case_sort_key(case),
    )


def build_event_attachment_assessment(
    case: CaseRecord,
    analysis: EventAnalysis,
    match_assessment: Dict[str, object],
) -> AttachmentAssessment:
    dimensions = match_assessment["dimensions"]
    identity_consistent = bool(match_assessment.get("identity_consistent"))
    decision = str(match_assessment.get("decision") or "ATTACH")
    confidence_band = str(match_assessment.get("confidence_band") or "LOW")

    return build_attachment_assessment(
        allowed=decision in {"ATTACH", "WEAK_ATTACH", "BRANCH_NEW_CASE"},
        reason=str(match_assessment.get("reason") or "continuity_decision"),
        spatial_fit=dimension_to_fit(dimensions["spatial"]["kind"]),
        temporal_fit=dimension_to_fit(dimensions["temporal"]["kind"]),
        ticket_fit=dimension_to_fit(dimensions["ticket"]["kind"]),
        asset_fit=dimension_to_fit(dimensions["asset"]["kind"]),
        identity_consistent=identity_consistent,
        context_only=not identity_consistent,
        confidence=match_assessment.get("confidence"),
        metadata={
            "decision": decision,
            "confidence_band": confidence_band,
            "branch_reason": match_assessment.get("branch_reason"),
            "related_axes": match_assessment.get("related_axes", []),
            "primary_supportive_dimensions": match_assessment.get("primary_supportive_dimensions", []),
            "primary_ambiguous_dimensions": match_assessment.get("primary_ambiguous_dimensions", []),
            "primary_branching_tension_dimensions": match_assessment.get("primary_branching_tension_dimensions", []),
            "primary_contradictory_dimensions": match_assessment.get("primary_contradictory_dimensions", []),
            "strong_primary_contradictory_dimensions": match_assessment.get("strong_primary_contradictory_dimensions", []),
            "secondary_supportive_dimensions": match_assessment.get("secondary_supportive_dimensions", []),
            "secondary_ambiguous_dimensions": match_assessment.get("secondary_ambiguous_dimensions", []),
            "secondary_contradictory_dimensions": match_assessment.get("secondary_contradictory_dimensions", []),
            "ambiguity_flags": match_assessment.get("ambiguity_flags", []),
            "present_fields": match_assessment.get("present_fields", []),
            "missing_fields": match_assessment.get("missing_fields", []),
            "event_id": analysis.event.event_id,
            "alternative_case_ids": match_assessment.get("alternative_case_ids", []),
        },
    )


def select_best_case_decision(
    registry: CaseRegistry,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> Tuple[Optional[CaseRecord], Optional[Dict[str, object]]]:
    candidate_pairs: List[Tuple[CaseRecord, Dict[str, object]]] = []

    for case in registry.cases:
        if not case_is_open_for_assignment(case, analysis, event_index):
            continue

        assessment = assess_case_match(case, analysis, event_index)
        decision = str(assessment["decision"])

        if decision == "NEW_UNRELATED_CASE":
            continue

        candidate_pairs.append((case, assessment))

    if not candidate_pairs:
        return None, None

    candidate_pairs.sort(
        key=lambda pair: assessment_selection_key(pair[1], pair[0]),
        reverse=True,
    )

    best_case, best_assessment = candidate_pairs[0]
    alternative_case_ids = [case.case_id for case, _ in candidate_pairs[1:]]

    if alternative_case_ids:
        best_assessment["alternative_case_ids"] = alternative_case_ids
        best_assessment["multiple_candidate_cases"] = True
    else:
        best_assessment["alternative_case_ids"] = []
        best_assessment["multiple_candidate_cases"] = False

    best_case.metadata["last_grouping_match"] = {
        "matched_event_id": analysis.event.event_id,
        "decision": best_assessment["decision"],
        "reason": best_assessment["reason"],
        "branch_reason": best_assessment.get("branch_reason"),
        "confidence_band": best_assessment.get("confidence_band"),
        "matched_at": utc_now_iso(),
        "alternative_case_ids": alternative_case_ids,
    }

    return best_case, best_assessment


# ============================================================
# CASE CREATION / UPDATE
# ============================================================

def create_empty_case(case_id: str, created_at: Optional[str] = None) -> CaseRecord:
    timestamp = created_at or utc_now_iso()
    case = CaseRecord(
        case_id=case_id,
        created_at=timestamp,
        updated_at=timestamp,
        status="ACTIVE",
        identity=CaseIdentity(),
        event_ids=[],
        ticket_ids=[],
        asset_ids=[],
        context_ticket_ids=[],
        context_asset_ids=[],
        field_report_ids=[],
        marking_ids=[],
        positive_response_ids=[],
        attachments=[],
        observations=[],
        tags=[],
        metadata={},
    )
    ensure_case_metadata_defaults(case)
    set_case_family_root(case)
    return case


def clone_prior_case(prior_case: CaseRecord) -> CaseRecord:
    cloned = deepcopy(prior_case)
    cloned = normalize_case_record(cloned)
    cloned.metadata = dict(cloned.metadata or {})
    cloned.metadata["seeded_from_prior_run"] = True
    return cloned


def update_case_anchor_if_needed(
    case: CaseRecord,
    analysis: EventAnalysis,
    match_assessment: Optional[Dict[str, object]] = None,
) -> None:
    """
    Keep anchors stable. Only update when the case has no anchor or the current
    anchor is clearly weaker than the new evidence.
    """
    if case.identity.anchor_event_id is None:
        case.identity.anchor_event_id = analysis.event.event_id
        case.identity.anchor_time = analysis.event.event_time
        case.identity.anchor_lat = getattr(analysis.event, "lat", None)
        case.identity.anchor_lon = getattr(analysis.event, "lon", None)
        return

    current_anchor_lat = case.identity.anchor_lat
    current_anchor_lon = case.identity.anchor_lon
    new_lat = getattr(analysis.event, "lat", None)
    new_lon = getattr(analysis.event, "lon", None)

    if current_anchor_lat is None or current_anchor_lon is None:
        case.identity.anchor_time = analysis.event.event_time
        case.identity.anchor_lat = new_lat
        case.identity.anchor_lon = new_lon
        return

    if new_lat is None or new_lon is None:
        return

    centroid_lat = case.metadata.get("recent_centroid_lat")
    centroid_lon = case.metadata.get("recent_centroid_lon")
    if centroid_lat is None or centroid_lon is None:
        return

    current_anchor_dist = haversine_m(current_anchor_lat, current_anchor_lon, centroid_lat, centroid_lon)
    new_anchor_dist = haversine_m(new_lat, new_lon, centroid_lat, centroid_lon)

    decision = str((match_assessment or {}).get("decision") or "")
    if decision in {"ATTACH", "WEAK_ATTACH"} and new_anchor_dist + 10.0 < current_anchor_dist:
        case.identity.anchor_event_id = analysis.event.event_id
        case.identity.anchor_time = analysis.event.event_time
        case.identity.anchor_lat = new_lat
        case.identity.anchor_lon = new_lon


def update_case_identity_context_from_analysis(case: CaseRecord, analysis: EventAnalysis) -> None:
    existing_primary_tickets = set(case.identity.primary_ticket_ids)
    existing_primary_assets = set(case.identity.primary_asset_ids)

    case.ticket_ids = unique_preserve_order([*case.ticket_ids, *analysis.candidate_ticket_ids])
    case.asset_ids = unique_preserve_order([*case.asset_ids, *analysis.candidate_asset_ids])

    contextual_ticket_ids = [
        ticket_id for ticket_id in unique_preserve_order(analysis.candidate_ticket_ids)
        if ticket_id not in existing_primary_tickets
    ]
    contextual_asset_ids = [
        asset_id for asset_id in unique_preserve_order(analysis.candidate_asset_ids)
        if asset_id not in existing_primary_assets
    ]

    case.context_ticket_ids = unique_preserve_order([*case.context_ticket_ids, *contextual_ticket_ids])
    case.context_asset_ids = unique_preserve_order([*case.context_asset_ids, *contextual_asset_ids])

    maybe_fill_identity_from_case_state(case)


def update_case_contractors_and_work_types(case: CaseRecord, analysis: EventAnalysis) -> None:
    ensure_case_metadata_defaults(case)

    contractor = get_analysis_contractor(analysis)
    if contractor:
        observed = unique_preserve_order(list(case.metadata.get("observed_contractors", []) or []) + [contractor])
        case.metadata["observed_contractors"] = observed
        if case.metadata.get("dominant_contractor") is None:
            case.metadata["dominant_contractor"] = contractor

    work_type = get_analysis_work_type(analysis)
    if work_type:
        observed = unique_preserve_order(list(case.metadata.get("observed_work_types", []) or []) + [work_type])
        case.metadata["observed_work_types"] = observed
        if case.metadata.get("dominant_work_type") is None:
            case.metadata["dominant_work_type"] = work_type


def apply_match_assessment_metadata(case: CaseRecord, match_assessment: Dict[str, object]) -> None:
    ensure_case_metadata_defaults(case)

    ambiguity_flags = list(match_assessment.get("ambiguity_flags", []) or [])

    case.metadata["degraded_identity"] = bool(match_assessment.get("degraded"))
    case.metadata["missing_primary_fields"] = "missing_primary_fields" in ambiguity_flags
    case.metadata["weak_primary_continuity"] = "weak_primary_continuity" in ambiguity_flags
    case.metadata["conflicting_primary_signals"] = "conflicting_primary_signals" in ambiguity_flags
    case.metadata["overreliance_on_secondary_signals"] = "overreliance_on_secondary_signals" in ambiguity_flags
    case.metadata["multiple_candidate_cases"] = bool(match_assessment.get("multiple_candidate_cases"))

    if case.metadata["multiple_candidate_cases"]:
        ambiguity_flags.append("multiple_candidate_cases")

    case.metadata["last_match_confidence_band"] = match_assessment.get("confidence_band")
    case.metadata["last_related_axes"] = list(match_assessment.get("related_axes", []) or [])
    case.metadata["last_branch_reason"] = match_assessment.get("branch_reason")

    add_ambiguity_flags(case, ambiguity_flags)


def update_case_ambiguity_flags(case: CaseRecord) -> None:
    ensure_case_metadata_defaults(case)

    ambiguity_flags: List[str] = []

    if len(unique_preserve_order(case.ticket_ids)) > MAX_PRIMARY_TICKET_IDS:
        ambiguity_flags.append("multiple_plausible_tickets")
        case.metadata["multiple_plausible_tickets"] = True
    else:
        case.metadata["multiple_plausible_tickets"] = False

    observed_contractors = [normalize_text(v) for v in list(case.metadata.get("observed_contractors", []) or [])]
    observed_contractors = [v for v in observed_contractors if v]
    if len(unique_preserve_order(observed_contractors)) > 1:
        ambiguity_flags.append("mixed_contractors")
        case.metadata["mixed_contractors"] = True
    else:
        case.metadata["mixed_contractors"] = False

    observed_work_types = [normalize_text(v) for v in list(case.metadata.get("observed_work_types", []) or [])]
    observed_work_types = [v for v in observed_work_types if v]
    if len(unique_preserve_order(observed_work_types)) > 1:
        ambiguity_flags.append("mixed_work_types")
        case.metadata["mixed_work_types"] = True
    else:
        case.metadata["mixed_work_types"] = False

    if case.metadata.get("missing_primary_fields"):
        ambiguity_flags.append("missing_primary_fields")
    if case.metadata.get("weak_primary_continuity"):
        ambiguity_flags.append("weak_primary_continuity")
    if case.metadata.get("conflicting_primary_signals"):
        ambiguity_flags.append("conflicting_primary_signals")
    if case.metadata.get("overreliance_on_secondary_signals"):
        ambiguity_flags.append("overreliance_on_secondary_signals")
    if case.metadata.get("multiple_candidate_cases"):
        ambiguity_flags.append("multiple_candidate_cases")

    case.metadata["ambiguity_flags"] = unique_preserve_order(ambiguity_flags)


def update_case_continuity_stats(case: CaseRecord, event_index: Dict[str, EventRecord]) -> None:
    ensure_case_metadata_defaults(case)

    indexed_events = get_case_events(case, event_index)
    indexed_times = [parse_datetime(event.event_time) for event in indexed_events]
    indexed_times = [value for value in indexed_times if value is not None]
    if indexed_times:
        earliest = min(indexed_times).isoformat().replace("+00:00", "Z")
        latest = max(indexed_times).isoformat().replace("+00:00", "Z")
        prior_earliest = parse_datetime(case.metadata.get("earliest_event_time"))
        prior_latest = parse_datetime(case.metadata.get("latest_event_time"))
        case.metadata["earliest_event_time"] = (
            min(min(indexed_times), prior_earliest).isoformat().replace("+00:00", "Z")
            if prior_earliest is not None
            else earliest
        )
        case.metadata["latest_event_time"] = (
            max(max(indexed_times), prior_latest).isoformat().replace("+00:00", "Z")
            if prior_latest is not None
            else latest
        )

    centroid = get_case_centroid(case, event_index)
    if centroid is not None:
        case.metadata["recent_centroid_lat"] = safe_round(centroid[0], 8)
        case.metadata["recent_centroid_lon"] = safe_round(centroid[1], 8)

    spread = compute_case_spatial_spread_m(case, event_index)
    case.metadata["spatial_spread_m"] = safe_round(spread, 2)

    longest_gap = compute_longest_case_gap_min(case, event_index)
    case.metadata["longest_gap_min"] = safe_round(longest_gap, 2)

    if spread is not None and spread > MAX_CENTROID_DRIFT_DISTANCE_M:
        case.metadata["drifting_activity"] = True
        case.metadata["fork_suspected"] = True
    else:
        case.metadata["drifting_activity"] = False

    if (
        case.identity.anchor_lat is not None
        and case.identity.anchor_lon is not None
        and centroid is not None
    ):
        drift = haversine_m(case.identity.anchor_lat, case.identity.anchor_lon, centroid[0], centroid[1])
        if drift > MAX_ANCHOR_DRIFT_DISTANCE_M:
            case.metadata["fork_suspected"] = True


def log_case_attachment_decision(
    case: CaseRecord,
    analysis: EventAnalysis,
    match_assessment: Dict[str, object],
) -> None:
    append_case_history(
        case,
        "attachment_history",
        {
            "event_id": analysis.event.event_id,
            "at": utc_now_iso(),
            "decision": match_assessment.get("decision"),
            "reason": match_assessment.get("reason"),
            "branch_reason": match_assessment.get("branch_reason"),
            "confidence_band": match_assessment.get("confidence_band"),
            "present_fields": list(match_assessment.get("present_fields", []) or []),
            "missing_fields": list(match_assessment.get("missing_fields", []) or []),
            "related_axes": list(match_assessment.get("related_axes", []) or []),
            "primary_supportive_dimensions": list(match_assessment.get("primary_supportive_dimensions", []) or []),
            "primary_ambiguous_dimensions": list(match_assessment.get("primary_ambiguous_dimensions", []) or []),
            "primary_branching_tension_dimensions": list(match_assessment.get("primary_branching_tension_dimensions", []) or []),
            "primary_contradictory_dimensions": list(match_assessment.get("primary_contradictory_dimensions", []) or []),
            "strong_primary_contradictory_dimensions": list(match_assessment.get("strong_primary_contradictory_dimensions", []) or []),
            "secondary_supportive_dimensions": list(match_assessment.get("secondary_supportive_dimensions", []) or []),
            "secondary_ambiguous_dimensions": list(match_assessment.get("secondary_ambiguous_dimensions", []) or []),
            "secondary_contradictory_dimensions": list(match_assessment.get("secondary_contradictory_dimensions", []) or []),
            "ambiguity_flags": list(match_assessment.get("ambiguity_flags", []) or []),
            "alternative_case_ids": list(match_assessment.get("alternative_case_ids", []) or []),
        },
        MAX_ATTACHMENT_HISTORY,
    )


def log_case_rejection_decision(
    case: CaseRecord,
    analysis: EventAnalysis,
    match_assessment: Dict[str, object],
) -> None:
    append_case_history(
        case,
        "rejected_attachment_history",
        {
            "event_id": analysis.event.event_id,
            "at": utc_now_iso(),
            "decision": match_assessment.get("decision"),
            "reason": match_assessment.get("reason"),
            "branch_reason": match_assessment.get("branch_reason"),
            "confidence_band": match_assessment.get("confidence_band"),
            "present_fields": list(match_assessment.get("present_fields", []) or []),
            "missing_fields": list(match_assessment.get("missing_fields", []) or []),
            "related_axes": list(match_assessment.get("related_axes", []) or []),
            "primary_contradictory_dimensions": list(match_assessment.get("primary_contradictory_dimensions", []) or []),
            "strong_primary_contradictory_dimensions": list(match_assessment.get("strong_primary_contradictory_dimensions", []) or []),
            "ambiguity_flags": list(match_assessment.get("ambiguity_flags", []) or []),
        },
        MAX_REJECTION_HISTORY,
    )


def attach_event_analysis_to_case(
    case: CaseRecord,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
    match_assessment: Optional[Dict[str, object]] = None,
) -> None:
    ensure_case_metadata_defaults(case)

    case.event_ids = unique_preserve_order([*case.event_ids, analysis.event.event_id])

    update_case_identity_context_from_analysis(case, analysis)
    update_case_contractors_and_work_types(case, analysis)
    update_case_continuity_stats(case, event_index)

    if match_assessment is None:
        present_fields, missing_fields = classify_presence_map(record_presence_map_from_analysis(analysis))
        match_assessment = {
            "decision": "ATTACH",
            "reason": "case_anchor_or_initial_attachment",
            "branch_reason": None,
            "confidence_band": "HIGH",
            "confidence": confidence_band_to_value("HIGH"),
            "identity_consistent": True,
            "degraded": bool(missing_fields),
            "present_fields": present_fields,
            "missing_fields": missing_fields,
            "related_axes": ["spatial", "temporal", "context"],
            "primary_supportive_dimensions": ["spatial", "temporal"],
            "primary_ambiguous_dimensions": [],
            "primary_branching_tension_dimensions": [],
            "primary_contradictory_dimensions": [],
            "strong_primary_contradictory_dimensions": [],
            "secondary_supportive_dimensions": [],
            "secondary_ambiguous_dimensions": [],
            "secondary_contradictory_dimensions": [],
            "ambiguity_flags": ["missing_primary_fields"] if missing_fields else [],
            "multiple_candidate_cases": False,
            "alternative_case_ids": [],
            "dimensions": {
                "spatial": {"kind": "supportive"},
                "temporal": {"kind": "supportive"},
                "ticket": {"kind": "supportive" if analysis.candidate_ticket_ids else "unavailable"},
                "asset": {"kind": "supportive" if analysis.candidate_asset_ids else "unavailable"},
                "contractor": {"kind": "unavailable"},
                "work_type": {"kind": "unavailable"},
            },
        }

    event_assessment = build_event_attachment_assessment(case, analysis, match_assessment)
    event_role = "trigger" if analysis.event.event_id == case.identity.anchor_event_id else "event"
    append_attachment_if_missing(
        case,
        build_case_attachment(
            "event",
            analysis.event.event_id,
            role=event_role,
            assessment=event_assessment,
            metadata={
                "event_time": analysis.event.event_time,
                "timestamp_basis": analysis.event.metadata.get("timestamp_basis"),
                "timestamp_label": analysis.event.metadata.get("timestamp_label"),
                "ingested_at": analysis.event.metadata.get("ingested_at"),
                "used_ingest_time_fallback": analysis.event.metadata.get("used_ingest_time_fallback"),
            },
        ),
    )

    for ticket_id in case.identity.primary_ticket_ids:
        append_attachment_if_missing(
            case,
            build_case_attachment(
                "ticket",
                ticket_id,
                role="primary_identity",
                assessment=build_attachment_assessment(
                    allowed=True,
                    reason="case_identity_ticket",
                    ticket_fit=1.0,
                    identity_consistent=True,
                    context_only=False,
                    confidence=case.identity.identity_confidence,
                    metadata={"confidence_band": "HIGH"},
                ),
            ),
        )

    for asset_id in case.identity.primary_asset_ids:
        append_attachment_if_missing(
            case,
            build_case_attachment(
                "asset",
                asset_id,
                role="primary_identity",
                assessment=build_attachment_assessment(
                    allowed=True,
                    reason="case_identity_asset",
                    asset_fit=1.0,
                    identity_consistent=True,
                    context_only=False,
                    confidence=case.identity.identity_confidence,
                    metadata={"confidence_band": "HIGH"},
                ),
            ),
        )

    contextual_ticket_ids = [
        ticket_id for ticket_id in unique_preserve_order(analysis.candidate_ticket_ids)
        if ticket_id not in set(case.identity.primary_ticket_ids)
    ]
    contextual_asset_ids = [
        asset_id for asset_id in unique_preserve_order(analysis.candidate_asset_ids)
        if asset_id not in set(case.identity.primary_asset_ids)
    ]

    for ticket_id in contextual_ticket_ids:
        append_attachment_if_missing(
            case,
            build_case_attachment(
                "ticket",
                ticket_id,
                role="context",
                assessment=build_attachment_assessment(
                    allowed=True,
                    reason="contextual_ticket_from_event_analysis",
                    ticket_fit=0.5,
                    identity_consistent=False,
                    context_only=True,
                    confidence=0.5,
                    metadata={"event_id": analysis.event.event_id, "confidence_band": "LOW"},
                ),
            ),
        )

    for asset_id in contextual_asset_ids:
        append_attachment_if_missing(
            case,
            build_case_attachment(
                "asset",
                asset_id,
                role="context",
                assessment=build_attachment_assessment(
                    allowed=True,
                    reason="contextual_asset_from_event_analysis",
                    asset_fit=0.5,
                    identity_consistent=False,
                    context_only=True,
                    confidence=0.5,
                    metadata={"event_id": analysis.event.event_id, "confidence_band": "LOW"},
                ),
            ),
        )

    append_observations_if_missing(case, analysis.observations)
    dedupe_case_attachments(case)
    dedupe_case_observations(case)

    update_case_anchor_if_needed(case, analysis, match_assessment)
    apply_match_assessment_metadata(case, match_assessment)
    update_case_ambiguity_flags(case)
    update_case_continuity_stats(case, event_index)

    case.status = "ACTIVE"
    case.metadata["identity_confidence"] = safe_round(case.identity.identity_confidence, 4)
    case.metadata["last_attached_event_id"] = analysis.event.event_id
    case.metadata["last_attached_at"] = utc_now_iso()
    case.updated_at = utc_now_iso()

    log_case_attachment_decision(case, analysis, match_assessment)


def can_attach_field_report_to_case(case: CaseRecord, report: FieldReportRecord) -> AttachmentAssessment:
    if report.lat is None or report.lon is None:
        return build_attachment_assessment(
            allowed=True,
            reason="field_report_without_coordinates_attached_as_context_only",
            identity_consistent=False,
            context_only=True,
            confidence=0.35,
            metadata={"missing_fields": ["lat", "lon"], "confidence_band": "LOW"},
        )

    spatial_fit: Optional[float] = None
    if case.identity.anchor_lat is not None and case.identity.anchor_lon is not None:
        dist = haversine_m(case.identity.anchor_lat, case.identity.anchor_lon, report.lat, report.lon)
        if dist <= 30.0:
            spatial_fit = 1.0
        elif dist <= 60.0:
            spatial_fit = 0.80
        elif dist <= 100.0:
            spatial_fit = 0.55
        else:
            spatial_fit = 0.15

    identity_consistent = bool(spatial_fit is not None and spatial_fit >= 0.75)
    band = "HIGH" if identity_consistent else "LOW"
    return build_attachment_assessment(
        allowed=True,
        reason="field_report_attached_by_spatial_relevance",
        spatial_fit=spatial_fit,
        identity_consistent=identity_consistent,
        context_only=not identity_consistent,
        confidence=spatial_fit if spatial_fit is not None else 0.35,
        metadata={"confidence_band": band},
    )


def attach_field_report_to_case(case: CaseRecord, report: FieldReportRecord, role: str = "context") -> None:
    assessment = can_attach_field_report_to_case(case, report)
    case.field_report_ids = unique_preserve_order([*case.field_report_ids, report.report_id])
    append_attachment_if_missing(
        case,
        build_case_attachment(
            "field_report",
            report.report_id,
            role=role,
            assessment=assessment,
        ),
    )
    append_observations_if_missing(
        case,
        [
            Observation(
                observation_type=ObservationType.FIELD_REPORT_PRESENT,
                summary=f"Field report {report.report_id} attached to case context",
                field_report_id=report.report_id,
                confidence=assessment.confidence,
                metadata={
                    "observed_at": report.observed_at,
                    "contractor": report.contractor,
                    "equipment_type": report.equipment_type,
                    "work_method": report.work_method,
                    "narrative": report.narrative,
                },
            )
        ],
    )
    dedupe_case_attachments(case)
    dedupe_case_observations(case)
    case.updated_at = utc_now_iso()


def can_attach_marking_to_case(case: CaseRecord, marking: MarkingRecord) -> AttachmentAssessment:
    ticket_fit = 1.0 if marking.ticket_id and marking.ticket_id in get_primary_ticket_ids(case) else 0.0
    context_ticket_fit = 0.70 if marking.ticket_id and marking.ticket_id in get_all_case_ticket_ids(case) else 0.0

    identity_consistent = ticket_fit > 0.0
    combined_ticket_fit = ticket_fit if ticket_fit > 0.0 else context_ticket_fit
    band = "HIGH" if identity_consistent else "LOW"

    return build_attachment_assessment(
        allowed=True,
        reason="marking_attached_by_ticket_or_case_context",
        ticket_fit=combined_ticket_fit if combined_ticket_fit > 0.0 else None,
        identity_consistent=identity_consistent,
        context_only=not identity_consistent,
        confidence=combined_ticket_fit if combined_ticket_fit > 0.0 else 0.4,
        metadata={"confidence_band": band},
    )


def attach_marking_to_case(case: CaseRecord, marking: MarkingRecord, role: str = "context") -> None:
    assessment = can_attach_marking_to_case(case, marking)
    case.marking_ids = unique_preserve_order([*case.marking_ids, marking.marking_id])
    append_attachment_if_missing(
        case,
        build_case_attachment(
            "marking",
            marking.marking_id,
            role=role,
            assessment=assessment,
        ),
    )
    append_observations_if_missing(
        case,
        [
            Observation(
                observation_type=ObservationType.MARKING_STATE_REPORTED,
                summary=f"Marking {marking.marking_id} reported {marking.marking_state or marking.locate_status or 'unknown'}",
                ticket_id=marking.ticket_id,
                marking_id=marking.marking_id,
                confidence=marking.mark_confidence if marking.mark_confidence is not None else assessment.confidence,
                metadata={
                    "observed_at": marking.observed_at,
                    "utility_name": marking.utility_name,
                    "locate_status": marking.locate_status,
                    "marking_state": marking.marking_state,
                    "partial_marks": marking.partial_marks,
                    "clearly_visible": marking.clearly_visible,
                    "refresh_required": marking.refresh_required,
                },
            )
        ],
    )
    dedupe_case_attachments(case)
    dedupe_case_observations(case)
    case.updated_at = utc_now_iso()


def can_attach_positive_response_to_case(case: CaseRecord, response: PositiveResponseRecord) -> AttachmentAssessment:
    ticket_fit = 1.0 if response.ticket_id and response.ticket_id in get_primary_ticket_ids(case) else 0.0
    context_ticket_fit = 0.70 if response.ticket_id and response.ticket_id in get_all_case_ticket_ids(case) else 0.0

    identity_consistent = ticket_fit > 0.0
    combined_ticket_fit = ticket_fit if ticket_fit > 0.0 else context_ticket_fit
    band = "HIGH" if identity_consistent else "LOW"

    return build_attachment_assessment(
        allowed=True,
        reason="positive_response_attached_by_ticket_or_case_context",
        ticket_fit=combined_ticket_fit if combined_ticket_fit > 0.0 else None,
        identity_consistent=identity_consistent,
        context_only=not identity_consistent,
        confidence=combined_ticket_fit if combined_ticket_fit > 0.0 else 0.4,
        metadata={"confidence_band": band},
    )


def attach_positive_response_to_case(
    case: CaseRecord,
    response: PositiveResponseRecord,
    role: str = "context",
) -> None:
    assessment = can_attach_positive_response_to_case(case, response)
    case.positive_response_ids = unique_preserve_order([*case.positive_response_ids, response.response_id])
    append_attachment_if_missing(
        case,
        build_case_attachment(
            "positive_response",
            response.response_id,
            role=role,
            assessment=assessment,
        ),
    )
    append_observations_if_missing(
        case,
        [
            Observation(
                observation_type=ObservationType.POSITIVE_RESPONSE_REPORTED,
                summary=f"Positive response {response.response_id} reported {response.response_status or 'unknown'}",
                ticket_id=response.ticket_id,
                response_id=response.response_id,
                confidence=assessment.confidence,
                metadata={
                    "observed_at": response.observed_at,
                    "responder": response.responder,
                    "response_code": response.response_code,
                    "clear_to_excavate": response.clear_to_excavate,
                    "complete_response": response.complete_response,
                    "conflict_flag": response.conflict_flag,
                },
            )
        ],
    )
    dedupe_case_attachments(case)
    dedupe_case_observations(case)
    case.updated_at = utc_now_iso()


def attach_context_records_to_registry(
    registry: CaseRegistry,
    field_reports: Sequence[FieldReportRecord] = (),
    markings: Sequence[MarkingRecord] = (),
    positive_responses: Sequence[PositiveResponseRecord] = (),
) -> None:
    """
    Attach non-event context records to the best matching cases.

    This preserves case.py ownership of case identity/attachment behavior while
    letting main.py remain orchestration-only.
    """
    for report in field_reports:
        ranked: List[Tuple[float, CaseRecord]] = []
        for case in registry.cases:
            assessment = can_attach_field_report_to_case(case, report)
            confidence = assessment.confidence or 0.0
            if confidence >= 0.55:
                ranked.append((confidence, case))

        if ranked:
            ranked.sort(key=lambda item: item[0], reverse=True)
            attach_field_report_to_case(ranked[0][1], report)

    for marking in markings:
        for case in registry.cases:
            case_ticket_ids = set(get_all_case_ticket_ids(case))
            if marking.ticket_id and marking.ticket_id in case_ticket_ids:
                attach_marking_to_case(case, marking)

    for response in positive_responses:
        for case in registry.cases:
            case_ticket_ids = set(get_all_case_ticket_ids(case))
            if response.ticket_id and response.ticket_id in case_ticket_ids:
                attach_positive_response_to_case(case, response)


def create_case_from_analysis(
    registry: CaseRegistry,
    analysis: EventAnalysis,
    parent_case: Optional[CaseRecord] = None,
    branch_reason: Optional[str] = None,
) -> CaseRecord:
    case = create_empty_case(next_case_id(registry))
    case.identity = build_case_identity_from_analysis(analysis)

    case.ticket_ids = unique_preserve_order(analysis.candidate_ticket_ids)
    case.asset_ids = unique_preserve_order(analysis.candidate_asset_ids)

    case.context_ticket_ids = unique_preserve_order(
        [ticket_id for ticket_id in analysis.candidate_ticket_ids if ticket_id not in set(case.identity.primary_ticket_ids)]
    )
    case.context_asset_ids = unique_preserve_order(
        [asset_id for asset_id in analysis.candidate_asset_ids if asset_id not in set(case.identity.primary_asset_ids)]
    )

    if parent_case is not None:
        ensure_case_metadata_defaults(parent_case)
        ensure_case_metadata_defaults(case)
        family_id = parent_case.metadata.get("family_id") or parent_case.case_id
        case.metadata["family_id"] = family_id
        case.metadata["parent_case_id"] = parent_case.case_id
        case.metadata["branch_from_case_id"] = parent_case.case_id
        case.metadata["branch_reason"] = branch_reason or "related_branch"
        case.metadata["branch_created_at"] = utc_now_iso()
        case.metadata["case_family_role"] = "child"

        parent_case.metadata["fork_suspected"] = True
        register_case_relation(parent_case, case.case_id, "child_case_ids")
        register_case_relation(case, parent_case.case_id, "related_case_ids")

    else:
        set_case_family_root(case)

    present_fields, missing_fields = classify_presence_map(record_presence_map_from_analysis(analysis))

    attach_event_analysis_to_case(
        case,
        analysis,
        event_index={},
        match_assessment={
            "decision": "ATTACH" if parent_case is None else "BRANCH_NEW_CASE",
            "reason": "new_case_anchor" if parent_case is None else (branch_reason or "related_branch"),
            "branch_reason": branch_reason if parent_case is not None else None,
            "confidence_band": "HIGH" if parent_case is None else "MEDIUM",
            "confidence": confidence_band_to_value("HIGH" if parent_case is None else "MEDIUM"),
            "identity_consistent": True,
            "degraded": bool(missing_fields),
            "present_fields": present_fields,
            "missing_fields": missing_fields,
            "related_axes": ["spatial", "temporal", "context"],
            "primary_supportive_dimensions": ["spatial", "temporal"],
            "primary_ambiguous_dimensions": [],
            "primary_branching_tension_dimensions": [],
            "primary_contradictory_dimensions": [],
            "strong_primary_contradictory_dimensions": [],
            "secondary_supportive_dimensions": [],
            "secondary_ambiguous_dimensions": [],
            "secondary_contradictory_dimensions": [],
            "ambiguity_flags": ["missing_primary_fields"] if missing_fields else [],
            "multiple_candidate_cases": False,
            "alternative_case_ids": [],
            "dimensions": {
                "spatial": {"kind": "supportive"},
                "temporal": {"kind": "supportive"},
                "ticket": {"kind": "supportive" if analysis.candidate_ticket_ids else "unavailable"},
                "asset": {"kind": "supportive" if analysis.candidate_asset_ids else "unavailable"},
                "contractor": {"kind": "unavailable"},
                "work_type": {"kind": "unavailable"},
            },
        },
    )

    case.metadata["created_from_event_id"] = analysis.event.event_id
    case.metadata["grouping_reason"] = "branch_from_related_case" if parent_case else "new_case_default_or_no_viable_match"
    case.metadata["thread_hint_ticket_ids"] = unique_preserve_order(analysis.candidate_ticket_ids)
    case.metadata["thread_hint_asset_ids"] = unique_preserve_order(analysis.candidate_asset_ids)
    case.metadata["identity_confidence"] = safe_round(case.identity.identity_confidence, 4)

    maybe_fill_identity_from_case_state(case)
    return case


def sort_cases_newest_first(registry: CaseRegistry) -> None:
    registry.cases.sort(key=case_sort_key, reverse=True)


def add_analysis_to_registry(
    registry: CaseRegistry,
    analysis: EventAnalysis,
    event_index: Dict[str, EventRecord],
) -> CaseRecord:
    existing_event_case = get_case_by_event_id(registry, analysis.event.event_id)
    if existing_event_case is not None:
        return existing_event_case

    matched_case, match_assessment = select_best_case_decision(registry, analysis, event_index)

    if matched_case is None or match_assessment is None:
        new_case = create_case_from_analysis(registry, analysis)
        registry.cases.insert(0, new_case)
        sort_cases_newest_first(registry)
        return new_case

    decision = str(match_assessment["decision"])

    if decision in {"ATTACH", "WEAK_ATTACH"}:
        attach_event_analysis_to_case(
            matched_case,
            analysis,
            event_index=event_index,
            match_assessment=match_assessment,
        )
        maybe_fill_identity_from_case_state(matched_case)
        sort_cases_newest_first(registry)
        return matched_case

    if decision == "BRANCH_NEW_CASE":
        branch_case = create_case_from_analysis(
            registry,
            analysis,
            parent_case=matched_case,
            branch_reason=str(
                match_assessment.get("branch_reason")
                or match_assessment.get("reason")
                or "related_branch"
            ),
        )
        matched_case.metadata["last_branch_decision"] = {
            "event_id": analysis.event.event_id,
            "created_case_id": branch_case.case_id,
            "reason": match_assessment.get("reason"),
            "branch_reason": match_assessment.get("branch_reason"),
            "confidence_band": match_assessment.get("confidence_band"),
            "at": utc_now_iso(),
        }
        apply_match_assessment_metadata(matched_case, match_assessment)
        update_case_ambiguity_flags(matched_case)
        log_case_rejection_decision(matched_case, analysis, match_assessment)
        registry.cases.insert(0, branch_case)
        sort_cases_newest_first(registry)
        return branch_case

    new_case = create_case_from_analysis(registry, analysis)
    registry.cases.insert(0, new_case)
    sort_cases_newest_first(registry)
    return new_case


# ============================================================
# REGISTRY SEEDING FROM PRIOR CASES
# ============================================================

def case_status_rank(case: CaseRecord) -> int:
    status = case_status_normalized(case)
    return {"ACTIVE": 3, "INACTIVE": 2, "CLOSED": 1}.get(status, 0)


def should_keep_case_over_other(case: CaseRecord, other: CaseRecord) -> bool:
    return (
        len(case.event_ids or []),
        case_status_rank(case),
        len(case.attachments or []),
        len(case.observations or []),
        case_sort_key(case),
        str(case.case_id or ""),
    ) >= (
        len(other.event_ids or []),
        case_status_rank(other),
        len(other.attachments or []),
        len(other.observations or []),
        case_sort_key(other),
        str(other.case_id or ""),
    )


def cases_share_same_event_ownership(case: CaseRecord, other: CaseRecord) -> bool:
    left = set(case.event_ids or [])
    right = set(other.event_ids or [])
    if not left or not right:
        return False

    shared = left & right
    if not shared:
        return False

    return shared == left or shared == right


def dedupe_registry_cases_by_event_ownership(cases: Sequence[CaseRecord]) -> List[CaseRecord]:
    deduped: List[CaseRecord] = []

    for case in cases:
        replacement_index: Optional[int] = None
        keep_current = True

        for index, existing in enumerate(deduped):
            if not cases_share_same_event_ownership(case, existing):
                continue

            if should_keep_case_over_other(case, existing):
                replacement_index = index
            else:
                keep_current = False
            break

        if replacement_index is not None:
            deduped[replacement_index] = case
            continue

        if keep_current:
            deduped.append(case)

    return deduped

def seed_registry_from_prior_cases(
    prior_cases: Optional[Sequence[CaseRecord]],
) -> CaseRegistry:
    seeded_cases: List[CaseRecord] = []
    if prior_cases:
        for prior_case in prior_cases:
            try:
                seeded_cases.append(clone_prior_case(prior_case))
            except Exception as exc:
                print(f"[case.py] Skipping malformed prior case during seed: {exc}")

    seeded_cases = dedupe_registry_cases_by_event_ownership(seeded_cases)

    registry = CaseRegistry(
        cases=seeded_cases,
        next_case_number=next_case_number_from_cases(seeded_cases),
    )
    sort_cases_newest_first(registry)
    return registry


# ============================================================
# REGISTRY BUILD / REFRESH
# ============================================================

def refresh_case_metadata(
    registry: CaseRegistry,
    event_index: Dict[str, EventRecord],
) -> None:
    newest_time: Optional[datetime] = None

    for case in registry.cases:
        ensure_case_metadata_defaults(case)
        set_case_family_root(case)

        case.metadata["event_count"] = len(case.event_ids)
        case.metadata["ticket_count"] = len(case.ticket_ids)
        case.metadata["asset_count"] = len(case.asset_ids)
        case.metadata["context_ticket_count"] = len(case.context_ticket_ids)
        case.metadata["context_asset_count"] = len(case.context_asset_ids)
        case.metadata["field_report_count"] = len(case.field_report_ids)
        case.metadata["marking_count"] = len(case.marking_ids)
        case.metadata["positive_response_count"] = len(case.positive_response_ids)
        case.metadata["primary_ticket_count"] = len(case.identity.primary_ticket_ids)
        case.metadata["primary_asset_count"] = len(case.identity.primary_asset_ids)
        case.metadata["normalized_status"] = case_status_normalized(case)
        case.metadata["identity_confidence"] = safe_round(case.identity.identity_confidence, 4)

        update_case_ambiguity_flags(case)
        update_case_continuity_stats(case, event_index)

        latest_time = get_latest_case_event_time(case, event_index)
        if latest_time is not None and (newest_time is None or latest_time > newest_time):
            newest_time = latest_time

    if newest_time is not None:
        for case in registry.cases:
            update_case_lifecycle_status(case, newest_time, event_index)
            case.metadata["normalized_status"] = case_status_normalized(case)


def build_case_registry_from_analyses(
    analyses: Sequence[EventAnalysis],
    events: Sequence[EventRecord],
    prior_cases: Optional[Sequence[CaseRecord]] = None,
) -> CaseRegistry:
    registry = seed_registry_from_prior_cases(prior_cases)
    event_index = {event.event_id: event for event in events}

    for analysis in analyses:
        add_analysis_to_registry(registry, analysis, event_index)

    refresh_case_metadata(registry, event_index)
    sort_cases_newest_first(registry)
    return registry


# ============================================================
# OPTIONAL READ HELPERS
# ============================================================

def get_case_by_id(registry: CaseRegistry, case_id: str) -> Optional[CaseRecord]:
    for case in registry.cases:
        if case.case_id == case_id:
            return case
    return None


def get_case_by_event_id(registry: CaseRegistry, event_id: str) -> Optional[CaseRecord]:
    for case in registry.cases:
        if event_id in set(case.event_ids or []):
            return case
    return None


def list_case_ids(registry: CaseRegistry) -> List[str]:
    return [case.case_id for case in registry.cases]


def case_has_reference(case: CaseRecord, record_type: str, record_id: str) -> bool:
    for attachment in case.attachments:
        if attachment.record_type == record_type and attachment.record_id == record_id:
            return True
    return False
