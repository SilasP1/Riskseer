# PLANS.md

## Purpose

This file is the reusable planning template for non-trivial Riskseer work.

It is part of the WAT operating system:

- `AGENTS.md` defines architecture and execution discipline
- `WORKFLOWS/` define markdown-based natural language processes
- `TOOLS/` define tool interfaces mapped to existing repo logic
- `PLANS.md` forces planning before multi-file or logic-changing execution

Use this template for:

- multi-file changes
- logic changes
- architecture-sensitive work
- evaluation, continuity, API, or frontend decision-flow changes

---

## Planning Rules

Every plan must:

1. start after reading `AGENTS.md`
2. be grounded in inspected code, not assumptions
3. restate file ownership for every relevant file
4. select the workflow(s) to use
5. identify the tool(s) to call
6. identify boundary risks before implementation
7. define validation before coding
8. prefer the smallest safe diff
9. include stop conditions

If you have not inspected the relevant files, the plan is incomplete.

---

## Reusable Plan Template

```md
# Plan: <short task name>

## Objective

- What outcome is required?
- What should change?
- What must remain unchanged?

## Current System Analysis

- What does the current code do today?
- What is the actual affected data flow in this repo?
- How do current responsibilities split across logic, orchestration, and presentation?
- Which current behaviors are backend truth vs frontend presentation?

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
- Why these workflows fit the real code path:

## Tool Selection

- Selected tool(s) from `TOOLS/`:
- Owning file(s) for each tool:
- Whether each tool is direct or composite:

## Files Involved And Responsibilities

- `<file>`:
  current responsibility
  why it is relevant
  whether it should change

- `<file>`:
  current responsibility
  why it is relevant
  whether it should change

Include files inspected even if they should remain unchanged.

## Boundary Risks

- Does this risk moving logic into the wrong file?
- Does this risk UI-owned backend truth?
- Does this risk weakening case identity or continuity?
- Does this risk collapsing observed / derived / inferred / assumed?
- Does this risk creating duplicate logic?

For each risk:
- state the risk clearly
- state how it will be avoided

## Minimal Change Strategy

- What is the smallest safe implementation path?
- Which file should own the change?
- Which files must not absorb the change?
- What existing functions or outputs can be reused?

## Validation Steps

- Backend validation:
  exact command or code path to run
- Frontend validation:
  exact command or code path to run
- Output validation:
  what generated output, API payload, or rendered artifact will be checked
- Boundary validation:
  how you will confirm responsibilities stayed intact

Only include validation you can actually run.

## Stop Conditions

Stop and reassess if:

- the change requires moving responsibilities across boundaries
- the frontend would become the truth source for backend logic
- the change weakens evidence-layer separation
- the task expands into a broad refactor without approval
- continuity or case identity behavior would change without direct validation

## Completion Report

When done, report:

1. What changed
2. Why it changed
3. Validation performed
4. Risks or follow-up issues
5. Whether any architecture boundary was pressured or preserved

---

# Plan: Responsibility Integrity Model

## Objective

- Add a backend-first Responsibility Integrity Model (RIM) for case-level decision support quality.
- Evaluate responsibility integrity across excavator behavior, locate execution, mark/field reality, asset confidence, and coordination.
- Preserve the existing case-first architecture and evidence-layer separation.

## Current System Analysis

- `case_evaluation.py` already owns current-state reasoning, evidence layers, alignment, information integrity, behavioral risk, uncertainty burden, failure layers, decision state, urgency, and response posture.
- `case_logic.py` already orchestrates current-state and temporal outputs and stores evaluation metadata on each case.
- `main.py` serializes dataclass outputs into `case_registry.json`; no new main orchestration logic is needed.
- `explanations.py` renders structured backend truth into operator/internal artifacts.
- `api.py` normalizes saved backend outputs without re-evaluating.
- `Riskseer Frontend/src/App.jsx` presents case-detail views and should only render backend-provided RIM data.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_evaluation.md`
  - `decision_posture.md`
  - `explanation_generation.md`
