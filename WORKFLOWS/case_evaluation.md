# Workflow: Case Evaluation

## Purpose

Use this workflow when the task changes how Riskseer evaluates the current state of a case.

This workflow is for current-state reasoning only. It does not own grouping or prior-state comparison.

## Primary Owner Files

- `case_evaluation.py`
- `case_logic.py`
- `schemas.py`

## Tool Calls

- `build_evidence_layers`
- `evaluate_case_alignment`
- `evaluate_information_integrity`
- `evaluate_behavioral_risk`
- `compute_uncertainty_burden`
- `determine_failure_layers`
- `determine_decision_state`
- `determine_urgency`
- `determine_response_posture`
- `orchestrate_case_evaluation`

## Steps

1. Confirm the task belongs to current-state evaluation and not to case grouping, temporal comparison, explanation rendering, or frontend presentation.
2. Inspect `case_evaluation.py`, `case_logic.py`, and any touched schema definitions.
3. Build or inspect the evidence layers first.
   Keep observed, derived, inferred, and assumed separate.
4. Evaluate alignment, information integrity, and behavioral risk from the current case as it exists now.
5. Compute uncertainty burden from those structured assessments.
6. Determine failure layers from the current state.
7. Determine decision state, urgency, and response posture from current-state truth.
8. Let `case_logic.py` orchestrate the evaluated output back onto the case.
9. Validate using a repo-local evaluation or pipeline path.

## Guardrails

- Do not move grouping logic into this workflow.
- Do not move temporal drift logic into this workflow.
- Do not let explanation wording replace structured evidence.
- Do not collapse evidence layers for convenience.
