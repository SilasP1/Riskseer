# Riskseer

Riskseer catches the weak assumptions behind field decisions before they turn
into damage. The competition demo is focused on excavation: it groups field
activity into continuing cases, separates facts from inference, evaluates the
support behind the next decision, and shows operators what needs attention now.

The deterministic Riskseer engine owns case identity, decision state, urgency,
and response posture. The optional OpenAI Investigator reads that saved result
through bounded tools and produces a concise, evidence-cited brief. It cannot
change or soften the backend decision.

## Live competition demo

[Open Riskseer](https://silasp1.github.io/Riskseer/)

GitHub Pages hosts a guided, fictional scenario demo showing how Thistle
detections can be interpreted against 811 and temporary-site context. The
public walkthrough uses precomputed fixture interpretations so it is safe,
repeatable, and does not imply live field analysis.

The repository and local workspace retain the working deterministic Riskseer
engine, Python API, tests, and optional OpenAI Investigator. The Investigator is
not enabled on the public static site because GitHub Pages cannot securely run
the Python API or hold an API key.

## OpenAI Build Week extension

Riskseer started before Build Week as an early, excavation-focused
decision-integrity engine. The case-first architecture and the underlying idea
of testing whether a field decision is still supported were already in place.
The work submitted for Build Week is the meaningful extension completed from
July 13–21, 2026, and that is the work I expect to be judged.

During Build Week I used Codex and GPT-5.6 to turn that foundation into a
runnable, testable product demonstration:

- I added a bounded OpenAI Investigator that reads saved engine truth through
  three read-only tools and returns a structured, evidence-cited brief.
- I added the Investigator API path, dependency manifests, setup instructions,
  and regression tests needed to run and inspect the system consistently.
- I rebuilt the public experience around two guided operator scenarios, an
  interactive corridor map, explicit human confirmation, and a compact window
  into the engine contract.
- I deployed a repeatable static walkthrough to GitHub Pages while keeping API
  keys, production data, internal thresholds, and production prioritization
  logic out of the browser.

The dated commit and pull-request history in this repository documents that
Build Week work separately from the initial import.

### How I collaborated with Codex

I used Codex as an engineering partner across the repository rather than as a
one-shot code generator. Codex helped audit the existing code paths, turn
product decisions into scoped changes, implement the Investigator and API
boundary, write regression tests, rebuild the demo interface, and configure the
GitHub Pages deployment. That compressed the distance between an internal
engine and something another person can actually run and understand.

I kept the consequential product and engineering decisions human-owned. In
particular, I chose that the deterministic engine—not the model—must own case
identity, evidence state, urgency, and response posture; GPT-5.6 may only explain
saved results through allowlisted citations; and an operator must retain the
final field or security classification. I also chose to make the public demo
fictional and precomputed instead of exposing a key or implying live field
analysis.

GPT-5.6 contributes at runtime through the optional Investigator. It turns an
already-evaluated case into a concise brief while the server validates its
citations and copies the official decision fields from backend truth. Codex
contributed throughout development, testing, design iteration, documentation,
and deployment.

### What I learned and what was difficult

The biggest lesson was that the model becomes more useful when its authority is
narrower. Separating deterministic decisions from generative explanation made
the system easier to test, easier to trust, and easier to demonstrate.

The hardest parts were preserving continuity in a pre-existing case-based
system, making the explanation layer useful without letting it become a second
decision engine, and presenting a complicated operational workflow in under
three minutes. GitHub Pages added another constraint: the public site had to be
credible and interactive without a Python server or exposed API credentials.
The resulting demo shows the product contract while the repository retains the
working local engine and Investigator path.

## Quick start

Python 3.10+ and Node.js 20+ are recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/load_test_dataset.py demo_three_cases
python main.py
python -m uvicorn api:app --reload
```

On Windows, activate with `.venv\Scripts\Activate.ps1` and load a fixture with
`powershell -File scripts\Load-TestDataset.ps1 demo_three_cases`.

In a second terminal:

```bash
cd "Riskseer Frontend"
npm install
npm run dev
```

Open `http://localhost:5173`. The API runs at `http://127.0.0.1:8000`.

## OpenAI Investigator

Create an API key in your own OpenAI project and set it only in your local
environment. Never paste it into source code or commit it.

```bash
export OPENAI_API_KEY="your-key"
# Optional; defaults to gpt-5.6
export RISKSEER_OPENAI_MODEL="gpt-5.6"
```

The integration uses one OpenAI Agents SDK agent, three read-only case tools,
Pydantic structured output, and a server-side citation allowlist. See the
[OpenAI Agents SDK guide](https://developers.openai.com/api/docs/guides/agents)
and [structured output documentation](https://openai.github.io/openai-agents-python/agents/).

Useful endpoints:

- `GET /api/health`
- `GET /api/ai/status`
- `GET /api/cases`
- `POST /api/cases/{case_id}/investigate`

For a hosted frontend, set `VITE_API_BASE_URL`. For a hosted API, set the
comma-separated `RISKSEER_CORS_ORIGINS`. Raw report rows are excluded unless
`RISKSEER_API_DEBUG=true`.

## Validation

```bash
.venv/bin/python -m pytest
.venv/bin/python -m compileall -q .
cd "Riskseer Frontend"
npm run lint
npm run build
```

The staged continuity fixture is also available:

```bash
python scripts/load_test_dataset.py rim_rich/stage_01_baseline
python main.py
python scripts/load_test_dataset.py rim_rich/stage_02_evolution
python main.py
```

The second run should preserve three case threads and compare them with their
prior snapshots.

## Safety boundary

Riskseer is decision support, not a replacement for required locating,
verification, supervision, or emergency procedures. Model output is an
explanation of backend evidence—not authorization to proceed. The public
walkthrough includes a clearly labeled, fictional temporary-security scenario
to demonstrate a possible product extension. Temporary-security ontology is not
implemented by the current deterministic excavation engine.

## License

Riskseer is temporarily public for OpenAI Build Week evaluation. Original
Riskseer code and demo content remain proprietary and are provided under the
terms in [LICENSE](LICENSE). Third-party components remain subject to their own
licenses.