- Why these workflows fit:
  RIM is current-state case reasoning that reinforces operator posture and later needs concise rendering from already-computed backend truth.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `build_evidence_layers`
  - `evaluate_case_alignment`
  - `evaluate_information_integrity`
  - `evaluate_behavioral_risk`
  - `compute_uncertainty_burden`
  - `determine_response_posture`
  - `orchestrate_case_evaluation`
  - `generate_operator_explanation`
  - `load_api_case_contract`
- Owning files:
  - `case_evaluation.py`
  - `case_logic.py`
  - `explanations.py`
  - `api.py`

## Files Involved And Responsibilities

- `schemas.py`:
  add structured dataclasses/enums for responsibility layers, decision support integrity, and RIM bundle only.
- `case_evaluation.py`:
  implement deterministic RIM evaluators and aggregation using existing observations/evaluation signals.
- `case_logic.py`:
  call RIM evaluators after existing current-state and lifecycle posture are known, attach the bundle to metadata and `CaseEvaluation`.
- `explanations.py`:
  render concise operator/internal RIM sections and report columns from backend truth.
- `api.py`:
  pass through `responsibility_integrity` from saved evaluation/metadata to the frontend contract.
- `Riskseer Frontend/src/App.jsx`:
  render a compact panel from backend-provided RIM only if data exists.

## Boundary Checklist

- `main.py` remains orchestration-only.
- `case.py` remains identity/continuity-only.
- `event_logic.py` and `ticket_logic.py` remain event/ticket utility owners.
- `case_evaluation.py` owns RIM evaluation, not explanations or grouping.
- `case_logic.py` only orchestrates and stores the RIM output.
- `explanations.py` only renders already-computed RIM fields.
- `api.py` only passes saved RIM fields through.
- frontend remains presentation-only.

## Validation Steps

- Run a direct backend evaluation or full pipeline path.
- Confirm `case_registry.json` contains structured `responsibility_integrity`.
- Run the frontend build after UI wiring.

---

# Plan: Case Detail Chain Coherence

## Objective

- Remove contradictory frontend case-detail framing across queue, decision, evidence, and case-detail tabs.
- Make the Responsibility Integrity chain a first-class part of each case view.
- Keep all decision truth backend-owned; use the frontend only to present a coherent story from saved backend fields.

## Current System Analysis

- `api.py` now passes backend `responsibility_integrity` through to the frontend contract.
- `Riskseer Frontend/src/App.jsx` still derives many labels and summaries independently, including queue reasons, "Proceed" labels, weak-support lists, hidden-risk framing, and action-panel copy.
- These helpers can contradict backend RIM when posture is `MONITOR` but decision support is `PARTIAL`, `DEGRADED`, or `CONFLICTED`.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `decision_posture.md`
  - `case_evaluation.md`
- Why these workflows fit:
  the UI is presenting decision posture and case support quality; the fix must preserve backend ownership and avoid new frontend scoring.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `load_api_case_contract`
  - `orchestrate_case_evaluation`
  - `generate_operator_explanation`
- Owner files:
  - `api.py`
  - `case_logic.py`
  - `explanations.py`
  - `Riskseer Frontend/src/App.jsx`

## Files Involved And Responsibilities

- `Riskseer Frontend/src/App.jsx`:
  present backend RIM consistently across the case view; remove contradictory fallback language where practical.
- `api.py`:
  read-only contract source; inspect only unless pass-through is missing.
- `case_logic.py` / `case_evaluation.py`:
  backend truth source; no expected changes unless frontend reveals missing structured data.

## Boundary Checklist

- Frontend must not re-score RIM or override backend posture.
- Frontend may choose clearer labels such as "Monitor" instead of "Proceed" when backend posture is monitor.
- Frontend may organize RIM layers into a chain view, but each layer state/reason must come from backend data.

