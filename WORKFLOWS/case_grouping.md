# Workflow: Case Grouping

## Purpose

Use this workflow when the task changes how event analyses attach to cases, branch into related cases, or preserve continuity over time.

This workflow is case-first. It must not flatten Riskseer into an event-list system.

## Primary Owner Files

- `case.py`
- `event_logic.py`
- `ticket_logic.py`
- `schemas.py`

## Tool Calls

- `normalize_source_records`
- `classify_event_context`
- `evaluate_event_against_ticket`
- `evaluate_event_against_asset`
- `select_case_attachment_decision`
- `attach_event_to_case`
- `build_case_registry`

## Steps

1. Confirm the task belongs to identity, continuity, attachment, or branching behavior.
2. Inspect `case.py` first, then inspect any upstream event/ticket helpers that feed it.
3. Confirm which parts of the current attachment decision depend on:
   - space
   - time
   - ticket
   - asset
   - continuity windows
4. Keep attachment and branching logic in `case.py`.
5. Use event-local context from `event_logic.py` and ticket-local helpers from `ticket_logic.py`, but do not move case identity decisions there.
6. Preserve stable case identity anchors and seeded prior-case continuity.
7. Prefer the smallest change that preserves existing branching and ambiguity recording behavior.
8. Validate using a repo-local registry build or pipeline path.

## Guardrails

- Do not put final decision-state logic into grouping.
- Do not replace case-first continuity with flat event sorting.
- Do not weaken ambiguity tracking for convenience.
- Do not let the frontend define grouping behavior.
