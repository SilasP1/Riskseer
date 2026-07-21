# Workflow: Decision Posture

## Purpose

Use this workflow when the task changes how Riskseer assigns decision state, urgency, response posture, or lifecycle-adjusted actionability.

This workflow must preserve the distinction between current-state reasoning and lifecycle actionability overrides.

## Primary Owner Files

- `case_evaluation.py`
- `case_logic.py`

## Tool Calls

- `evaluate_case_alignment`
- `evaluate_information_integrity`
- `evaluate_behavioral_risk`
- `compute_uncertainty_burden`
- `determine_failure_layers`
- `determine_decision_state`
- `determine_urgency`
- `determine_response_posture`
- `apply_lifecycle_actionability`
- `apply_lifecycle_decision_state`

## Steps

1. Confirm the task is about decision state, urgency, posture, or lifecycle-adjusted actionability.
2. Inspect `case_evaluation.py` and `case_logic.py`.
3. Keep current-state decision logic in `case_evaluation.py`.
4. Keep lifecycle status normalization and lifecycle actionability overrides in `case_logic.py`.
5. Make the smallest change that preserves current evidence-first reasoning.
6. Confirm that the final action framing still fits Riskseer:
   - STOP
   - VERIFY
   - ESCALATE
   - PROCEED
7. Validate on a repo-local pipeline or evaluation path.

## Guardrails

- Do not move decision logic into `main.py`, `api.py`, or the frontend.
- Do not let lifecycle status erase the underlying evaluated evidence.
- Do not reduce the system to a generic severity ranker.