## Validation Steps

- Run frontend build.

---

# Plan: RIM Demo Datasets

## Objective

- Add multiple repo-local demo cases that make weak, unknown, missing, and conflicted support visible.
- Cover ticket scope/time weakness, locate unknown/missing support, mark/field unknown support, asset context, and coordination unknowns using the currently loaded CSV inputs.

## Current System Analysis

- `main.py` currently loads only `data/events.csv`, `data/tickets.csv`, and `data/assets.csv`.
- Marking, field-report, and positive-response schemas exist, but `main.py` does not load those CSVs yet.
- RIM therefore can demonstrate locate/mark/coordination weakness mostly through attached ticket/event/asset evidence and unknown states, not through positive-response/marking source rows.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_evaluation.md`
- Why this workflow fits:
  the demo data is meant to exercise current-state evaluation and RIM outputs without changing logic.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `normalize_source_records`
  - `classify_event_context`
  - `build_case_registry`
  - `orchestrate_case_evaluation`

## Files Involved And Responsibilities

- `data/events.csv`, `data/tickets.csv`, `data/assets.csv`:
  active demo batch for immediate pipeline run.
- `data/test_data/rim_demo/`:
  reusable copy of the same demo fixture.

## Boundary Checklist

- No backend business logic changes.
- Demo data must exercise existing loaded code paths only.
- Any locate/mark/coordination support that lacks loaded source rows should appear as `UNKNOWN`, not fake `MISSING`.

## Validation Steps

- Run `python main.py`.
- Confirm generated `case_registry.json` includes varied RIM states.
- Confirm frontend build still passes.
- Confirm backend pipeline/API still expose RIM.
- Confirm case detail tabs use the same chain story.

---

# Plan: Rich Responsibility Support Datasets

## Objective

- Add richer staged demo data where each case has roughly ten operational events.
- Include loaded ticket, field-report, marking/locate, positive-response, asset, and field activity context.
- Make temporal evolution visible by providing a baseline stage and a follow-up stage that changes support quality.

## Current System Analysis

- `main.py` currently loads only events, tickets, and assets into the live pipeline.
- `schemas.py` already defines `FieldReportRecord`, `MarkingRecord`, and `PositiveResponseRecord`.
- `case.py` already owns attachment helpers for field reports, markings, and positive responses, but no registry-level orchestration currently invokes them.
- `case_evaluation.py` RIM already uses attached field report, marking, and positive-response identifiers as backend truth for locate, mark, and coordination support.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_grouping.md`
  - `case_evaluation.md`
  - `drift_detection.md`
- Why these workflows fit:
  contextual records must attach to cases through case-owned identity/attachment rules, then current-state RIM and temporal comparison consume those outputs.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `normalize_source_records`
  - `build_case_registry`
  - `orchestrate_case_evaluation`
  - `detect_case_drift`
- Owning files:
  - `event_logic.py`
  - `case.py`
  - `case_logic.py`
  - `case_temporal.py`

## Files Involved And Responsibilities

- `event_logic.py`:
  add normalization for field reports, markings, and positive responses.
- `case.py`:
  add registry-level contextual-record attachment using existing attachment helpers.
- `main.py`:
  orchestrate loading, attachment, output counts, archive, and clear behavior for the new CSV inputs.
- `data/test_data/rim_rich/`:
  add reusable staged fixtures for baseline and evolution runs.

## Boundary Checklist

- `main.py` remains orchestration-only.
- `case.py` owns record-to-case attachment, not scoring.
- `case_evaluation.py` consumes attached records; it does not own CSV ingestion.
- Dataset rows exercise existing evaluation semantics instead of hard-coding case outcomes.

## Validation Steps

- Run `python main.py` through staged fixtures.
- Inspect generated `case_registry.json` for attached field reports, markings, positive responses, and varied RIM states.
- Run the frontend build after backend output generation.

