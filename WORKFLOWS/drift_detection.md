# Workflow: Drift Detection

## Purpose

Use this workflow when the task changes how Riskseer compares current case state to prior saved state, detects trend, or computes temporal change.

This workflow is about prior-vs-current comparison only.

## Primary Owner Files

- `main.py`
- `case_temporal.py`
- `case_logic.py`

## Tool Calls

- `load_prior_case_state`
- `build_case_state_snapshot`
- `extract_prior_snapshot`
- `detect_case_drift`
- `compute_investigation_roi`
- `orchestrate_case_evaluation`
- `audit_case_outputs`

## Steps

1. Confirm the task belongs to prior-state loading, trend detection, temporal deltas, or ROI.
2. Inspect `main.py`, `case_temporal.py`, and `case_logic.py`.
3. Confirm how prior saved state currently enters the run.
4. Build or inspect the current state snapshot without re-running grouping logic.
5. Extract the prior snapshot from saved outputs.
6. Compare current and prior state to classify trend and compute change metadata.
7. Compute investigation ROI from current-state plus temporal context.
8. Store temporal metadata back onto the case through `case_logic.py`.
9. Run audit checks if the change affects trend, posture shift, hidden risk, or UI summary consistency.

## Guardrails

- Do not recreate current-state evaluation in this workflow.
- Do not fabricate trend when no prior state exists.
- Do not move prior-state logic into the frontend.
