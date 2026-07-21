# Workflow: OpenAI Investigator

## Purpose

Use this workflow when changing the optional AI-generated case brief. The
investigator explains saved case truth; it does not evaluate, regroup, or
authorize a case.

## Primary Owner Files

- `investigator.py`
- `api.py`

## Tool Calls

- `get_case_decision`
- `get_case_evidence`
- `get_case_change`
- `investigate_saved_case`

## Steps

1. Load a normalized, already-evaluated API case.
2. Build a bounded citation catalog without combining observed, derived,
   inferred, and assumed layers.
3. Give one agent read-only access to decision, evidence, and temporal tools.
4. Require typed structured output and at least one valid citation per finding.
5. Copy official decision, urgency, and posture from the backend after model
   execution; never accept those values from model output.
6. Reject invented citation IDs and return an explicit API error.
7. Validate without a live key using catalog/finalization tests. Treat a live
   model call as a separate environment validation.

## Guardrails

- Do not let model output mutate a case or become backend decision truth.
- Do not expose raw files, unrestricted retrieval, write tools, or shell tools.
- Do not infer blame, liability, clearance, or legal conclusions.
- Do not store or commit an API key.
