# Sevaro Command Center

Tele-neurology operations command center for the Sevaro / Rutgers Health Hack (Challenge 2). It rebuilds physician and consult state from an event stream, surfaces what needs attention now and in the next 90 minutes, recommends the cheapest safe fix, and runs the full approval loop to act on it. All decisions are deterministic and explainable; no AI/ML.

## Live demo

**https://cerevia.dev**

Sign in with a demo account below. All data is synthetic (no real patients, physicians, or hospitals).

| Role | Email | Password |
| --- | --- | --- |
| Coordinator | `coordinator@sevaro.com` | `Sevaro-d4f377` |
| Clinical lead | `lead@sevaro.com` | `Sevaro-046e59` |
| Physician | `physician@sevaro.com` | `Sevaro-afed88` |

- **Coordinator** sees the full network: attention queue, breaches, physician activity, projected coverage gaps, and proposes fixes.
- **Clinical lead** approves or rejects split-shift offers and authorizes escalations.
- **Physician** sees only their own offers and accepted shifts (the phone view).

## What it does

Three required layers, computed server-side on the replayed event state:

1. **Detect** — consults breaching time standards, demand surges above a hospital's baseline, credentialed coverage falling below the required level now or after upcoming shift ends, and physician signals that contradict each other.
2. **Decide** — the cheapest safe fix per problem, with the approver named: reassign a consult, escalate a critical stroke, wait for a scheduled shift, or offer an off-shift physician a short split shift. Every off-shift physician is shown with the rule each one passed or failed.
3. **Act** — propose → clinical-lead approval → send (no patient data) → accept/decline/10-min timeout → recompute coverage → stop offering once the gap is filled, with an append-only audit log.

A simulation guard handles the split-shift trap, so a called-in physician relieves the gap instead of absorbing every call.

## Tech stack

| Layer | Choice |
| --- | --- |
| Backend | Python 3.14.7, FastAPI, Pydantic v2, Uvicorn |
| Engine | Pure-Python deterministic replay (standard library first), injected clock |
| Database | PostgreSQL via psycopg 3 (append-only event log, quarantine, audit) |
| Web dashboard | React 19, TypeScript, Vite, Tailwind CSS, ECharts |
| Mobile (lead + physician) | Flutter (web build), role-based dashboard |
| API contract | OpenAPI schema → `openapi-typescript` generates the web types |
| Tests & CI | pytest, Node test runner, Flutter test, GitHub Actions |
| Hosting | Render (Docker image serves the API and the built web app); AWS fallback, Azure last resort |

## Repository layout

- `backend/` — FastAPI app, replay engine, detection/decide/act layers, tests.
- `web/` — React + Vite operations dashboard.
- `mobile/` — Flutter app for the clinical lead and physician roles.
- `docs/` — PRD, backend architecture, deployment, and team handoffs.
- `scripts/` — read-only data audit and hosting smoke tests.
- `data/` — supplied synthetic CSVs (gitignored, unchanged).

## Running locally

The app uses the production database and accounts, locally too; there is no local database to run. Copy `.env.example` to `.env`, fill in `CC_DATABASE_URL`, `CC_USERS`, and `CC_AUTH_SECRET`, then from this directory:

```sh
make backend   # API on http://localhost:8000
make web       # dashboard on http://localhost:5173
```

Sign in with your account. See the [backend guide](backend/README.md) for setup and tests.

Run the independent, read-only fixture audit:

```sh
python3 scripts/audit_sample_data.py --data-dir data
```

## Documentation

- [PRD v2.3](docs/Sevaro%20Command%20Center%20PRD%20v2.md): scope, fixture expectations, acceptance tests, and operations priorities.
- [Backend architecture](docs/Command%20Center%20Backend%20Scaffold.md): interfaces, state consistency, and performance requirements.
- [Fixture review](docs/Backend%20Scaffold%20Review.md): source-data findings and outstanding decisions.
- [Backend foundation](backend/README.md): implemented features, local setup, and tests.
- [P2 backend handoff](docs/P2-Backend.md): G1–G8 domain interfaces, verification, and team integration.
- [Deployment](docs/Deployment.md): Render first, AWS fallback, Azure last resort.
