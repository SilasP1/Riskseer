"""
source_adaptors/__init__.py

WHAT THIS FILE DOES
-------------------
1. Exposes the public adaptor interface for the source_adaptors package.
2. Re-exports shared base types and helper functions.
3. Re-exports concrete source adaptors.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not parse raw source data itself.
2. It does not normalize records directly.
3. It does not make any decisions about case grouping, evaluation, or urgency.
4. It does not contain source-specific business logic.
"""

from .base import (
    AdapterResult,
    BaseSourceAdaptor,
    SourceQuality,
    normalize_bool,
    normalize_datetime_str,
    normalize_float,
    normalize_text,
)

from .field_reports_adapter import FieldReportAdaptor
from .marking_adapter import MarkingAdaptor
from .positive_response_adapter import PositiveResponseAdaptor

__all__ = [
    "AdapterResult",
    "BaseSourceAdaptor",
    "SourceQuality",
    "normalize_bool",
    "normalize_datetime_str",
    "normalize_float",
    "normalize_text",
    "FieldReportAdaptor",
    "MarkingAdaptor",
    "PositiveResponseAdaptor",
]