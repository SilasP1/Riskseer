"""
source_adaptors/positive_response_adapter.py

WHAT THIS FILE DOES
-------------------
1. Adapts raw positive-response / utility-response inputs into normalized record dictionaries.
2. Captures what is known about clearance, response status, responder identity, and timing.
3. Preserves unknown response state as unknown instead of forcing a safe/unsafe conclusion.
4. Records missingness and source quality information.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not decide whether a utility response is sufficient for safe work.
2. It does not treat a response as equivalent to ground truth.
3. It does not group records into cases.
4. It does not assign urgency, decision_state, or response posture.
5. It does not convert absent response data into "not cleared" unless the source explicitly says so.
6. It does not produce final operator-facing explanations.
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


class PositiveResponseAdaptor(BaseSourceAdaptor):
    source_type = "positive_response"

    def adapt(self, raw: Dict[str, Any]) -> AdapterResult:
        warnings: List[str] = []
        errors: List[str] = []
        missing_fields: List[str] = []

        response_id = normalize_text(raw.get("response_id") or raw.get("id") or raw.get("source_id")) or ""
        observed_at = normalize_datetime_str(raw.get("observed_at") or raw.get("timestamp") or raw.get("responded_at"))
        ingested_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        timestamp_label = "Recorded by source" if observed_at else "Logged at ingest (source time missing)"
        ticket_id = normalize_text(raw.get("ticket_id"))

        if not observed_at:
            missing_fields.append("observed_at")
        if not ticket_id:
            missing_fields.append("ticket_id")

        response_status = normalize_text(raw.get("response_status") or raw.get("status"))
        responder = normalize_text(raw.get("responder") or raw.get("utility_name"))
        response_code = normalize_text(raw.get("response_code"))
        clear_to_excavate = normalize_bool(raw.get("clear_to_excavate"))
        complete_response = normalize_bool(raw.get("complete_response"))
        conflict_flag = normalize_bool(raw.get("conflict_flag"))
        confidence_hint = normalize_float(raw.get("confidence"))

        if not response_status:
            warnings.append("Positive response status is unknown.")
        if clear_to_excavate is None:
            warnings.append("Clear-to-excavate field is unknown, not false.")
        if complete_response is None:
            warnings.append("Complete-response field is unknown.")

        completeness = 1.0 - (len(missing_fields) / 2.0)
        completeness = max(0.0, min(1.0, completeness))

        record = {
            "record_type": "positive_response",
            "response_id": response_id,
            "observed_at": observed_at or ingested_at,
            "ticket_id": ticket_id,
            "response_status": response_status,      # explicit unknown allowed
            "responder": responder,
            "response_code": response_code,
            "clear_to_excavate": clear_to_excavate,  # None means unknown
            "complete_response": complete_response,  # None means unknown
            "conflict_flag": conflict_flag,
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
        if response_status:
            observations.append(
                {
                    "observation_type": "POSITIVE_RESPONSE_REPORTED",
                    "summary": "Positive response status was explicitly reported",
                    "source_id": response_id,
                    "value": response_status,
                }
            )

        quality = self._build_quality(
            raw=raw,
            source_id=response_id,
            missing_fields=missing_fields,
            notes=warnings.copy(),
            confidence=confidence_hint if confidence_hint is not None else 0.75,
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
