"""
schemas.py

GOAL
----
This file defines the canonical internal data contracts for Riskseer.

These schemas exist to keep the system stable as new data sources are added.
Raw source data should be translated into these records before it reaches
grouping, evaluation, or explanation layers.

WHAT THIS FILE DOES
-------------------
1. Defines enums used across the engine.
2. Defines canonical record types for:
   - events
   - tickets
   - assets
   - field reports
   - marking records
   - positive response records
3. Defines shared quality / provenance structures.
4. Defines observations, evidence layers, and case evaluation records.
5. Defines case identity, attachment assessment, conflict structures,
   case containers, and registry helpers.

WHAT THIS FILE DOES NOT DO
--------------------------
1. It does not parse raw source files.
2. It does not normalize raw source payloads.
3. It does not assign decision_state, urgency, or response posture.
4. It does not group events into cases.
5. It does not evaluate operational risk.
6. It does not generate operator-facing explanations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================
# ENUMS
# ============================================================

class DecisionState(str, Enum):
    SAFE_TO_PROCEED = "SAFE_TO_PROCEED"
    PROCEED_WITH_VERIFICATION = "PROCEED_WITH_VERIFICATION"
    HIGH_RISK_OF_MISJUDGMENT = "HIGH_RISK_OF_MISJUDGMENT"
    STOP_WORK = "STOP_WORK"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class UrgencyLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResponsePosture(str, Enum):
    MONITOR = "MONITOR"
    VERIFY = "VERIFY"
    VERIFY_BEFORE_PROCEEDING = "VERIFY_BEFORE_PROCEEDING"
    ESCALATE = "ESCALATE"
    HOLD_WORK = "HOLD_WORK"


class EvidenceKind(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"


class FailureLayer(str, Enum):
    AUTHORIZATION_AMBIGUITY = "AUTHORIZATION_AMBIGUITY"
    PROCESS_BYPASS_OR_GAP = "PROCESS_BYPASS_OR_GAP"
    HABIT_CONTINUATION = "HABIT_CONTINUATION"
    LIMITED_VISIBILITY_WORK = "LIMITED_VISIBILITY_WORK"
    CONTEXT_LIMITATION = "CONTEXT_LIMITATION"
    CHANGING_SITE_CONDITIONS = "CHANGING_SITE_CONDITIONS"


class ResponsibilityLayerState(str, Enum):
    STRONG = "STRONG"
    WEAK = "WEAK"
    UNKNOWN = "UNKNOWN"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"


class DecisionSupportState(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    DEGRADED = "DEGRADED"
    CONFLICTED = "CONFLICTED"


class DecisionRiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionDefensibilityState(str, Enum):
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class ObservationType(str, Enum):
    EVENT_SEEN = "EVENT_SEEN"
    NEAR_ASSET = "NEAR_ASSET"
    FAR_FROM_ASSET = "FAR_FROM_ASSET"
    INSIDE_TICKET_AREA = "INSIDE_TICKET_AREA"
    OUTSIDE_TICKET_AREA = "OUTSIDE_TICKET_AREA"
    INSIDE_TICKET_WINDOW = "INSIDE_TICKET_WINDOW"
    OUTSIDE_TICKET_WINDOW = "OUTSIDE_TICKET_WINDOW"
    NO_MATCHING_TICKET = "NO_MATCHING_TICKET"
    MULTIPLE_POSSIBLE_TICKETS = "MULTIPLE_POSSIBLE_TICKETS"
    HEAVY_EQUIPMENT_INDICATOR = "HEAVY_EQUIPMENT_INDICATOR"
    TRENCHLESS_INDICATOR = "TRENCHLESS_INDICATOR"
    REPEATED_ACTIVITY = "REPEATED_ACTIVITY"
    ESCALATING_ACTIVITY = "ESCALATING_ACTIVITY"
    DATA_GAP = "DATA_GAP"
    STALE_CONTEXT = "STALE_CONTEXT"

    FIELD_REPORT_PRESENT = "FIELD_REPORT_PRESENT"
    MARKING_STATE_REPORTED = "MARKING_STATE_REPORTED"
    POSITIVE_RESPONSE_REPORTED = "POSITIVE_RESPONSE_REPORTED"


class SourceRecordType(str, Enum):
    EVENT = "event"
    TICKET = "ticket"
    ASSET = "asset"
    FIELD_REPORT = "field_report"
    MARKING = "marking"
    POSITIVE_RESPONSE = "positive_response"


class ConflictType(str, Enum):
    SPATIAL_CONFLICT = "SPATIAL_CONFLICT"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    PROCESS_CONFLICT = "PROCESS_CONFLICT"
    AUTHORIZATION_CONFLICT = "AUTHORIZATION_CONFLICT"
    MARKING_CONFLICT = "MARKING_CONFLICT"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


# ============================================================
# SHARED QUALITY / PROVENANCE
# ============================================================

@dataclass
class SourceContext:
    """
    Shared source/provenance metadata for canonical records.
    """
    source_type: str
    source_id: str = ""
    observed_at: Optional[str] = None
    ingested_at: Optional[str] = None
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataQuality:
    """
    Quality of the record as ingested, not safety of the real-world situation.
    """
    confidence: Optional[float] = None
    freshness: Optional[float] = None
    completeness: Optional[float] = None
    missing_fields: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


# ============================================================
# CANONICAL SOURCE RECORDS
# ============================================================

@dataclass
class EventRecord:
    event_id: str
    event_time: str
    lat: float
    lon: float
    source: str
    intensity: Optional[float] = None
    event_type: Optional[str] = None
    equipment_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


@dataclass
class TicketRecord:
    ticket_id: str
    start_time: str
    end_time: str
    center_lat: float
    center_lon: float
    radius_m: float
    contractor: Optional[str] = None
    work_type: Optional[str] = None
    status: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


@dataclass
class AssetRecord:
    asset_id: str
    asset_type: str
    lat: float
    lon: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


@dataclass
class FieldReportRecord:
    """
    Canonical field report / patrol note / manual observation record.

    Unknown fields remain None. Missing is not equivalent to false.
    """
    report_id: str
    observed_at: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    narrative: Optional[str] = None
    equipment_type: Optional[str] = None
    work_method: Optional[str] = None
    reporter: Optional[str] = None
    contractor: Optional[str] = None
    photos_present: Optional[bool] = None
    audio_present: Optional[bool] = None
    video_present: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


@dataclass
class MarkingRecord:
    """
    Canonical marking / locate record.

    Explicitly preserves unknown marking state instead of converting it into
    a negative conclusion.
    """
    marking_id: str
    observed_at: Optional[str]
    lat: Optional[float]
    lon: Optional[float]
    ticket_id: Optional[str] = None
    utility_name: Optional[str] = None
    marking_state: Optional[str] = None
    locate_status: Optional[str] = None
    mark_type: Optional[str] = None
    last_marked_at: Optional[str] = None
    last_refreshed_at: Optional[str] = None
    mark_confidence: Optional[float] = None
    refresh_required: Optional[bool] = None
    partial_marks: Optional[bool] = None
    clearly_visible: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


@dataclass
class PositiveResponseRecord:
    """
    Canonical positive response / utility response record.

    Unknown response state remains unknown. It is not automatically treated
    as not cleared or cleared.
    """
    response_id: str
    observed_at: Optional[str]
    ticket_id: Optional[str]
    response_status: Optional[str] = None
    responder: Optional[str] = None
    response_code: Optional[str] = None
    clear_to_excavate: Optional[bool] = None
    complete_response: Optional[bool] = None
    conflict_flag: Optional[bool] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_context: Optional[SourceContext] = None
    quality: DataQuality = field(default_factory=DataQuality)


# ============================================================
# OBSERVATIONS / EVIDENCE
# ============================================================

@dataclass
class Observation:
    observation_type: ObservationType
    summary: str
    event_id: Optional[str] = None
    ticket_id: Optional[str] = None
    asset_id: Optional[str] = None
    field_report_id: Optional[str] = None
    marking_id: Optional[str] = None
    response_id: Optional[str] = None
    value: Optional[Any] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceItem:
    kind: EvidenceKind
    statement: str
    source_ids: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceLayers:
    observed: List[EvidenceItem] = field(default_factory=list)
    derived: List[EvidenceItem] = field(default_factory=list)
    inferred: List[EvidenceItem] = field(default_factory=list)
    assumed: List[EvidenceItem] = field(default_factory=list)


# ============================================================
# CASE IDENTITY / ATTACHMENT / CONFLICT CONTRACTS
# ============================================================

@dataclass
class CaseIdentity:
    """
    Stable case identity contract.

    This is the anchor definition of what the case fundamentally is.
    It should be set early and changed rarely.
    """
    anchor_event_id: Optional[str] = None
    anchor_time: Optional[str] = None
    anchor_lat: Optional[float] = None
    anchor_lon: Optional[float] = None

    primary_ticket_ids: List[str] = field(default_factory=list)
    primary_asset_ids: List[str] = field(default_factory=list)

    identity_confidence: Optional[float] = None
    summary: str = ""


@dataclass
class AttachmentAssessment:
    """
    Canonical attachment-fit record.

    This lets grouping/attachment code record why something was attached,
    how strong the fit was, and whether it is identity-consistent or merely
    contextual.
    """
    allowed: bool = False
    reason: str = ""

    spatial_fit: Optional[float] = None
    temporal_fit: Optional[float] = None
    ticket_fit: Optional[float] = None
    asset_fit: Optional[float] = None

    identity_consistent: Optional[bool] = None
    context_only: Optional[bool] = None

    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceConflict:
    """
    Explicit conflict record for contradictory or destabilizing signals.
    """
    conflict_type: ConflictType
    summary: str
    source_ids: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# CASE ATTACHMENTS / LINKS
# ============================================================

@dataclass
class CaseAttachment:
    record_type: str
    record_id: str
    role: Optional[str] = None
    attached_at: Optional[str] = None
    assessment: Optional[AttachmentAssessment] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# CASE EVALUATION DIMENSIONS
# ============================================================

@dataclass
class AlignmentAssessment:
    spatial_alignment: Optional[float] = None
    temporal_alignment: Optional[float] = None
    ticket_match_strength: Optional[float] = None
    asset_relevance: Optional[float] = None
    summary: str = ""
    concerns: List[str] = field(default_factory=list)


@dataclass
class InformationIntegrityAssessment:
    ticket_quality: DataQuality = field(default_factory=DataQuality)
    asset_quality: DataQuality = field(default_factory=DataQuality)
    event_quality: DataQuality = field(default_factory=DataQuality)
    field_report_quality: DataQuality = field(default_factory=DataQuality)
    marking_quality: DataQuality = field(default_factory=DataQuality)
    positive_response_quality: DataQuality = field(default_factory=DataQuality)
    overall_confidence: Optional[float] = None
    summary: str = ""
    concerns: List[str] = field(default_factory=list)


@dataclass
class BehavioralRiskAssessment:
    repeated_activity: bool = False
    escalating_activity: bool = False
    conflicting_signals_ignored: bool = False
    habit_risk: Optional[float] = None
    summary: str = ""
    concerns: List[str] = field(default_factory=list)


@dataclass
class ResponsibilityLayerAssessment:
    state: ResponsibilityLayerState = ResponsibilityLayerState.UNKNOWN
    reason: str = ""
    confidence: Optional[float] = None
    observed_facts: List[str] = field(default_factory=list)
    derived_facts: List[str] = field(default_factory=list)
    missing_facts: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)


@dataclass
class DecisionSupportIntegrity:
    state: DecisionSupportState = DecisionSupportState.DEGRADED
    decision_risk: DecisionRiskLevel = DecisionRiskLevel.MODERATE
    recommended_posture: ResponsePosture = ResponsePosture.VERIFY
    reason: str = ""
    confidence: Optional[float] = None


@dataclass
class ResponsibilityIntegrityBundle:
    layers: Dict[str, ResponsibilityLayerAssessment] = field(default_factory=dict)
    decision_support_integrity: DecisionSupportIntegrity = field(default_factory=DecisionSupportIntegrity)
    failure_propagation: List[str] = field(default_factory=list)


@dataclass
class DecisionDefensibilityEvaluation:
    state: DecisionDefensibilityState = DecisionDefensibilityState.MODERATE
    decision_risk: DecisionRiskLevel = DecisionRiskLevel.MODERATE
    reason: str = ""
    components: Dict[str, str] = field(default_factory=dict)
    key_weaknesses: List[str] = field(default_factory=list)
    defensible_decision: str = ""


@dataclass
class CaseEvaluation:
    decision_state: DecisionState = DecisionState.NEEDS_REVIEW
    urgency: UrgencyLevel = UrgencyLevel.MODERATE
    response_posture: ResponsePosture = ResponsePosture.VERIFY

    confidence: Optional[float] = None
    uncertainty_burden: Optional[float] = None

    alignment: AlignmentAssessment = field(default_factory=AlignmentAssessment)
    information_integrity: InformationIntegrityAssessment = field(default_factory=InformationIntegrityAssessment)
    behavioral_risk: BehavioralRiskAssessment = field(default_factory=BehavioralRiskAssessment)
    responsibility_integrity: ResponsibilityIntegrityBundle = field(default_factory=ResponsibilityIntegrityBundle)
    decision_defensibility: DecisionDefensibilityEvaluation = field(default_factory=DecisionDefensibilityEvaluation)

    evidence_layers: EvidenceLayers = field(default_factory=EvidenceLayers)
    failure_layers: List[FailureLayer] = field(default_factory=list)
    conflicts: List[EvidenceConflict] = field(default_factory=list)

    why_now: List[str] = field(default_factory=list)
    what_changed: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)

    operator_summary: str = ""
    internal_summary: str = ""


# ============================================================
# CASE RECORD
# ============================================================

@dataclass
class CaseRecord:
    case_id: str
    created_at: str
    updated_at: str

    status: str = "OPEN"

    identity: CaseIdentity = field(default_factory=CaseIdentity)

    event_ids: List[str] = field(default_factory=list)

    # Legacy/general reference lists currently used by the pipeline.
    # Keep these for compatibility while moving behavior toward explicit
    # identity vs context separation.
    ticket_ids: List[str] = field(default_factory=list)
    asset_ids: List[str] = field(default_factory=list)

    # Explicit contextual references that are attached to the case but are
    # not necessarily part of its defining identity.
    context_ticket_ids: List[str] = field(default_factory=list)
    context_asset_ids: List[str] = field(default_factory=list)

    field_report_ids: List[str] = field(default_factory=list)
    marking_ids: List[str] = field(default_factory=list)
    positive_response_ids: List[str] = field(default_factory=list)

    attachments: List[CaseAttachment] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)

    evaluation: CaseEvaluation = field(default_factory=CaseEvaluation)
    responsibility_integrity: ResponsibilityIntegrityBundle = field(default_factory=ResponsibilityIntegrityBundle)
    decision_defensibility: DecisionDefensibilityEvaluation = field(default_factory=DecisionDefensibilityEvaluation)

    parent_case_id: Optional[str] = None
    forked_from_case_id: Optional[str] = None
    lineage_notes: List[str] = field(default_factory=list)

    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# REGISTRY / PIPELINE OUTPUT HELPERS
# ============================================================

@dataclass
class CaseRegistry:
    cases: List[CaseRecord] = field(default_factory=list)
    next_case_number: int = 1


@dataclass
class PipelineSnapshot:
    generated_at: str
    total_events: int = 0
    total_tickets: int = 0
    total_assets: int = 0
    total_field_reports: int = 0
    total_markings: int = 0
    total_positive_responses: int = 0
    total_cases: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
