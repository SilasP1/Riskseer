# AGENTS.md

## Holy Grail

The holy grail of work in this repository is a WAT-style operating system:

- Workflows: markdown-based natural language processes derived from the real Riskseer codebase
- Agent: an orchestrator that selects workflows and calls tools, but does not contain core decision logic
- Tools: interfaces that map directly to existing Riskseer logic or required repo-local functions

This WAT system must fit the current Riskseer architecture. It must not invent a new one.

Riskseer is a case-first decision-integrity system for excavation/compliance triage. Its job is to detect when work still looks normal but the support for continuing is weak, stale, partial, conflicting, or degraded.

It is not:

- a generic dashboard
- a broad enterprise job-ranking product
- a vague AI insight layer
- a UI-led analytics system

---

## Inferred Current Architecture

The current codebase implements this flow:

1. `main.py` loads CSV inputs and prior saved state.
2. `event_logic.py` normalizes raw rows into canonical records.
3. `event_logic.py` performs event-local interpretation against ticket/asset context and emits observations plus candidate references.
4. `case.py` groups event analyses into stable cases, preserving identity, continuity, and branching behavior.
5. `case_evaluation.py` evaluates the current state of each case and builds explicit evidence layers:
   - observed
   - derived
   - inferred
   - assumed
6. `case_temporal.py` compares current case state to prior saved state and determines trend, deltas, hidden-risk change, and investigation ROI.
7. `case_logic.py` orchestrates current-state plus temporal outputs, applies lifecycle actionability, and stores evaluation metadata back onto each case.
8. `explanations.py` renders readable operator/internal explanations and report rows from already-computed case truth.
9. `main.py` writes output artifacts.
10. `api.py` and `lookup_case.py` read saved outputs without re-running evaluation.
11. `Riskseer Frontend/src/App.jsx` consumes API case objects and presents queue, overview, and case-detail flows.

Supporting layers:

- `ticket_logic.py` holds ticket time-window and local ticket-match helpers used by `event_logic.py`
- `case_audit.py` audits already-generated temporal/UI-summary consistency from saved case outputs

---

## How The Current System Works

### Case identity and continuity

Case identity and continuity are currently owned by `case.py`.

The repo already uses:

- anchor event, time, and coordinates
- primary ticket and asset IDs
- case seeding from prior saved cases
- continuity windows, inactivity timeouts, reopen thresholds
- attach vs weak attach vs branch vs new-case decisions
- ambiguity flags and family relationships

Do not move this behavior out of `case.py`.

### Current evaluation

Current evaluation is split between:

- `case_evaluation.py`:
  alignment, information integrity, behavioral risk, uncertainty burden, failure layers, decision state, urgency, response posture, and explicit evidence layers
- `case_logic.py`:
  orchestration of evaluation outputs, lifecycle actionability overrides, backend summaries, and metadata packaging

### Temporal change and drift

Temporal comparison is split between:

- `main.py`:
  loading prior saved state
- `case_temporal.py`:
  state snapshots, prior-snapshot extraction, trend classification, hidden-risk delta, ROI, and change summaries
- `case_logic.py`:
  wiring temporal outputs into the evaluated case

### Output and presentation

- `explanations.py` renders human-readable text from structured backend truth
- `api.py` normalizes saved outputs to the frontend contract
- `lookup_case.py` provides read-only inspection
- `Riskseer Frontend/src/App.jsx` presents queue/overview/case UI

---

## Actual File Responsibilities

These responsibilities are mandatory.

### `main.py`
Owns orchestration only.

Allowed:

- load inputs
- load prior saved registry/trend state
- call normalization, event analysis, case registry build, evaluation, explanation, and audit paths
- write outputs
- archive/clear processed inputs
- print run summaries

Forbidden:

- case grouping logic
- evaluation policy
- scoring logic
- explanation wording policy
- UI logic

### `ticket_logic.py`
Owns ticket-specific local utilities.

Allowed:

- ticket time-window classification
- ticket local match-strength helpers
- ticket-only relationship utilities

Forbidden:

- case grouping
- whole-event orchestration
- case scoring
- explanation generation

### `event_logic.py`
Owns event normalization and event-local interpretation.

Allowed:

