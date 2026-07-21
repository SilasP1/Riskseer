# Riskseer Tool Definitions

## Purpose

These tools are WAT interfaces over the existing Riskseer codebase.

They are not a second logic layer. Each tool maps directly to current repo code or to a thin composition of existing repo logic.

If a tool and the code diverge, the code wins and the tool definition must be updated.

---

## Tool Catalog

### `normalize_source_records`

- Type: direct
- Owner files:
  - `event_logic.py`
- Current function mapping:
  - `normalize_event_records`
  - `normalize_ticket_records`
  - `normalize_asset_records`
  - `normalize_field_report_records`
  - `normalize_marking_records`
  - `normalize_positive_response_records`
- Purpose:
  convert raw source rows into canonical Riskseer records
- Must not:
  perform case logic or final evaluation

### `evaluate_event_against_ticket`

- Type: composite
- Owner files:
  - `ticket_logic.py`
  - `event_logic.py`
- Current function mapping:
  - `classify_ticket_time_relationship`
  - `compute_ticket_match_strength`
  - `analyze_event_ticket_relationship`
- Purpose:
  compute narrow event-to-ticket temporal and spatial relationship data
- Must not:
  assign final case decision truth

### `evaluate_event_against_asset`

- Type: direct
- Owner files:
  - `event_logic.py`
- Current function mapping:
  - `analyze_event_asset_relationship`
- Purpose:
  compute narrow event-to-asset proximity data
- Must not:
  assign final case decision truth

### `classify_event_context`

- Type: direct
- Owner files:
  - `event_logic.py`
- Current function mapping:
  - `analyze_single_event`
  - `analyze_events`
- Purpose:
  produce event-local observations, candidate ticket IDs, candidate asset IDs, and relationship metadata
- Must not:
  own case continuity

### `select_case_attachment_decision`

- Type: direct
- Owner files:
  - `case.py`
- Current function mapping:
  - `select_best_case_decision`
- Purpose:
  decide attach vs weak attach vs branch vs new case for an analyzed event
- Must not:
  assign case decision posture

### `attach_event_to_case`

- Type: composite
- Owner files:
  - `case.py`
- Current function mapping:
  - `attach_event_analysis_to_case`
  - `add_analysis_to_registry`
- Purpose:
  apply the attachment/branch/new-case decision to the registry
- Must not:
  own current-state evaluation

### `build_case_registry`

- Type: direct
- Owner files:
  - `case.py`
- Current function mapping:
  - `build_case_registry_from_analyses`
- Purpose:
  build a case registry from analyzed events and seeded prior cases
- Must not:
  assign decision state or explanation text

### `build_evidence_layers`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `build_evidence_layers`
- Purpose:
  construct observed / derived / inferred / assumed evidence layers
- Must not:
  collapse those layers

### `evaluate_case_alignment`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `evaluate_alignment`
- Purpose:
  assess spatial, temporal, ticket, and asset alignment for the current case

### `evaluate_information_integrity`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `evaluate_information_integrity`
- Purpose:
  assess completeness/coherence of available support for the current case

### `evaluate_behavioral_risk`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `evaluate_behavioral_risk`
- Purpose:
  assess repeated activity, escalation, and habit-like continuation signals

### `compute_uncertainty_burden`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `compute_uncertainty_burden`
- Purpose:
  combine current structured assessments into uncertainty burden

### `determine_failure_layers`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `determine_failure_layers`
- Purpose:
  assign current failure layers from evaluated case state

### `determine_decision_state`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `determine_decision_state`
- Purpose:
  assign current decision state from evaluated case truth

### `determine_urgency`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `determine_urgency`
- Purpose:
  assign urgency from current evaluated case truth

### `determine_response_posture`

- Type: direct
- Owner files:
  - `case_evaluation.py`
- Current function mapping:
  - `determine_response_posture`
- Purpose:
  assign current response posture from evaluated case truth

### `apply_lifecycle_actionability`

- Type: direct
- Owner files:
  - `case_logic.py`
- Current function mapping:
  - `apply_lifecycle_actionability`
  - `apply_lifecycle_decision_state`
- Purpose:
  adapt current-state actionability based on lifecycle status
- Must not:
  erase the underlying current-state evidence

### `orchestrate_case_evaluation`

- Type: direct
- Owner files:
  - `case_logic.py`
- Current function mapping:
  - `evaluate_case`
  - `evaluate_cases`
  - `evaluate_registry_in_place`
- Purpose:
  orchestrate current-state and temporal case evaluation end to end
- Must not:
  absorb grouping logic

### `load_prior_case_state`

- Type: composite
- Owner files:
  - `main.py`
- Current function mapping:
  - `load_prior_registry_payload`
  - `build_prior_case_records`
  - `load_prior_trend_history`
  - `build_prior_case_index`
- Purpose:
  load the prior saved state needed for continuity and temporal comparison

### `build_case_state_snapshot`

- Type: direct
- Owner files:
  - `case_temporal.py`
- Current function mapping:
  - `build_case_state_snapshot`
- Purpose:
  create a compact current-state snapshot for temporal comparison

### `extract_prior_snapshot`

- Type: direct
- Owner files:
  - `case_temporal.py`
- Current function mapping:
  - `extract_prior_snapshot`
- Purpose:
  extract comparable prior-state data from saved outputs

### `detect_case_drift`

- Type: direct
- Owner files:
  - `case_temporal.py`
- Current function mapping:
  - `build_temporal_change_summary`
- Purpose:
  classify temporal change and produce deltas between current and prior state

### `compute_investigation_roi`

- Type: direct
- Owner files:
  - `case_temporal.py`
- Current function mapping:
  - `compute_investigation_roi`
- Purpose:
  compute investigation priority from current-state and temporal context

### `generate_operator_explanation`

- Type: direct
- Owner files:
  - `explanations.py`
- Current function mapping:
  - `build_operator_explanation`
- Purpose:
  render operator-facing explanation from existing backend truth

### `generate_internal_explanation`

- Type: direct
- Owner files:
  - `explanations.py`
- Current function mapping:
  - `build_internal_explanation`
- Purpose:
  render internal explanation from existing backend truth

### `build_case_report`

- Type: direct
- Owner files:
  - `explanations.py`
- Current function mapping:
  - `build_case_report_rows`
  - `build_case_snapshot`
- Purpose:
  render compact case output artifacts from existing backend truth

### `audit_case_outputs`

- Type: direct
- Owner files:
  - `case_audit.py`
- Current function mapping:
  - `build_audit_payload`
  - `build_audit_text`
- Purpose:
  audit temporal and summary integrity from already-evaluated cases

### `load_api_case_contract`

- Type: direct
- Owner files:
  - `api.py`
- Current function mapping:
  - `normalize_case`
  - `load_cases`
- Purpose:
  project saved backend outputs into the frontend/API contract
- Must not:
  become a second evaluator

---

## Tool Rules

All tools must preserve:

- deterministic behavior
- case-first architecture
- evidence-layer separation
- ownership boundaries

No tool may:

- move backend truth into the frontend
- invent a new logic layer outside the owning file
- collapse observed / derived / inferred / assumed
