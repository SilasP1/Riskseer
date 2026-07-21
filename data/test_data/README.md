Test datasets for manual pipeline runs.

Usage:

```powershell
.\scripts\Clear-LiveData.ps1
.\scripts\Load-TestDataset.ps1
python main.py
```

To reset saved trend comparisons before a fresh demo run:

```powershell
.\scripts\Clear-TrendHistory.ps1
```

Datasets:

- `default`
  A small mixed scenario pack with recent timestamps, multiple ticket relationships,
  and a few different spatial/temporal contradiction patterns.

- `temporal_evolution`
  A long-horizon lifecycle pack with week-long chains, closed historical threads,
  inactive watchpoints, and active/reopened cases with events as recent as
  April 7, 2026. Use this when testing status transitions, lifecycle messaging,
  and temporal continuity behavior.

- `temporal_reactivation`
  A focused lifecycle pack for reopen logic. Includes cases that should reopen
  within the 3-day continuity window, cases that should stay inactive after
  reopening, and older threads that are too old to reopen and should instead
  stay split into separate historical and current cases.

- `balanced_10_cases`
  A deliberately shaped queue fixture with 10 cases total: 4 active
  (`CRITICAL`, `HIGH`, `MODERATE`, and `LOW`), 3 inactive, and 3 closed.
  This pack is designed for queue review, lifecycle behavior, temporal
  track-record testing, and card-summary testing under imperfect but
  structured data.

- `decision_integrity_stress`
  A larger scenario pack meant to push the current product thesis harder.
  It includes safe-looking active work, overlapping-ticket ambiguity,
  no-ticket machine activity, trenchless/reduced-visibility work,
  inactive watchpoints, closed historical threads, and reopened cases that
  come back within the continuity window.

- `realistic_field_mix`
  A more realistic operator-facing mix. Most cases are boring, valid, and
  properly supported so Riskseer has to stay quiet. A smaller slice is
  ambiguous enough to require verification, and only a very small slice is
  truly dangerous. It also includes ticket-only rows with no activity so
  expired or inactive paperwork does not create fake cases by itself.

- `demo_phase1_baseline`
  Calm baseline for demos. About 8-10 cases, mostly quiet `MONITOR` work with
  a single moderate verification case.

- `demo_phase2_disruption`
  Same baseline, but one previously mild case becomes more serious and should
  move into escalation territory without the whole queue exploding.

- `demo_phase1_realistic`
  Scenario A baseline. A calmer, more realistic demo baseline. Seven cases
  should stay normal and quiet, with one ambiguous case in
  `VERIFY_BEFORE_PROCEEDING`. There should be no more than one escalation
  candidate in the whole slice.

- `demo_phase2_realistic`
  Scenario A follow-up: calm to escalation. The same realistic baseline, but
  the single ambiguous case worsens through an operational escalation while the
  normal cases stay normal. Use this with the contradiction audit to confirm
  that the queue changes minimally and for the right reasons.

- `demo_phase1_restraint`
  Scenario B baseline. This starts from the same calm realistic picture as the
  realistic demo baseline: mostly quiet monitor cases, with one ambiguous case
  that deserves verification but does not justify interruption.

- `demo_phase2_restraint`
  Scenario B follow-up. The ambiguous case stays non-interrupting instead of
  worsening. Use this to prove restraint: stable monitor cases should stay flat,
  and the one shaky case should remain `VERIFY_BEFORE_PROCEEDING` or settle
  without triggering escalation.

- `demo_phase1_improving`
  Scenario C baseline. Starts from the same calm realistic picture with one
  ambiguous case in `VERIFY_BEFORE_PROCEEDING`.

- `demo_phase2_improving`
  Scenario C follow-up. The ambiguous case resolves or improves because ticket
  support gets cleaner, so the engine should de-escalate without drama while
  the rest of the queue stays calm.

- `demo_phase3_stop_work`
  Adds one real stop-work case on top of the phase 2 picture. The point is to
  show one sharp interruption while the rest of the queue stays mostly stable.

- `demo_phase4_resolution`
  Shows the queue settling back down: the prior stop case becomes supported
  again, one ambiguous case drops back, and one older thread lands in inactive
  watch status.

- `timestamp_provenance_mix`
  A focused pack for timestamp provenance and timeline behavior. It includes
  events, tickets, and assets with missing source times so Riskseer has to
  fall back to ingest time and label that clearly in the backend and frontend.

- `operator_layer_mix_phase1`
  A richer mixed baseline built to create more differentiation across the
  workspace. It includes quiet valid work, two different ambiguous cases,
  one stronger escalation candidate, inactive threads, and closed history so
  the queue and layer pages do not all sort the same way.

- `operator_layer_mix_phase2`
  Follow-up to the richer mixed baseline. One ambiguous case worsens through
  operational escalation, one previously inactive thread comes back to life,
  one ambiguous case improves because ticket support gets cleaner, and the
  quiet cases stay quiet. Use this to test temporal movement and page-level
  differentiation across the operator layers.
