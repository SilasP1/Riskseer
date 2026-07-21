# Riskseer frontend

The React client presents backend-evaluated Riskseer cases. It does not assign
case decisions, urgency, or response posture.

```bash
npm install
npm run dev
```

The app expects the API at `http://127.0.0.1:8000` by default. Override it with
`VITE_API_BASE_URL` when needed. GitHub Pages builds with `VITE_STATIC_DEMO=true`,
which presents the guided Thistle + Riskseer scenario walkthrough. Local/API
mode retains the full case queue and investigator interface. Run `npm run lint`
and `npm run build` before publishing changes.

The repository root also mirrors the compiled static entry point and hashed
assets. This keeps the current branch-based Pages fallback consistent with the
Actions deployment; refresh that mirror after changing the public demo bundle.