- normalize raw events, tickets, and assets
- compute event-to-ticket relationships
- compute event-to-asset relationships
- emit observations
- emit candidate ticket and asset IDs
- emit event-local repeat/escalation indicators

Forbidden:

- case continuity
- final case posture or urgency
- operator-facing explanation logic

### `case.py`
Owns case identity, continuity, attachment, branching, and registry behavior.

Allowed:

- create/update/seed/sort cases
- preserve stable identity anchors
- decide attach vs weak attach vs branch vs new case
- manage ambiguity flags, attachment metadata, family links, and lifecycle state

Forbidden:

- decision-state logic
- urgency logic
- response-posture logic
- polished operator wording

### `case_evaluation.py`
Owns current-state case reasoning.

Allowed:

- build evidence layers
- evaluate alignment
- evaluate information integrity
- evaluate behavioral risk
- compute uncertainty burden
- determine failure layers
- determine decision state
- determine urgency
- determine response posture

Forbidden:

- case grouping
- prior-state comparison
- explanation rendering

### `case_temporal.py`
Owns prior-vs-current case comparison.

Allowed:

- build state snapshots
- extract prior snapshots
- classify trend
- compute temporal deltas
- compute hidden-risk temporal assessment
- compute investigation ROI

Forbidden:

- case grouping
- raw input parsing
- re-running current-state logic from scratch
- explanation rendering

### `case_logic.py`
Owns orchestration of case evaluation outputs.

Allowed:

- call current-state and temporal layers
- apply lifecycle actionability overrides
- compose backend summaries and metadata from structured evaluation outputs
- store snapshots/trend metadata back onto each case

Forbidden:

- raw CSV parsing
- case grouping
- becoming a dumping ground for presentation-only convenience logic

### `explanations.py`
Owns wording/rendering of already-computed backend truth.

Allowed:

- operator explanation rendering
- internal explanation rendering
- report-row rendering
- snapshot rendering
- evidence-layer rendering

Forbidden:

- evaluation logic
- hidden policy decisions
- inventing evidence
- collapsing observed/derived/inferred/assumed into one blended explanation

### `case_audit.py`
Owns audit checks over already-generated backend outputs.

Allowed:

- temporal/UI-summary integrity audits
- audit payload generation
- audit text generation

Forbidden:

- mutating case truth
- becoming a second evaluator

### `api.py`
Owns read-only API normalization from saved outputs to frontend shape.

Allowed:

- read registry/report outputs
- normalize case payload shape
- preserve backend truth in the API contract

Forbidden:

- re-evaluating cases
- overriding backend posture/urgency/trend/failure semantics
- becoming the source of truth for prioritization logic

### `lookup_case.py`
Owns read-only inspection of saved outputs.

Allowed:

- load outputs
- search/filter/sort for inspection
- render case detail from saved truth

Forbidden:

- re-evaluating cases
- mutating outputs
- introducing replacement business logic

### `Riskseer Frontend/src/App.jsx`
Owns presentation and interaction flow only.

Allowed:

- summarize
- filter
- sort for viewing convenience
- organize queue, overview, and case detail
- highlight backend-provided results

Forbidden:

- defining backend truth
- overriding backend decision state, urgency, posture, trend, or failure layers
- becoming the source of truth for hidden-risk or decision-validity logic
- collapsing evidence layers into one opaque frontend-only reasoning blob

---

## Actual Mismatches And Risks In The Current Repo

These are current architecture risks inferred from the code, not assumptions.

1. `Riskseer Frontend/src/App.jsx` contains substantial client-side derivation and prioritization logic. It mostly organizes backend truth, but it pressures the "no UI-owned logic" boundary.
2. `case_logic.py` contains backend-facing summary wording helpers such as `build_ui_summary` and `build_operator_summary`. That is acceptable only if treated as backend truth shared across consumers, not UI copy.
3. `api.py` performs fallback selection and normalization across saved output shapes. That is acceptable only as a read-only shape adapter.
4. `lookup_case.py` has inspection-only sorting and search helpers. Those must remain inspection helpers and not become replacement business logic.

Evidence-layer status:

- The backend preserves observed / derived / inferred / assumed in `case_evaluation.py` and `explanations.py`.
- The frontend reads those layers, but also generates additional presentation framing. That framing must not replace backend evidence-layer truth.

