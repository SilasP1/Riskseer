"""
source_adaptors/marking_adapter.py

WHAT THIS FILE DOES
-------------------
1. Adapts raw marking / locate status inputs into normalized record dictionaries.
2. Captures what is known about marks, locate state, refresh timing, and confidence.
3. Preserves unknown marking state as unknown instead of forcing a negative value.
4. Records missingness and source quality information.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not decide whether the marks are actually correct.
2. It does not decide whether a site is safe to proceed.
3. It does not group records into cases.
4. It does not evaluate operational risk or human failure.
5. It does not convert absent marking data into "no marks" unless the source explicitly says so.
6. It does not emit final operator-facing conclusions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List

from .base import (
    AdapterResult,
    BaseSourceAdaptor,
    normalize_bool,
    normalize_datetime_str,
    normalize_float,
    normalize_text,
)


class MarkingAdaptor(BaseSourceAdaptor):
    source_type = "marking"

    def adapt(self, raw: Dict[str, Any]) -> AdapterResult:
        warnings: List[str] = []
        errors: List[str] = []
        missing_fields: List[str] = []

        marking_id = normalize_text(raw.get("marking_id") or raw.get("id") or raw.get("source_id")) or ""
        observed_at = normalize_datetime_str(raw.get("observed_at") or raw.get("timestamp"))
        ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        timestamp_label = "Recorded by source" if observed_at else "Logged at ingest (source time missing)"
        last_marked_at = normalize_datetime_str(raw.get("last_marked_at"))
        last_refreshed_at = normalize_datetime_str(raw.get("last_refreshed_at"))

        lat = normalize_float(raw.get("lat") or raw.get("latitude"))
        lon = normalize_float(raw.get("lon") or raw.get("longitude"))

        if not observed_at:
            missing_fields.append("observed_at")
        if lat is None:
            missing_fields.append("lat")
        if lon is None:
            missing_fields.append("lon")

        marking_state = normalize_text(raw.get("marking_state") or raw.get("status") or raw.get("mark_status"))
        locate_status = normalize_text(raw.get("locate_status"))
        utility_name = normalize_text(raw.get("utility_name"))
        ticket_id = normalize_text(raw.get("ticket_id"))
        mark_type = normalize_text(raw.get("mark_type"))
        mark_confidence = normalize_float(raw.get("mark_confidence"))
        refresh_required = normalize_bool(raw.get("refresh_required"))
        partial_marks = normalize_bool(raw.get("partial_marks"))
        clearly_visible = normalize_bool(raw.get("clearly_visible"))

        if not marking_state:
            warnings.append("Marking state is unknown.")
        if not last_marked_at:
            warnings.append("Last marked timestamp is missing.")
        if not ticket_id:
            warnings.append("No ticket ID linked to marking record.")

        completeness = 1.0 - (len(missing_fields) / 3.0)
        completeness = max(0.0, min(1.0, completeness))

        record = {
            "record_type": "marking",
            "marking_id": marking_id,
            "observed_at": observed_at or ingested_at,
            "lat": lat,
            "lon": lon,
            "ticket_id": ticket_id,
            "utility_name": utility_name,
            "marking_state": marking_state,          # explicit unknown allowed
            "locate_status": locate_status,
            "mark_type": mark_type,
            "last_marked_at": last_marked_at,
            "last_refreshed_at": last_refreshed_at,
            "mark_confidence": mark_confidence,
            "refresh_required": refresh_required,
            "partial_marks": partial_marks,
            "clearly_visible": clearly_visible,
            "metadata": {
                "raw_source_type": self.source_type,
                "raw_keys": sorted(list(raw.keys())),
                "timestamp_basis": "source_recorded_time" if observed_at else "ingested_now_missing_source_time",
                "timestamp_label": timestamp_label,
                "ingested_at": ingested_at,
                "used_ingest_time_fallback": observed_at is None,
            },
        }

        observations: List[Dict[str, Any]] = []
        if marking_state:
            observations.append(
                {
                    "observation_type": "MARKING_STATE_REPORTED",
                    "summary": "Marking state was explicitly reported",
                    "source_id": marking_id,
                    "value": marking_state,
                }
            )

        quality = self._build_quality(
            raw=raw,
            source_id=marking_id,
            missing_fields=missing_fields,
            notes=warnings.copy(),
            confidence=mark_confidence if mark_confidence is not None else 0.70,
            freshness=None,
            completeness=completeness,
        )

        return AdapterResult(
            records=[record],
            observations=observations,
            quality=quality,
            errors=errors,
            warnings=warnings,
        )