---

# Plan: Decision Defensibility Evaluation

## Objective

- Add a structured backend evaluation of whether the current case supports a defensible operational decision under scrutiny.
- Evaluate evidence sufficiency, process integrity, consistency, verification depth, and assumption load.
- Augment posture and RIM without replacing existing decision state, urgency, or response posture.

## Current System Analysis

- `case_evaluation.py` owns current-state case reasoning, evidence layers, RIM, alignment, information integrity, behavioral risk, uncertainty, failure layers, and posture inputs.
- `case_logic.py` orchestrates current-state and temporal outputs, then stores metadata on the case.
- `explanations.py` renders internal/operator text from already-computed backend truth.
- `api.py` normalizes saved backend outputs for the frontend without re-evaluating.
- The frontend already renders backend case-detail panels and should only display the new backend-provided object.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_evaluation.md`
  - `explanation_generation.md`
  - `decision_posture.md`
- Why these workflows fit:
  defensibility is current-state decision-support reasoning that consumes RIM/evidence/alignment plus temporal metadata and needs concise rendering from backend truth.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `build_evidence_layers`
  - `evaluate_case_alignment`
  - `evaluate_information_integrity`
  - `evaluate_behavioral_risk`
  - `orchestrate_case_evaluation`
  - `generate_internal_explanation`
  - `load_api_case_contract`

## Files Involved And Responsibilities

- `schemas.py`:
  add dataclasses/enums for decision defensibility structured output.
- `case_evaluation.py`:
  implement deterministic `evaluate_decision_defensibility` using existing backend truth.
- `case_logic.py`:
  call the evaluator after RIM and temporal outputs exist, store it on case metadata/evaluation, and optionally reinforce actions.
- `explanations.py`:
  render the already-computed defensibility object in internal output and report rows.
- `api.py`:
  pass through saved `decision_defensibility`.
- `Riskseer Frontend/src/App.jsx`:
  show a compact Defensibility section from backend output only.

## Boundary Risks

- Risk: creating legal fault assignment.
  Avoidance: language focuses on decision support quality and scrutiny readiness only.
- Risk: duplicating posture logic.
  Avoidance: defensibility consumes posture/RIM/evidence but does not replace them.
- Risk: frontend-derived scoring.
  Avoidance: frontend only renders backend-provided state, reason, and components.

## Validation Steps

- Compile backend Python files.
- Run staged rich demo pipeline to regenerate `case_registry.json`.
- Inspect LOW vs HIGH/MODERATE defensibility examples in generated output.
- Run frontend build.

---

# Plan: Output Coherence Fixes

## Objective

- Fix generated output contradictions found in the post-implementation review.
- Ensure critical no-ticket cases do not read as improving without actual support/posture improvement.
- Make defensibility wording distinguish a defensible verification decision from broad proceed confidence.
- Clarify ticket exists-but-does-not-cover-work cases as unsupported rather than absent.
- Preserve asset consequence when near/conflicting asset evidence exists.

## Current System Analysis

- `case_temporal.py` owns temporal trend and hidden-risk change. It currently allows operational deescalation/hidden-risk deltas to mark a critical unsupported case as improving.
- `case_evaluation.py` owns current-state RIM, ticket-support language, and decision defensibility logic.
- `case_logic.py` owns orchestration and summary/action propagation.
- `explanations.py` renders already-computed truth and should not hide contradictions by wording alone.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `drift_detection.md`
  - `case_evaluation.md`
  - `explanation_generation.md`
- Why these workflows fit:
  the fixes touch temporal classification, current-state support semantics, and rendered output consistency.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `detect_case_drift`
  - `compute_investigation_roi`
  - `build_evidence_layers`
  - `evaluate_information_integrity`
  - `orchestrate_case_evaluation`
  - `generate_internal_explanation`
  - `audit_case_outputs`

## Files Involved And Responsibilities

- `case_temporal.py`:
  guard trend/hidden-risk logic for hold-work/no-ticket and asset-consequence cases.
- `case_evaluation.py`:
  refine support wording and defensibility state/reason logic.
- `case_logic.py`:
  keep orchestration unchanged unless summary propagation needs a backend-truth adjustment.
- `explanations.py`:
  render any refined defensibility fields without adding scoring.

## Validation Steps

- Compile backend files.
- Re-run rich staged fixtures.
- Inspect output cases `00004`, `00005`, `00006`.
- Run contradiction audit and frontend build.

---

# Plan: UI Landing And Queue Overhaul

## Objective

- Make the first screen a no-scroll landing page.
- Landing content:
  - short non-selectable "what changed" section with cases that became riskier or are trending safer
  - one most-immediate-attention case
- Keep case selection and drill-in on the queue page, then case detail page.

## Current System Analysis

- `Riskseer Frontend/src/App.jsx` currently has `summary`, `queue`, and `case` pages.
- The summary page is selectable and scroll-heavy, with multiple overview signal cards.
- The queue page already supports case selection and opening a case.
- Backend trend truth is available through `trendMeta`, `temporal_change`, `changeSummary`, and existing queue priority ordering.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `decision_posture.md`
- Why this workflow fits:
  the UI is changing how backend posture and trend are presented, while preserving backend decision ownership.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `load_api_case_contract`
- Owner file:
  - `api.py`
  - `Riskseer Frontend/src/App.jsx`

## Files Involved And Responsibilities

- `Riskseer Frontend/src/App.jsx`:
  reshape page flow and landing content using existing backend fields.
- `Riskseer Frontend/src/App.css`:
  add no-scroll landing layout and compact change cards.

## Boundary Checklist

- Frontend remains presentation-only.
- No backend posture, urgency, trend, or RIM truth is redefined.
- "What changed" landing cases are display-only.
- Queue remains the case selection surface.

## Validation Steps

- Run frontend build.
- Confirm API remains reachable.
- Confirm landing page starts first and queue/case navigation still works.

---

# Plan: RIM Unknown Versus Missing Semantics

## Objective

- Add explicit `UNKNOWN` support to RIM layer states.
- Reserve `MISSING` for evidence-backed absence, not merely absent/unknown source data.
- Apply this distinction across excavator, locate, marks, assets, and coordination layers.

## Current System Analysis

- `schemas.py` currently defines RIM layer states as `STRONG`, `WEAK`, `MISSING`, and `CONFLICTED`.
- `case_evaluation.py` currently uses `MISSING` in several places where the data is simply not attached.
- Frontend rendering already title-cases enum states but treats weak-layer selection as `CONFLICTED`, `MISSING`, or `WEAK`; it should include `UNKNOWN`.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_evaluation.md`
- Why this workflow fits:
  this changes current-state case reasoning semantics inside the backend RIM evaluator.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `evaluate_case_alignment`
  - `evaluate_information_integrity`
  - `orchestrate_case_evaluation`
  - `load_api_case_contract`

