"""
ticket_logic.py

GOAL
----
Own ticket-specific temporal and matching utilities.

This file exists to keep ticket validity and ticket relationship helpers out of
event orchestration code. It should stay focused on ticket/time logic and small,
reusable ticket evaluation primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple


def classify_ticket_time_relationship(
    event_time: Optional[datetime],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
) -> Tuple[str, Optional[float]]:
    """
    Returns:
        temporal_state,
        minutes_from_window

    temporal_state:
        - INSIDE_WINDOW
        - BEFORE_WINDOW
        - AFTER_WINDOW
        - UNKNOWN
    """
    if event_time is None or start_time is None or end_time is None:
        return "UNKNOWN", None

    if start_time <= event_time <= end_time:
        return "INSIDE_WINDOW", 0.0

    if event_time < start_time:
        delta_min = (start_time - event_time).total_seconds() / 60.0
        return "BEFORE_WINDOW", delta_min

    delta_min = (event_time - end_time).total_seconds() / 60.0
    return "AFTER_WINDOW", delta_min


def compute_ticket_match_strength(
    inside_area: bool,
    temporal_state: str,
    distance_m: Optional[float],
    radius_m: Optional[float],
) -> float:
    """
    Narrow local heuristic only.
    This is NOT final case scoring.
    """
    score = 0.0

    if inside_area:
        score += 0.6
    elif distance_m is not None and radius_m and radius_m > 0:
        overflow = max(0.0, distance_m - radius_m)
        if overflow <= max(15.0, radius_m * 0.10):
            score += 0.2

    if temporal_state == "INSIDE_WINDOW":
        score += 0.4
    elif temporal_state in {"BEFORE_WINDOW", "AFTER_WINDOW"}:
        score += 0.05

    return max(0.0, min(1.0, score))