---

## WAT System For Riskseer

### Agent

The Agent is the orchestrator.

The Agent may:

- read repo state
- choose a workflow from `WORKFLOWS/`
- call tools defined in `TOOLS/`
- coordinate implementation and validation

The Agent must not:

- invent new evaluation logic outside owning files
- become a second scoring engine
- treat workflow prose as executable business logic

### Workflows

Workflows are markdown-based natural language processes stored in `WORKFLOWS/`.

They must:

- describe how Riskseer work should proceed using the existing codebase
- call tools that map directly to existing logic or required repo-local functions
- preserve evidence-layer separation
- remain specific to Riskseer

They must not:

- be generic automation recipes
- redefine the architecture
- hide business logic outside the owning code files

### Tools

Tools are documented interfaces stored in `TOOLS/`.

They must:

- map directly to existing Riskseer functions or thin compositions of existing repo logic
- clearly state owner file(s), inputs, outputs, and constraints
- never become a shadow logic layer that diverges from the code

They must not:

- invent new product logic unrelated to the repo
- replace owning modules
- hide decision rules away from the engine

---

## Required Workflow Execution Model

For any non-trivial task, the required process is:

1. read `AGENTS.md`
2. inspect the current relevant files
3. restate file ownership
4. select an existing workflow from `WORKFLOWS/`, or create/update one if no current workflow fits
5. write a plan in `PLANS.md` if the task is multi-file, logic-changing, or architecture-sensitive
6. execute the workflow using tools defined in `TOOLS/`
7. validate outputs with the most relevant available repo path
8. report changes

Definition of non-trivial:

- more than one file
- any logic change
- any architecture-sensitive change
- any evaluation, continuity, API, or frontend decision-flow change

Single-file wording-only edits may skip `PLANS.md`, but must still follow the rest of the sequence.

---

## Non-Negotiable Constraints

All changes must preserve:

1. deterministic pipeline behavior
2. case-first design
3. stable case identity and continuity
4. explicit evidence-layer separation:
   - observed
   - derived
   - inferred
   - assumed
5. no UI-owned backend logic
6. smallest safe diffs
7. no silent movement of responsibilities between files
8. no broad refactors without explicit justification

Do not simplify by:

- flattening the case-based system into event-only logic
- merging current-state and temporal reasoning into one opaque layer
- letting the frontend become the truth source
- treating "ticket exists" as equivalent to "safe to proceed"

---

## Workflow Rules

Every workflow must:

- be based on real code paths in this repo
- name the tools it uses
- identify the owning files for those tools
- preserve evidence-layer separation
- stop if the requested change would violate an ownership boundary

Workflow selection guidance:

- case grouping or continuity changes:
  use `WORKFLOWS/case_grouping.md`
- current-state evaluation changes:
  use `WORKFLOWS/case_evaluation.md`
- temporal comparison or drift changes:
  use `WORKFLOWS/drift_detection.md`
- decision-state/urgency/posture changes:
  use `WORKFLOWS/decision_posture.md`
- explanation or report rendering changes:
  use `WORKFLOWS/explanation_generation.md`

---

## Planning Requirement

Use `PLANS.md` for:

- multi-file work
- logic changes
- architecture-sensitive work
- evaluation, continuity, API, or frontend decision-flow work

The plan must be based on inspected code, not assumptions.

---

## Validation Expectations

After meaningful changes, run the most relevant available validation.

Minimum expectations:

- backend logic change:
  run a repo-local pipeline or direct evaluation path
- frontend change:
  run the frontend build
- output/explanation change:
  confirm outputs still generate/render
- architecture-sensitive change:
  confirm the change stayed in the correct owner file

Do not claim validation you did not run.

---

## Required Completion Output Format

Every completed task response must include:

1. What changed
2. Why it changed
3. Validation performed
4. Risks or follow-up issues
5. Whether any architecture boundary was pressured or preserved

---

## Absolute Do-Not Rules

Do not:

- invent a new architecture
- collapse file responsibilities
- move backend logic into the UI
- replace the case-based system with flat event logic
- reduce evidence-layer distinctions
- perform broad refactors without justification

Do:

- preserve existing system intent
- improve clarity and structure
- align workflows with real code behavior
- keep the system deterministic and auditable
