# Riskseer Product Boundary

## Core Claim

Riskseer is a decision integrity layer.

More specifically:

- Urbint predicts where risk is likely.
- Riskseer flags when a decision is resting on weak assumptions.

It is built to catch the moment when work still looks normal, but the support for continuing is weaker than it seems.

Riskseer does not try to prove underground truth.
Riskseer does not replace locating, marking, or field validation.
Riskseer does not compete on broad upstream job-risk scoring.

Its job is narrower:

- identify when a crew may be relying on weak, stale, partial, or conflicting support
- surface that weakness before habit carries the work forward
- output an action:
  - `STOP`
  - `VERIFY`
  - `ESCALATE`
  - `PROCEED`

## What Riskseer Is

Riskseer is:

- a real-time decision validity system
- a false-confidence interrupter
- a habit override tool
- a current-context reasoning layer
- a system for showing when the basis for continuing has degraded

Riskseer should speak in terms of:

- what looks normal
- what support is weak
- why that matters now
- what to check before continuing
- why something looks valid even though the reason it looks valid no longer holds

## What Riskseer Is Not

Riskseer is not:

- a generic excavation risk score
- an inspection prioritization engine
- a utility resource allocation tool
- a locate truth engine
- a map verifier
- a dashboard for broad analytics
- a post-incident reporting layer

If the product starts sounding like:

- "this job is high risk"
- "this area has elevated probability"
- "here is a score across all work"

that is drift toward Urbint-like territory.

## Product Thesis

The problem is not just risk.

The problem is mistaken confidence under changing conditions.

Crews continue because:

- a ticket exists
- work appears routine
- nothing obvious looks wrong
- habit is stronger than weak warning signals

Riskseer exists to interrupt that exact moment.

## Allowed Claims

Riskseer can credibly say:

- work is continuing while authorization or context remains unresolved
- available ticket support is partial, stale, conflicting, or incomplete
- the current basis for continuing is weaker than it appears
- mechanized work is continuing under degraded support
- this matches a pattern where crews may continue under false confidence
- this situation deserves a pause, verification, or escalation

## Forbidden Claims

Riskseer must not claim, unless direct evidence exists:

- markings are wrong
- the map is wrong
- the crew is definitely outside the real safe zone
- the excavation is definitely unauthorized
- a strike is imminent
- the underground condition is known with certainty

The system should not pretend to know what it cannot know.

## Competitive Boundary vs Urbint

Urbint-style systems answer:

- which jobs deserve more attention
- where to send inspectors
- how to prioritize limited resources

Riskseer must answer:

- why this crew should pause right now
- why this moment only looks safe
- why the support for continuing no longer holds up cleanly

Clean comparison:

- Urbint: before work
- Riskseer: during the decision

- Urbint: risk probability
- Riskseer: decision validity / decision integrity

- Urbint: prioritization
- Riskseer: interruption

- Urbint: pattern scoring
- Riskseer: current-context contradiction

The cleanest contrast is:

- Urbint: "this job is more likely to be risky"
- Riskseer: "this looks valid, but the reason it looks valid does not hold"

## Build Rules

Every feature should pass this test:

1. Does this help explain why continuing right now is weaker than it seems?
2. Does this help interrupt habit before obvious failure?
3. Does this produce a clearer action at the decision moment?

If yes, it fits.

If a feature mainly helps:

- rank jobs across the enterprise
- schedule inspections
- build dashboards
- summarize historical trends
- generate broad risk scores

it is probably not core Riskseer.

## Features To Build

- contradiction detection around current ticket, timing, scope, and continuity
- operator-facing "what looks normal / what is weak / what to check now" framing
- clear action outputs: `STOP`, `VERIFY`, `ESCALATE`, `PROCEED`
- explicit restraint: show when not to interrupt
- temporal degradation logic:
  - support got weaker
  - work resumed after a gap
  - activity continues under unresolved context
- behavioral framing:
  - work is continuing as if support is certain
  - routine is outrunning validation
- lifecycle handling:
  - active
  - inactive
  - closed
  - reactivated

## Features To Reject

- enterprise risk heatmaps as the primary experience
- job-scoring pages with no decision-level action
- generic analytics dashboards
- explanations that sound like a safety report instead of a decision interruption
- language that implies hidden truth instead of degraded support
- "AI risk score" messaging

## UI Rules

The top of the product should always answer:

1. What looks normal?
2. What is weak?
3. Why does that matter now?
4. What do I check before continuing?

The UI should not lead with:

- a score
- a long explanation
- a broad dashboard

It should lead with:

- the case to look at first
- the action to take
- the weak support behind a normal-looking situation

## Success Condition

Riskseer succeeds when an operator says:

"I can see why someone would keep moving here, but I also see why that confidence is not strong enough."

It fails when it sounds like:

"Here is another risk dashboard."