## Files Involved And Responsibilities

- `schemas.py`:
  add `UNKNOWN` RIM layer state.
- `case_evaluation.py`:
  update RIM evaluators, aggregation, and propagation semantics.
- `Riskseer Frontend/src/App.jsx`:
  display `UNKNOWN` as an attention-worthy chain state without redefining backend truth.

## Boundary Checklist

- `case_evaluation.py` remains current-state evaluation owner.
- Frontend only renders the new backend enum state.
- No case grouping, temporal comparison, or explanation policy is moved.

## Validation Steps

- Compile backend Python files.
- Run pipeline to regenerate outputs.
- Confirm `responsibility_integrity` contains `UNKNOWN` where source absence is not proof of absence.
- Run frontend build.

---

# Plan: Queue-To-Case Flow Simplification

## Objective

- Remove the top-level Case navigation tab.
- Let queue cards open case details directly.
- Keep Landing and Queue as the only top-level destinations.

## Current System Analysis

- `Riskseer Frontend/src/App.jsx` currently has `landing`, `queue`, and internal `case` pages.
- The top nav exposes Case as a separate tab, forcing users to select in queue and then switch/open elsewhere.
- Queue cards currently select a case without opening it after the landing overhaul.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `decision_posture.md`
- Why this workflow fits:
  this changes presentation flow around backend posture/action, but not backend truth.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `load_api_case_contract`

