"""Shared contracts and conservative normalizers for source adaptors.

This module deliberately does not interpret source meaning. Concrete adaptors
preserve source claims and missingness; case evaluation owns operational truth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SourceQuality:
    source_type: str
    source_id: str
    confidence: Optional[float] = None
    freshness: Optional[float] = None
    completeness: Optional[float] = None
    missing_fields: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    raw_keys: List[str] = field(default_factory=list)


@dataclass
class AdapterResult:
    records: List[Dict[str, Any]] = field(default_factory=list)
    observations: List[Dict[str, Any]] = field(default_factory=list)
    quality: Optional[SourceQuality] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def normalize_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def normalize_float(value: Any) -> Optional[float]:
    text = normalize_text(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    text = normalize_text(value)
    if text is None:
        return None
    normalized = text.lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False
    return None


def normalize_datetime_str(value: Any) -> Optional[str]:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = normalize_text(value)
        if text is None:
            return None
        candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None

    normalized = parsed.isoformat()
    return normalized[:-6] + "Z" if normalized.endswith("+00:00") else normalized


class BaseSourceAdaptor(ABC):
    source_type = "unknown"

    @abstractmethod
    def adapt(self, raw: Dict[str, Any]) -> AdapterResult:
        raise NotImplementedError

    def _build_quality(
        self,
        *,
        raw: Dict[str, Any],
        source_id: str,
        missing_fields: List[str],
        notes: List[str],
        confidence: Optional[float],
        freshness: Optional[float],
        completeness: Optional[float],
    ) -> SourceQuality:
        return SourceQuality(
            source_type=self.source_type,
            source_id=source_id,
            confidence=confidence,
            freshness=freshness,
            completeness=completeness,
            missing_fields=list(missing_fields),
            notes=list(notes),
            raw_keys=sorted(str(key) for key in raw),
        )
