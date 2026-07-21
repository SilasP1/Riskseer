"""
event_logic.py

RULES FOR THIS FILE
-------------------
1. This file may only translate raw event/ticket/asset data into structured observations.
2. This file may compute local relationships:
   - event <-> ticket spatial relationship
   - event <-> ticket temporal relationship
   - event <-> asset proximity relationship
   - simple repeat/escalation indicators from event history
3. This file may emit:
   - Observation objects
   - candidate ticket IDs
   - candidate asset IDs
   - narrow relationship metadata for later evaluation
4. This file may NOT:
   - assign final case decision_state
   - assign urgency
   - assign response_posture
   - evaluate whole-case behavioral meaning
   - produce operator-facing explanations
   - perform ranking, prioritization, or case scoring
5. If a judgment requires combining multiple observations across time/context,
   it belongs in case_logic.py, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from schemas import (
    AssetRecord,
    EventRecord,
    FieldReportRecord,
    MarkingRecord,
    Observation,
    ObservationType,
    PositiveResponseRecord,
    SourceContext,
    TicketRecord,
)
from ticket_logic import classify_ticket_time_relationship, compute_ticket_match_strength


# ============================================================
# CONFIG
# ============================================================

DEFAULT_ASSET_NEAR_M = 50.0
DEFAULT_REPEAT_WINDOW_MIN = 30.0
DEFAULT_REPEAT_DISTANCE_M = 40.0
DEFAULT_ESCALATION_INTENSITY_DELTA = 0.20


# ============================================================
# LOCAL RESULT STRUCTURES
# ============================================================

@dataclass
class TicketRelationship:
    ticket_id: str
    spatial_distance_m: Optional[float]
    inside_ticket_area: bool
    temporal_state: str  # INSIDE_WINDOW / BEFORE_WINDOW / AFTER_WINDOW / UNKNOWN
    minutes_from_window: Optional[float]
    match_strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetRelationship:
    asset_id: str
    distance_m: Optional[float]
    near_asset: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EventAnalysis:
    event: EventRecord
    observations: List[Observation] = field(default_factory=list)
    candidate_ticket_ids: List[str] = field(default_factory=list)
    candidate_asset_ids: List[str] = field(default_factory=list)
    ticket_relationships: List[TicketRelationship] = field(default_factory=list)
    asset_relationships: List[AssetRelationship] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# TIME / GEO HELPERS
# ============================================================

def parse_datetime(value: Any) -> Optional[datetime]:
    """
    Best-effort datetime parsing.
    Returns None when parsing fails.
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Handle trailing Z in a simple way.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Great-circle distance in meters.
    """
    r = 6371000.0

    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lon2 - lon1)

    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def first_nonempty(*values: Any) -> Optional[str]:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"true", "t", "yes", "y", "1"}:
        return True
    if text in {"false", "f", "no", "n", "0"}:
        return False
    return None


def normalize_optional_datetime(value: Any) -> Optional[str]:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_timestamp_metadata(
    raw: Dict[str, Any],
    *,
    source_type: str,
    source_id: str,
    primary_field_names: Sequence[str],
    fallback_field_names: Sequence[str] = (),
) -> Dict[str, Any]:
    ingested_at = utc_now_iso()
    source_value = None
    source_field = None

    for field_name in [*primary_field_names, *fallback_field_names]:
        candidate = normalize_optional_datetime(raw.get(field_name))
        if candidate:
            source_value = candidate
            source_field = field_name
            break

    used_fallback_now = source_value is None
    effective_value = source_value or ingested_at

    if source_field in primary_field_names:
        timestamp_basis = "source_recorded_time"
        timestamp_label = "Recorded by source"
    elif source_field in fallback_field_names:
        timestamp_basis = "source_logged_time"
        timestamp_label = "Logged by source"
    else:
        timestamp_basis = "ingested_now_missing_source_time"
        timestamp_label = "Logged at ingest (source time missing)"

    return {
        "source_context": SourceContext(
            source_type=source_type,
            source_id=source_id,
            observed_at=source_value,
            ingested_at=ingested_at,
            provenance={
                "timestamp_field": source_field,
                "timestamp_basis": timestamp_basis,
                "timestamp_label": timestamp_label,
                "used_ingest_time_fallback": used_fallback_now,
            },
        ),
        "effective_time": effective_value,
        "ingested_at": ingested_at,
        "timestamp_basis": timestamp_basis,
        "timestamp_label": timestamp_label,
        "timestamp_field": source_field,
        "used_ingest_time_fallback": used_fallback_now,
    }


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def normalize_event_record(raw: Dict[str, Any]) -> EventRecord:
    event_id = str(raw.get("event_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="event",
        source_id=event_id,
        primary_field_names=("event_time",),
        fallback_field_names=("observed_at", "timestamp", "logged_at", "recorded_at"),
    )

    return EventRecord(
        event_id=event_id,
        event_time=time_info["effective_time"],
        lat=float(raw.get("lat")),
        lon=float(raw.get("lon")),
        source=str(raw.get("source", "")).strip(),
        intensity=safe_float(raw.get("intensity")),
        event_type=(str(raw.get("event_type")).strip() if raw.get("event_type") is not None else None),
        equipment_type=(str(raw.get("equipment_type")).strip() if raw.get("equipment_type") is not None else None),
        metadata={
            k: v
            for k, v in raw.items()
            if k not in {"event_id", "event_time", "lat", "lon", "source", "intensity", "event_type", "equipment_type"}
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
        },
        source_context=time_info["source_context"],
    )


def normalize_ticket_record(raw: Dict[str, Any]) -> TicketRecord:
    ticket_id = str(raw.get("ticket_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="ticket",
        source_id=ticket_id,
        primary_field_names=("start_time", "end_time"),
        fallback_field_names=("observed_at", "timestamp", "logged_at", "recorded_at"),
    )
    start_time = normalize_optional_datetime(raw.get("start_time")) or time_info["effective_time"]
    end_time = normalize_optional_datetime(raw.get("end_time")) or start_time

    return TicketRecord(
        ticket_id=ticket_id,
        start_time=start_time,
        end_time=end_time,
        center_lat=float(raw.get("center_lat")),
        center_lon=float(raw.get("center_lon")),
        radius_m=float(raw.get("radius_m")),
        contractor=(str(raw.get("contractor")).strip() if raw.get("contractor") is not None else None),
        work_type=(str(raw.get("work_type")).strip() if raw.get("work_type") is not None else None),
        status=(str(raw.get("status")).strip() if raw.get("status") is not None else None),
        metadata={
            k: v
            for k, v in raw.items()
            if k not in {
                "ticket_id",
                "start_time",
                "end_time",
                "center_lat",
                "center_lon",
                "radius_m",
                "contractor",
                "work_type",
                "status",
            }
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
            "start_time_was_fallback": normalize_optional_datetime(raw.get("start_time")) is None,
            "end_time_was_fallback": normalize_optional_datetime(raw.get("end_time")) is None,
        },
        source_context=time_info["source_context"],
    )


def normalize_asset_record(raw: Dict[str, Any]) -> AssetRecord:
    asset_id = str(raw.get("asset_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="asset",
        source_id=asset_id,
        primary_field_names=("observed_at",),
        fallback_field_names=("timestamp", "logged_at", "recorded_at"),
    )

    return AssetRecord(
        asset_id=asset_id,
        asset_type=str(raw.get("asset_type", "")).strip(),
        lat=float(raw.get("lat")),
        lon=float(raw.get("lon")),
        metadata={
            k: v
            for k, v in raw.items()
            if k not in {"asset_id", "asset_type", "lat", "lon"}
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "asset_logged_at": time_info["effective_time"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
        },
        source_context=time_info["source_context"],
    )


def normalize_field_report_record(raw: Dict[str, Any]) -> FieldReportRecord:
    report_id = str(raw.get("report_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="field_report",
        source_id=report_id,
        primary_field_names=("observed_at", "report_time"),
        fallback_field_names=("timestamp", "logged_at", "recorded_at"),
    )

    return FieldReportRecord(
        report_id=report_id,
        observed_at=time_info["effective_time"],
        lat=safe_float(raw.get("lat")),
        lon=safe_float(raw.get("lon")),
        narrative=first_nonempty(raw.get("narrative"), raw.get("summary"), raw.get("notes")),
        equipment_type=first_nonempty(raw.get("equipment_type"), raw.get("equipment")),
        work_method=first_nonempty(raw.get("work_method"), raw.get("work_type"), raw.get("method")),
        reporter=first_nonempty(raw.get("reporter"), raw.get("observer")),
        contractor=first_nonempty(raw.get("contractor"), raw.get("crew")),
        photos_present=safe_bool(raw.get("photos_present")),
        audio_present=safe_bool(raw.get("audio_present")),
        video_present=safe_bool(raw.get("video_present")),
        metadata={
            k: v
            for k, v in raw.items()
            if k
            not in {
                "report_id",
                "observed_at",
                "report_time",
                "lat",
                "lon",
                "narrative",
                "summary",
                "notes",
                "equipment_type",
                "equipment",
                "work_method",
                "work_type",
                "method",
                "reporter",
                "observer",
                "contractor",
                "crew",
                "photos_present",
                "audio_present",
                "video_present",
            }
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
        },
        source_context=time_info["source_context"],
    )


def normalize_marking_record(raw: Dict[str, Any]) -> MarkingRecord:
    marking_id = str(raw.get("marking_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="marking",
        source_id=marking_id,
        primary_field_names=("observed_at", "last_marked_at", "last_refreshed_at"),
        fallback_field_names=("timestamp", "logged_at", "recorded_at"),
    )

    return MarkingRecord(
        marking_id=marking_id,
        observed_at=time_info["effective_time"],
        lat=safe_float(raw.get("lat")),
        lon=safe_float(raw.get("lon")),
        ticket_id=first_nonempty(raw.get("ticket_id")),
        utility_name=first_nonempty(raw.get("utility_name"), raw.get("utility")),
        marking_state=first_nonempty(raw.get("marking_state"), raw.get("state")),
        locate_status=first_nonempty(raw.get("locate_status"), raw.get("status")),
        mark_type=first_nonempty(raw.get("mark_type"), raw.get("facility_type")),
        last_marked_at=normalize_optional_datetime(raw.get("last_marked_at")),
        last_refreshed_at=normalize_optional_datetime(raw.get("last_refreshed_at")),
        mark_confidence=safe_float(raw.get("mark_confidence")),
        refresh_required=safe_bool(raw.get("refresh_required")),
        partial_marks=safe_bool(raw.get("partial_marks")),
        clearly_visible=safe_bool(raw.get("clearly_visible")),
        metadata={
            k: v
            for k, v in raw.items()
            if k
            not in {
                "marking_id",
                "observed_at",
                "last_marked_at",
                "last_refreshed_at",
                "timestamp",
                "logged_at",
                "recorded_at",
                "lat",
                "lon",
                "ticket_id",
                "utility_name",
                "utility",
                "marking_state",
                "state",
                "locate_status",
                "status",
                "mark_type",
                "facility_type",
                "mark_confidence",
                "refresh_required",
                "partial_marks",
                "clearly_visible",
            }
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
        },
        source_context=time_info["source_context"],
    )


def normalize_positive_response_record(raw: Dict[str, Any]) -> PositiveResponseRecord:
    response_id = str(raw.get("response_id", "")).strip()
    time_info = build_timestamp_metadata(
        raw,
        source_type="positive_response",
        source_id=response_id,
        primary_field_names=("observed_at", "response_time"),
        fallback_field_names=("timestamp", "logged_at", "recorded_at"),
    )

    return PositiveResponseRecord(
        response_id=response_id,
        observed_at=time_info["effective_time"],
        ticket_id=first_nonempty(raw.get("ticket_id")),
        response_status=first_nonempty(raw.get("response_status"), raw.get("status")),
        responder=first_nonempty(raw.get("responder"), raw.get("utility_name"), raw.get("utility")),
        response_code=first_nonempty(raw.get("response_code"), raw.get("code")),
        clear_to_excavate=safe_bool(raw.get("clear_to_excavate")),
        complete_response=safe_bool(raw.get("complete_response")),
        conflict_flag=safe_bool(raw.get("conflict_flag")),
        metadata={
            k: v
            for k, v in raw.items()
            if k
            not in {
                "response_id",
                "observed_at",
                "response_time",
                "timestamp",
                "logged_at",
                "recorded_at",
                "ticket_id",
                "response_status",
                "status",
                "responder",
                "utility_name",
                "utility",
                "response_code",
                "code",
                "clear_to_excavate",
                "complete_response",
                "conflict_flag",
            }
        }
        | {
            "timestamp_basis": time_info["timestamp_basis"],
            "timestamp_label": time_info["timestamp_label"],
            "timestamp_field": time_info["timestamp_field"],
            "ingested_at": time_info["ingested_at"],
            "used_ingest_time_fallback": time_info["used_ingest_time_fallback"],
        },
        source_context=time_info["source_context"],
    )

# ============================================================
# RELATIONSHIP HELPERS
# ============================================================

def analyze_event_ticket_relationship(
    event: EventRecord,
    ticket: TicketRecord,
) -> TicketRelationship:
    distance_m = haversine_m(event.lat, event.lon, ticket.center_lat, ticket.center_lon)
    inside_area = distance_m <= ticket.radius_m

    event_dt = parse_datetime(event.event_time)
    start_dt = parse_datetime(ticket.start_time)
    end_dt = parse_datetime(ticket.end_time)
    temporal_state, minutes_from_window = classify_ticket_time_relationship(event_dt, start_dt, end_dt)

    match_strength = compute_ticket_match_strength(
        inside_area=inside_area,
        temporal_state=temporal_state,
        distance_m=distance_m,
        radius_m=ticket.radius_m,
    )

    return TicketRelationship(
        ticket_id=ticket.ticket_id,
        spatial_distance_m=distance_m,
        inside_ticket_area=inside_area,
        temporal_state=temporal_state,
        minutes_from_window=minutes_from_window,
        match_strength=match_strength,
        metadata={
            "ticket_radius_m": ticket.radius_m,
            "contractor": ticket.contractor,
            "work_type": ticket.work_type,
            "status": ticket.status,
            "ticket_timestamp_basis": ticket.metadata.get("timestamp_basis"),
            "ticket_timestamp_label": ticket.metadata.get("timestamp_label"),
            "ticket_ingested_at": ticket.metadata.get("ingested_at"),
        },
    )


def analyze_event_asset_relationship(
    event: EventRecord,
    asset: AssetRecord,
    near_threshold_m: float = DEFAULT_ASSET_NEAR_M,
) -> AssetRelationship:
    distance_m = haversine_m(event.lat, event.lon, asset.lat, asset.lon)
    return AssetRelationship(
        asset_id=asset.asset_id,
        distance_m=distance_m,
        near_asset=distance_m <= near_threshold_m,
        metadata={
            "asset_type": asset.asset_type,
            "near_threshold_m": near_threshold_m,
            "asset_timestamp_basis": asset.metadata.get("timestamp_basis"),
            "asset_timestamp_label": asset.metadata.get("timestamp_label"),
            "asset_ingested_at": asset.metadata.get("ingested_at"),
            "asset_logged_at": asset.metadata.get("asset_logged_at"),
        },
    )


# ============================================================
# OBSERVATION BUILDERS
# ============================================================

def build_base_event_observation(event: EventRecord) -> Observation:
    return Observation(
        observation_type=ObservationType.EVENT_SEEN,
        summary=f"Event observed from source '{event.source}'",
        event_id=event.event_id,
        value=event.event_type or event.source,
        confidence=event.intensity,
        metadata={
            "event_time": event.event_time,
            "timestamp_basis": event.metadata.get("timestamp_basis"),
            "timestamp_label": event.metadata.get("timestamp_label"),
            "ingested_at": event.metadata.get("ingested_at"),
            "used_ingest_time_fallback": event.metadata.get("used_ingest_time_fallback"),
            "lat": event.lat,
            "lon": event.lon,
            "equipment_type": event.equipment_type,
        },
    )


def build_ticket_observations(
    event: EventRecord,
    relationship: TicketRelationship,
) -> List[Observation]:
    observations: List[Observation] = []

    observations.append(
        Observation(
            observation_type=(
                ObservationType.INSIDE_TICKET_AREA
                if relationship.inside_ticket_area
                else ObservationType.OUTSIDE_TICKET_AREA
            ),
            summary=(
                f"Event is inside ticket area for ticket {relationship.ticket_id}"
                if relationship.inside_ticket_area
                else f"Event is outside ticket area for ticket {relationship.ticket_id}"
            ),
            event_id=event.event_id,
            ticket_id=relationship.ticket_id,
            value=relationship.spatial_distance_m,
            confidence=relationship.match_strength,
            metadata=dict(relationship.metadata),
        )
    )

    if relationship.temporal_state == "INSIDE_WINDOW":
        observations.append(
            Observation(
                observation_type=ObservationType.INSIDE_TICKET_WINDOW,
                summary=f"Event is inside the active time window for ticket {relationship.ticket_id}",
                event_id=event.event_id,
                ticket_id=relationship.ticket_id,
                value=relationship.minutes_from_window,
                confidence=relationship.match_strength,
                metadata=dict(relationship.metadata),
            )
        )
    elif relationship.temporal_state in {"BEFORE_WINDOW", "AFTER_WINDOW"}:
        observations.append(
            Observation(
                observation_type=ObservationType.OUTSIDE_TICKET_WINDOW,
                summary=f"Event is outside the active time window for ticket {relationship.ticket_id}",
                event_id=event.event_id,
                ticket_id=relationship.ticket_id,
                value=relationship.minutes_from_window,
                confidence=relationship.match_strength,
                metadata={
                    **relationship.metadata,
                    "temporal_state": relationship.temporal_state,
                },
            )
        )
    else:
        observations.append(
            Observation(
                observation_type=ObservationType.DATA_GAP,
                summary=f"Ticket {relationship.ticket_id} has insufficient time data for temporal validation",
                event_id=event.event_id,
                ticket_id=relationship.ticket_id,
                confidence=0.2,
                metadata=dict(relationship.metadata),
            )
        )

    return observations


def build_asset_observations(
    event: EventRecord,
    relationship: AssetRelationship,
) -> List[Observation]:
    obs_type = ObservationType.NEAR_ASSET if relationship.near_asset else ObservationType.FAR_FROM_ASSET
    summary = (
        f"Event is near asset {relationship.asset_id}"
        if relationship.near_asset
        else f"Event is far from asset {relationship.asset_id}"
    )

    return [
        Observation(
            observation_type=obs_type,
            summary=summary,
            event_id=event.event_id,
            asset_id=relationship.asset_id,
            value=relationship.distance_m,
            confidence=1.0 if relationship.distance_m is not None else 0.2,
            metadata=dict(relationship.metadata),
        )
    ]


def build_equipment_observations(event: EventRecord) -> List[Observation]:
    observations: List[Observation] = []

    event_type = (event.event_type or "").strip().lower()
    equipment_type = (event.equipment_type or "").strip().lower()
    text_blob = " ".join([event_type, equipment_type]).strip()

    if any(token in text_blob for token in ["excavator", "backhoe", "drill", "boring", "trencher", "plow"]):
        observations.append(
            Observation(
                observation_type=ObservationType.HEAVY_EQUIPMENT_INDICATOR,
                summary="Event suggests heavy equipment presence",
                event_id=event.event_id,
                value=event.equipment_type or event.event_type,
                confidence=0.7,
                metadata={},
            )
        )

    if any(token in text_blob for token in ["hdd", "directional", "horizontal directional drilling", "bore", "trenchless"]):
        observations.append(
            Observation(
                observation_type=ObservationType.TRENCHLESS_INDICATOR,
                summary="Event suggests trenchless or HDD-related activity",
                event_id=event.event_id,
                value=event.equipment_type or event.event_type,
                confidence=0.7,
                metadata={},
            )
        )

    return observations


def build_ticket_presence_observations(
    event: EventRecord,
    candidate_ticket_relationships: Sequence[TicketRelationship],
) -> List[Observation]:
    if not candidate_ticket_relationships:
        return [
            Observation(
                observation_type=ObservationType.NO_MATCHING_TICKET,
                summary="No nearby or plausible matching ticket found for event",
                event_id=event.event_id,
                confidence=0.9,
                metadata={},
            )
        ]

    if len(candidate_ticket_relationships) > 1:
        return [
            Observation(
                observation_type=ObservationType.MULTIPLE_POSSIBLE_TICKETS,
                summary="Multiple plausible tickets are associated with this event",
                event_id=event.event_id,
                confidence=0.6,
                metadata={
                    "ticket_ids": [r.ticket_id for r in candidate_ticket_relationships],
                },
            )
        ]

    return []


def build_repeat_observations(
    event: EventRecord,
    event_history: Sequence[EventRecord],
    repeat_window_min: float = DEFAULT_REPEAT_WINDOW_MIN,
    repeat_distance_m: float = DEFAULT_REPEAT_DISTANCE_M,
    escalation_intensity_delta: float = DEFAULT_ESCALATION_INTENSITY_DELTA,
) -> List[Observation]:
    """
    Narrow local indicators only.
    These are observation flags, not behavioral conclusions.
    """
    observations: List[Observation] = []
    event_dt = parse_datetime(event.event_time)
    if event_dt is None:
        return observations

    nearby_recent: List[EventRecord] = []

    for prior in event_history:
        if prior.event_id == event.event_id:
            continue

        prior_dt = parse_datetime(prior.event_time)
        if prior_dt is None:
            continue

        delta_min = abs((event_dt - prior_dt).total_seconds()) / 60.0
        if delta_min > repeat_window_min:
            continue

        dist_m = haversine_m(event.lat, event.lon, prior.lat, prior.lon)
        if dist_m <= repeat_distance_m:
            nearby_recent.append(prior)

    if nearby_recent:
        observations.append(
            Observation(
                observation_type=ObservationType.REPEATED_ACTIVITY,
                summary="Repeated nearby activity observed within a short time window",
                event_id=event.event_id,
                value=len(nearby_recent),
                confidence=0.7,
                metadata={
                    "repeat_window_min": repeat_window_min,
                    "repeat_distance_m": repeat_distance_m,
                    "prior_event_ids": [e.event_id for e in nearby_recent],
                },
            )
        )

        current_intensity = event.intensity
        prior_intensities = [e.intensity for e in nearby_recent if e.intensity is not None]

        if current_intensity is not None and prior_intensities:
            max_prior = max(prior_intensities)
            if current_intensity - max_prior >= escalation_intensity_delta:
                observations.append(
                    Observation(
                        observation_type=ObservationType.ESCALATING_ACTIVITY,
                        summary="Current event intensity exceeds recent nearby activity",
                        event_id=event.event_id,
                        value=current_intensity - max_prior,
                        confidence=0.65,
                        metadata={
                            "current_intensity": current_intensity,
                            "max_prior_intensity": max_prior,
                            "delta_threshold": escalation_intensity_delta,
                        },
                    )
                )

    return observations


def build_context_gap_observations(
    event: EventRecord,
    tickets: Sequence[TicketRecord],
    assets: Sequence[AssetRecord],
) -> List[Observation]:
    observations: List[Observation] = []

    if not tickets:
        observations.append(
            Observation(
                observation_type=ObservationType.DATA_GAP,
                summary="No ticket context available during event analysis",
                event_id=event.event_id,
                confidence=0.2,
                metadata={"missing_context": "tickets"},
            )
        )

    if not assets:
        observations.append(
            Observation(
                observation_type=ObservationType.DATA_GAP,
                summary="No asset context available during event analysis",
                event_id=event.event_id,
                confidence=0.2,
                metadata={"missing_context": "assets"},
            )
        )

    return observations


# ============================================================
# PRIMARY ANALYSIS
# ============================================================

def analyze_single_event(
    event: EventRecord,
    tickets: Sequence[TicketRecord],
    assets: Sequence[AssetRecord],
    event_history: Optional[Sequence[EventRecord]] = None,
    asset_near_m: float = DEFAULT_ASSET_NEAR_M,
) -> EventAnalysis:
    """
    Analyze one event into structured local observations.
    """
    history = event_history or []
    observations: List[Observation] = [build_base_event_observation(event)]
    observations.extend(build_equipment_observations(event))
    observations.extend(build_context_gap_observations(event, tickets=tickets, assets=assets))
    observations.extend(build_repeat_observations(event, event_history=history))

    ticket_relationships: List[TicketRelationship] = [
        analyze_event_ticket_relationship(event, ticket) for ticket in tickets
    ]

    # Keep locally plausible ticket candidates only.
    # A ticket should not become a candidate just because it has some weak
    # temporal relationship while being spatially far away from the event.
    plausible_ticket_relationships = [
        rel for rel in ticket_relationships
        if (
            rel.inside_ticket_area
            or rel.match_strength >= 0.60
            or (
                rel.temporal_state == "INSIDE_WINDOW"
                and rel.spatial_distance_m is not None
                and rel.metadata.get("ticket_radius_m") is not None
                and rel.spatial_distance_m
                <= rel.metadata["ticket_radius_m"] + max(15.0, rel.metadata["ticket_radius_m"] * 0.10)
            )
        )
    ]

    # Sort best-first for downstream use.
    plausible_ticket_relationships.sort(
        key=lambda r: (
            r.match_strength,
            -(r.spatial_distance_m if r.spatial_distance_m is not None else 10**9),
        ),
        reverse=True,
    )

    observations.extend(build_ticket_presence_observations(event, plausible_ticket_relationships))

    for rel in plausible_ticket_relationships[:3]:
        observations.extend(build_ticket_observations(event, rel))

    asset_relationships: List[AssetRelationship] = [
        analyze_event_asset_relationship(event, asset, near_threshold_m=asset_near_m)
        for asset in assets
    ]
    asset_relationships.sort(
        key=lambda r: (r.distance_m if r.distance_m is not None else 10**9)
    )

    plausible_asset_relationships = [
        rel for rel in asset_relationships
        if rel.near_asset
    ]

    if plausible_asset_relationships:
        for rel in plausible_asset_relationships[:3]:
            observations.extend(build_asset_observations(event, rel))
    elif asset_relationships:
        observations.extend(build_asset_observations(event, asset_relationships[0]))

    return EventAnalysis(
        event=event,
        observations=observations,
        candidate_ticket_ids=[r.ticket_id for r in plausible_ticket_relationships[:3]],
        candidate_asset_ids=[r.asset_id for r in plausible_asset_relationships[:3]],
        ticket_relationships=plausible_ticket_relationships,
        asset_relationships=asset_relationships[:3],
        metadata={
            "total_ticket_relationships_evaluated": len(ticket_relationships),
            "total_asset_relationships_evaluated": len(asset_relationships),
        },
    )


def analyze_events(
    events: Sequence[EventRecord],
    tickets: Sequence[TicketRecord],
    assets: Sequence[AssetRecord],
    asset_near_m: float = DEFAULT_ASSET_NEAR_M,
) -> List[EventAnalysis]:
    """
    Analyze a batch of events.
    Earlier events are available as local history to later events.
    """
    analyses: List[EventAnalysis] = []
    history: List[EventRecord] = []

    sorted_events = sorted(
        events,
        key=lambda e: parse_datetime(e.event_time) or datetime.min,
    )

    for event in sorted_events:
        analysis = analyze_single_event(
            event=event,
            tickets=tickets,
            assets=assets,
            event_history=history,
            asset_near_m=asset_near_m,
        )
        analyses.append(analysis)
        history.append(event)

    return analyses


# ============================================================
# OPTIONAL CONVERSION HELPERS FOR CSV/DICT PIPELINES
# ============================================================

def normalize_event_records(rows: Iterable[Dict[str, Any]]) -> List[EventRecord]:
    return [normalize_event_record(row) for row in rows]


def normalize_ticket_records(rows: Iterable[Dict[str, Any]]) -> List[TicketRecord]:
    return [normalize_ticket_record(row) for row in rows]


def normalize_asset_records(rows: Iterable[Dict[str, Any]]) -> List[AssetRecord]:
    return [normalize_asset_record(row) for row in rows]


def normalize_field_report_records(rows: Iterable[Dict[str, Any]]) -> List[FieldReportRecord]:
    return [normalize_field_report_record(row) for row in rows if str(row.get("report_id", "")).strip()]


def normalize_marking_records(rows: Iterable[Dict[str, Any]]) -> List[MarkingRecord]:
    return [normalize_marking_record(row) for row in rows if str(row.get("marking_id", "")).strip()]


def normalize_positive_response_records(rows: Iterable[Dict[str, Any]]) -> List[PositiveResponseRecord]:
    return [normalize_positive_response_record(row) for row in rows if str(row.get("response_id", "")).strip()]