## Files Involved And Responsibilities

- `Riskseer Frontend/src/App.jsx`:
  remove Case from top navigation and route queue card clicks directly to case detail.
- `Riskseer Frontend/src/App.css`:
  adjust top navigation layout from three columns to two.

## Boundary Checklist

- Frontend remains presentation/navigation only.
- Backend decision truth and RIM outputs remain untouched.

## Validation Steps

- Run frontend build.
- Confirm queue card click path still opens the internal case detail page.

---

# Plan: Case Detail Tab Controls

## Objective

- Make Decision / Chain / Evidence tab switching obvious.
- Use one consistent tab-control location across all case-detail tabs.
- Put the controls at the top of the case detail view.

## Current System Analysis

- `Riskseer Frontend/src/App.jsx` currently renders case tab buttons in the case actions bar and also renders a second `tab-bar` inside the tab content shell.
- This creates inconsistent tab switching and makes the controls less obvious after scrolling.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `decision_posture.md`
- Why this workflow fits:
  this is presentation flow around backend decision/posture truth, not a backend logic change.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `load_api_case_contract`

## Files Involved And Responsibilities

- `Riskseer Frontend/src/App.jsx`:
  keep one tab switcher at the top of case detail.
- `Riskseer Frontend/src/App.css`:
  make the top tab switcher visually stronger and consistent.

## Boundary Checklist

- Frontend remains presentation-only.
- Backend case truth and posture are untouched.

## Validation Steps

