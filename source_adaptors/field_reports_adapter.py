"""
source_adaptors/field_reports_adapter.py

WHAT THIS FILE DOES
-------------------
1. Adapts raw field-report style inputs into normalized record dictionaries.
2. Extracts basic location, time, narrative, equipment, and reporting metadata.
3. Records missingness and source quality information.
4. Optionally emits low-level observations that a field report claimed something.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not decide whether a report is true.
2. It does not assign decision_state, urgency, or response posture.
3. It does not group reports into cases.
4. It does not evaluate operational risk.
5. It does not convert unknown into false.
6. It does not rewrite or interpret field narratives into final conclusions.
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


class FieldReportAdaptor(BaseSourceAdaptor):
    source_type = "field_report"

    def adapt(self, raw: Dict[str, Any]) -> AdapterResult:
        warnings: List[str] = []
        errors: List[str] = []
        missing_fields: List[str] = []

        report_id = normalize_text(raw.get("report_id") or raw.get("id") or raw.get("source_id")) or ""
        observed_at = normalize_datetime_str(
            raw.get("observed_at") or raw.get("timestamp") or raw.get("event_time")
        )
        ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        timestamp_label = "Recorded by source" if observed_at else "Logged at ingest (source time missing)"
        lat = normalize_float(raw.get("lat") or raw.get("latitude"))
        lon = normalize_float(raw.get("lon") or raw.get("longitude"))

        if not observed_at:
            missing_fields.append("observed_at")
        if lat is None:
            missing_fields.append("lat")
        if lon is None:
            missing_fields.append("lon")

        narrative = normalize_text(raw.get("narrative") or raw.get("notes") or raw.get("description"))
        equipment_type = normalize_text(raw.get("equipment_type"))
        work_method = normalize_text(raw.get("work_method"))
        reporter = normalize_text(raw.get("reporter") or raw.get("observer"))
        contractor = normalize_text(raw.get("contractor"))
        confidence_hint = normalize_float(raw.get("confidence"))
        photos_present = normalize_bool(raw.get("photos_present"))
        audio_present = normalize_bool(raw.get("audio_present"))
        video_present = normalize_bool(raw.get("video_present"))

        completeness = 1.0 - (len(missing_fields) / 3.0)
        completeness = max(0.0, min(1.0, completeness))

        if not narrative:
            warnings.append("Field report has no narrative text.")
        if confidence_hint is None:
            warnings.append("Field report has no explicit confidence field.")

        record = {
            "record_type": "field_report",
            "report_id": report_id,
            "observed_at": observed_at or ingested_at,
            "lat": lat,
            "lon": lon,
            "narrative": narrative,
            "equipment_type": equipment_type,
            "work_method": work_method,
            "reporter": reporter,
            "contractor": contractor,
            "photos_present": photos_present,
            "audio_present": audio_present,
            "video_present": video_present,
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
        if narrative:
            observations.append(
                {
                    "observation_type": "FIELD_REPORT_PRESENT",
                    "summary": "Field report narrative was provided",
                    "source_id": report_id,
                    "value": narrative,
                }
            )

        quality = self._build_quality(
            raw=raw,
            source_id=report_id,
            missing_fields=missing_fields,
            notes=warnings.copy(),
            confidence=confidence_hint if confidence_hint is not None else 0.65,
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
