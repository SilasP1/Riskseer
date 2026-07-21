# Workflow: Explanation Generation

## Purpose

Use this workflow when the task changes operator/internal explanations, report rows, snapshots, or output wording built from evaluated case truth.

This workflow is for rendering only. It must not become a second logic layer.

## Primary Owner Files

- `explanations.py`
- `case_logic.py`
- `api.py`

## Tool Calls

- `generate_operator_explanation`
- `generate_internal_explanation`
- `build_case_report`
- `build_case_snapshot`
- `load_api_case_contract`

## Steps

1. Confirm the task belongs to wording or rendering rather than evaluation logic.
2. Inspect `explanations.py` first. Inspect `case_logic.py` only if backend summary fields are part of the task. Inspect `api.py` only if payload shape affects presentation.
3. Preserve the distinction between:
   - observed
   - derived
   - inferred
   - assumed
4. Render from existing backend truth. Do not invent missing evidence.
5. Keep explanation formatting in `explanations.py` unless the field is backend truth shared across multiple consumers.
6. Validate by generating or reading real output artifacts.

## Guardrails

- Do not add hidden scoring or policy logic to explanation formatting.
- Do not let frontend-only language replace backend explanation truth.
- Do not blend evidence layers into one unsupported story.