- Run frontend build.
```

---

## Required Planning Discipline

Plans must explicitly answer:

- What currently owns this behavior?
- Why is that ownership correct or incorrect?
- Which workflow governs the work?
- Which tool(s) implement the real code path?
- What is the smallest change that preserves the architecture?

Plans must not:

- invent a new architecture
- assume ownership from filenames alone
- skip data-flow analysis
- skip workflow/tool selection
- skip validation definition

---

## Data-Flow Checklist

When relevant, trace the current repo path through:

1. input source
2. normalization
3. event interpretation
4. case grouping and continuity
5. current-state evaluation
6. temporal comparison
7. explanation/output rendering
8. API normalization
9. frontend presentation

If the task touches one of these stages, identify upstream and downstream effects.

---

## Boundary Checklist

For each plan, confirm:

- `main.py` remains orchestration-only
- `ticket_logic.py` remains ticket-utility-only
- `event_logic.py` remains event-interpretation-only
- `case.py` remains identity/continuity-only
- `case_evaluation.py` remains current-state evaluation-only
- `case_temporal.py` remains temporal comparison-only
- `case_logic.py` remains evaluation orchestration-only
- `explanations.py` remains wording/rendering-only
- `api.py` remains read-only normalization-only
- `lookup_case.py` remains read-only inspection-only
- frontend remains presentation-only

If the plan cannot satisfy one of these, stop before implementation and explain why.

---

# Plan: Riskseer WAT State Evaluation

## Objective

- Evaluate where Riskseer currently stands using the WAT operating system.
- Assess architecture fit, product fit, workflow/tool alignment, and current risks.
- Avoid changing engine behavior unless a concrete evaluation blocker is discovered.

## Current System Analysis

- The current repo is a case-first pipeline:
  input -> normalization -> event interpretation -> case grouping/continuity -> current-state evaluation -> temporal comparison -> explanation/output rendering -> API normalization -> frontend presentation.
- Current backend truth is primarily owned by `case.py`, `case_evaluation.py`, `case_temporal.py`, and `case_logic.py`.
- Current presentation pressure is primarily in `Riskseer Frontend/src/App.jsx`, which derives substantial view-side prioritization and framing from backend outputs.
- The WAT system added to the repo is documentation/orchestration discipline layered over the existing engine, not a replacement architecture.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `case_evaluation.md`
  - `drift_detection.md`
  - `explanation_generation.md`
- Why these workflows fit the real code path:
  the evaluation requires inspecting current-state reasoning, temporal/drift behavior, and how backend truth is rendered/exposed to users.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `build_evidence_layers`
  - `determine_decision_state`
  - `determine_response_posture`
  - `detect_case_drift`
  - `compute_investigation_roi`
  - `generate_operator_explanation`
  - `load_api_case_contract`
  - `audit_case_outputs`
- Owning file(s) for each tool:
  - `case_evaluation.py`
  - `case_temporal.py`
  - `explanations.py`
  - `api.py`
  - `case_audit.py`
- Whether each tool is direct or composite:
  mixed; use direct tools for assessment and composite understanding where needed.

## Files Involved And Responsibilities

- `AGENTS.md`:
  workflow operating system and architecture discipline
  relevant because the evaluation must use it
  should not change during evaluation unless a clear operating-system defect is found

- `PRODUCT_BOUNDARY.md`:
  product-fit boundary and action framing
  relevant because the evaluation must assess drift
  should not change during evaluation

- `case.py`:
  identity, continuity, attachment, branching
  relevant because case-first integrity is central to Riskseer
  likely read-only for this task

- `case_evaluation.py`:
  current-state reasoning and evidence layers
  relevant because it defines core backend truth
  likely read-only for this task

- `case_temporal.py`:
  prior-vs-current comparison and ROI
  relevant because drift detection is part of the evaluation
  likely read-only for this task

- `case_logic.py`:
  orchestration and lifecycle actionability
  relevant because summary ownership and boundary pressure must be assessed
  likely read-only for this task

- `api.py`:
  read-only API normalization
  relevant because frontend truth flow depends on it
  likely read-only for this task

- `Riskseer Frontend/src/App.jsx`:
  presentation layer
  relevant because UI-owned logic risk must be assessed
  likely read-only for this task

- `output/case_registry.json` and `output/case_contradiction_audit.json`:
  generated outputs
  relevant for current-state evidence of system quality
  read-only for this task

## Boundary Risks

- Risk: evaluating system maturity could turn into unplanned refactoring.
  Avoidance: keep this task read-only unless a concrete blocking defect appears.

- Risk: frontend-derived logic may be mischaracterized as backend truth.
  Avoidance: explicitly distinguish backend-owned truth from frontend-organized interpretation.

- Risk: current evidence-layer separation could be overstated because the frontend reframes it.
  Avoidance: judge evidence-layer integrity from backend files first, then compare UI behavior.

## Minimal Change Strategy

- Default to read-only evaluation.
- Use the WAT workflow/tool system as the assessment framework, not as a reason to rewrite code.
- If any change becomes necessary, stop and ask before moving beyond a tiny, clearly justified diff.

## Validation Steps

- Backend validation:
  run a repo-local pipeline/evaluation path against existing test data
- Frontend validation:
  run the frontend build
- Output validation:
  inspect generated audit/output artifacts for current state
- Boundary validation:
  compare tool definitions and workflows to real function owners and current file responsibilities

## Stop Conditions

- Stop if the task starts turning into a refactor.
- Stop if evaluation would require changing backend truth to justify the docs.
- Stop if the only way to answer is to invent architecture not present in the repo.

## Completion Report

When done, report:

1. What changed
2. Why it changed
3. Validation performed
4. Risks or follow-up issues
5. Whether any architecture boundary was pressured or preserved

---

# Plan: Demo Mode And Walkthrough

## Objective

- Add a clean demo-ready frontend presentation path that highlights three representative cases.
- Tighten the landing and case-detail wording so the product story reads operator-first instead of internally.
- Add a short live demo script tied to the current UI and backend-generated case states.

## Current System Analysis

- `api.py` already provides the frontend with backend-owned truth for posture, trend, RIM, defensibility, and supporting summaries.
- `Riskseer Frontend/src/App.jsx` owns page flow, queue organization, and presentation copy. It currently shows the full queue and a broader landing narrative than a short demo needs.
- The current generated outputs include clear representative cases:
  - a supported monitor case
  - a conflicted hold-work case
  - an unsupported hold-work case
- No backend logic change is required for the demo work if the frontend selects demo cases from existing backend fields.

## Workflow Selection

- Selected workflow(s) from `WORKFLOWS/`:
  - `decision_posture.md`
  - `explanation_generation.md`
- Why these workflows fit the real code path:
  the work changes how backend posture/trend/support truth is presented and narrated, without changing current-state evaluation ownership.

## Tool Selection

- Selected tool(s) from `TOOLS/`:
  - `load_api_case_contract`
- Owning file(s) for each tool:
  - `api.py`
- Composite presentation work will remain in:
  - `Riskseer Frontend/src/App.jsx`
  - `Riskseer Frontend/src/App.css`

## Files Involved And Responsibilities

- `Riskseer Frontend/src/App.jsx`:
  current responsibility: frontend presentation and interaction flow
  why it is relevant: demo case selection, landing flow, queue framing, and case-detail copy belong here
  whether it should change: yes

- `Riskseer Frontend/src/App.css`:
  current responsibility: frontend visual presentation
  why it is relevant: demo mode needs a compact, obvious, no-noise presentation
  whether it should change: yes

- `api.py`:
  current responsibility: read-only backend-to-frontend normalization
  why it is relevant: confirm demo mode can rely on current payload shape without new frontend truth
  whether it should change: inspect only unless a missing passthrough is found

- `output/case_registry.json`:
  current responsibility: saved backend truth
  why it is relevant: confirms representative cases exist for the demo selection rules
  whether it should change: no

- `DEMO_SCRIPT.md`:
  current responsibility: none yet
  why it is relevant: store the live walkthrough tied to the current UI
  whether it should change: create

## Boundary Risks

- Risk: the frontend could start ranking or re-scoring cases with new business logic.
  Avoidance: demo mode will select representative cases from existing backend fields such as posture, RIM support state, defensibility, and trend only.

- Risk: demo wording could diverge from backend explanation truth.
  Avoidance: use backend summaries and reasons as source material; keep wording changes presentation-only.

- Risk: a demo-only path could become the primary truth source.
  Avoidance: make demo mode a presentation slice over the same case objects, not a separate data model.

## Minimal Change Strategy

- Add a frontend helper that chooses three representative demo cases from backend-owned truth.
- Keep demo mode optional and presentation-only.
- Reuse existing landing, queue, and case panels instead of inventing new scoring or duplicate components.
- Add one markdown demo script that references the same case categories shown by demo mode.

## Validation Steps

- Frontend validation:
  run `npm run build` in `Riskseer Frontend`
- Output validation:
  inspect the current `output/case_registry.json` and confirm the selected demo cases match real backend states
- Boundary validation:
  confirm no backend evaluation logic moved into `api.py` or the frontend

## Stop Conditions

Stop and reassess if:

- demo mode requires inventing frontend-only decision logic
- the selected cases cannot be derived cleanly from current backend truth
- the wording changes require altering backend evaluation semantics rather than presentation

## Completion Report

When done, report:

1. What changed
2. Why it changed
3. Validation performed
4. Risks or follow-up issues
5. Whether any architecture boundary was pressured or preserved
