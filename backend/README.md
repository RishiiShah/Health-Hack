# Command Center backend

This is the deterministic Detect–Decide–Act backend, with a durable event log, consult replay, coverage forecasts, recommendations and the approved offer loop. It uses PostgreSQL (Amazon RDS in deployment), one synchronous mutation coordinator, UTC timestamps, an injectable simulation clock, a separate server receipt clock, and immutable published consult state. Set `CC_DATABASE_URL`; the local default is `postgresql://postgres:postgres@127.0.0.1:5432/postgres`.

## Simple local startup

Reference uploads and verification for localhost and Render are documented in
[Persistent reference data](../docs/Reference-Data.md). Use the upload script's
`--check` option to verify the same persisted reference version in either environment.

The app always runs against the **production database and accounts**, locally too: there is no Docker stack or local database for running it. Install Python 3.14.7, then from `backend/`:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python --version  # Expected: Python 3.14.7
```

Copy `.env.example` to the root `.env` and fill in the production `CC_DATABASE_URL` (RDS, `sslmode=verify-full`, `sslrootcert` pointing at your local copy of the RDS CA bundle), `CC_USERS` and `CC_AUTH_SECRET`. Then run `make backend` from the repository root: `python -m app` reads the root `.env` (real environment variables win) and serves `http://localhost:8000`. Without `CC_DATABASE_URL` the server refuses to start; it never falls back to a local database. Sign in with your production account. Run `make web` for the frontend (Node 24); Vite forwards API requests to port 8000. Leave `VITE_DEMO_DATA` unset to use real sign-in.

The production database has one writer at a time: a local backend and a hosted one both writing to it reload and retry on conflict, but a reader may briefly serve older state. Avoid running both while demonstrating.

Tests never touch production: `make backend-test` runs the suite against a disposable local PostgreSQL at `CC_TEST_DATABASE_URL` (default `postgres:postgres@127.0.0.1:5432`), creating and dropping a database per test, and refuses to run if that URL is the production server.

`backend/.python-version`, CI and the Docker image select 3.14.7. Package metadata accepts patch releases from 3.14.7 through the 3.14 series; later minor versions require validation. Use standard CPython; free-threaded/JIT builds have not been validated. No hosted performance improvement is claimed; recorded local measurements have their stated scope. Recreate an existing 3.12 virtual environment rather than upgrading its interpreter in place.

The Render configuration runs one worker and reads `CC_DATABASE_URL` from the dashboard. The sample CSV adapter is explicit and versioned; source CSVs stay read-only. The fixture service date is March 17, 2026; `load_refs` takes it explicitly. For a deterministic snapshot run, set `CC_CLOCK_MODE=fixed` and `CC_CLOCK_FIXED=2026-03-17T18:20:00-04:00`.

Implemented now: canonical event contracts and validation; sample description normalization; PostgreSQL persistence and dedupe; batch ordering and watermark quality counts; future-event persistence; unresolved events are durably held for five server-time minutes and causal conflicts are quarantined; deterministic monotonic consult stage/ownership replay; commit-before-publication serialization; time refresh without replay when the visible event prefix is unchanged; health, readiness, event ingest, consult snapshot and consult detail routes.

**API (step 9).** Every route in the API contract of [00-Boundaries](../docs/00-Boundaries-and-Contracts.md) is implemented: `/me`, `/snapshot` (queue, coverage, physicians, hospitals, offers), `WS /ws?token=`, `/gaps/{id}/candidates`, `/gaps/{id}/trap-check`, `/interventions` (+ `/authorize`), `/offers` (propose, approve-and-send, reject, accept, decline, audio), `/audit`, `/alerts/{id}/audio`, `/events`, `/events/csv`, `/admin/reset`, `/admin/clock`, `/admin/physician-tokens`, `/admin/references`, `/schedule`, `/me/shift` and `/me/offers`. Every route except `/health`, `/ready` and `/auth/login` needs `Authorization: Bearer <token>`: an account token from `POST /auth/login` (web and mobile; accounts in `CC_USERS`, see `make backend`), a physician link from `/admin/physician-tokens`, or a fixed role token for scripts; the server checks the permission table on each request (401 bad token, 403 wrong role, 404 for another physician's offer). Commands accept an `Idempotency-Key` header. Decisions need the six reference CSVs, from `CC_DATA_DIR` or uploaded with `POST /admin/references` (`{files: {name: text}, service_date?, name?}`, or `scripts/upload_references.py <folder>`), which stores them in the database so restarts keep them; uploaded references take precedence over `CC_DATA_DIR`. Without either, `/ready` reports detection unavailable and decision routes return 503. See [Deployment](../docs/Deployment.md) for all settings, and [Decision engine](../docs/Decision-Engine.md) for the rules.

Run against a scenario pack, then load its events:

```sh
CC_DATA_DIR=../test_data/01_development/inputs CC_CLOCK_MODE=anchored CC_CLOCK_FIXED=2026-03-17T18:20:00-04:00 \
CC_COORDINATOR_TOKEN=c CC_LEAD_TOKEN=l CC_ADMIN_TOKEN=a CC_TOKEN_SECRET=s .venv/bin/python -m app
curl -H 'Authorization: Bearer a' -H 'Content-Type: text/csv' --data-binary @../test_data/01_development/inputs/event_stream.csv localhost:8000/events/csv
```

Measured locally (Postgres in Docker, development pack): ingest of the 1,710-row base file 53 ms; one appended event 6 ms; `/snapshot` recompute median 20 ms, cached 0.5 ms.

JSON rejects unknown top-level fields and blank identifiers with 422 before ingestion. Signed Off consults retain their final owner and history when later events arrive. JSON may omit `ingested_at`; the coordinator supplies server receipt time. CSV rows require both source timestamps. Structural HTTP validation failures return 422 before coordinator ingestion; semantic failures are durably quarantined; unresolved rows are held with fixed first-receipt deadlines. `ingest_raw` adds per-row G1 quarantine and persistent quality metrics for P1 upload integration. The current typed HTTP route still returns structural 422 errors before coordinator ingestion. The sample is not automatically loaded. Upload event CSVs through the Data page or `POST /events/csv`; `app.fixture.load_fixture` also supplies typed rows for direct test ingestion.

The local sample-backed test is explicitly skipped when gitignored source data is unavailable in CI. Synthetic checks still run; this is not a CI guarantee of full fixture parity. No hosted performance improvement is claimed; recorded local measurements have their stated scope.

Sign-in and roles: `POST /auth/login {email, password}` returns a 12-hour HMAC-signed bearer token; `GET /auth/me` returns the account. Roles are `coordinator`, `lead` and `physician`; the web app opens the account's workspace automatically. The optional legacy `portal` field still checks an explicitly selected portal and returns 403 on a mismatch. Each route checks the permission table in `app/auth.py`; `/health` and `/ready` stay open. Accounts come from `CC_USERS` plus `CC_AUTH_SECRET`, or the JSON file at `CC_AUTH_CONFIG`. Explicit `CC_AUTH_CONFIG` takes precedence over environment accounts, as described below. Missing configuration fails closed: with no accounts and no role tokens the server refuses to start, and there is no switch that turns sign-in off. The smoke script sends `CC_ADMIN_TOKEN` and `CC_COORDINATOR_TOKEN`; the stress script sends `CC_TOKEN`.

New password hashes use PBKDF2-HMAC-SHA256 with 600,000 iterations, following [OWASP's password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2). Existing valid hashes keep their stored work factors. Malformed hashes fail at startup. Auth responses use `Cache-Control: no-store`; malformed tokens fail closed. Each login gets a distinct token. The web client retains sessions within the tab, including an in-memory fallback when storage is blocked, revalidates the user on reload, and handles expiry without allowing a late response to clear a newer login. A connection failure offers retry without discarding credentials. Sign-out removes the browser session; server-side revocation, refresh tokens, password recovery and login rate limiting remain unimplemented. Use TLS and an authenticated/rate-limited gateway before exposing this demo to the internet.

Hosting preference is Render, then AWS EC2, then an Azure VM, all using RDS. The shared image reads `PORT` and `CC_DATABASE_URL`. See [Deployment](../docs/Deployment.md) for the Render Blueprint and VM Compose configuration. Multiple workers/replicas are unsupported by this architecture.

Runtime dependencies are limited to FastAPI (API/OpenAPI), plain Uvicorn (ASGI serving), Pydantic (event validation) and psycopg (PostgreSQL client; the standard library has none), plus their required transitive dependencies. CSV/JSON handling, configuration, clocks and hosting probes use the standard library. Synchronous routes use FastAPI’s thread pool so ingestion does not block the event loop. CSV upload uses the raw HTTP body. The implemented `/ws` transport uses the declared websockets dependency; optional server accelerators require measurements. See the repository `AGENTS.md` for the standard-library-first practice.

## Historical increment records

The following totals, SQLite-era measurements and pending-integration statements describe earlier increments. They are preserved as history; current behavior and validation are in [Gap fixes](../docs/Decision-Engine-Gap-Fixes.md) and [document authority](../docs/README.md).

Foundation hardening: 30 tests passed, including terminal-state preservation, strict input rejection, atomic row-limit rejection, concurrent ingestion/snapshots, clock rewind with late inserts, failed-commit isolation, and database cleanup on failed startup. The coordinator caches committed events and uses standard-library binary search for the visible prefix; unchanged snapshot reads avoid database scans and replay. Restart still reconstructs from the database. `/snapshot` caches its encoded response per revision, visible state and clock second; see [Deployment](../docs/Deployment.md#caching) for measurements. This assumes the documented single writer; activate references through the running API. The separately verified production seed ran with no application connections and preserved operational state. No comparative latency benchmark has been performed.

P2 now implements the G1–G8 domain layer: immutable roster/credential references, durable orphan holds and reference activation, persistent ingest quality, matched call/video/ring state, ownership history and note age, pure physician views, routing exclusions and active-shift counters. See [P2 handoff](../docs/P2-Backend.md) for the Python interfaces and remaining P1/P3 integration. The existing HTTP physician/reference panels remain unsupported until P1 wires these interfaces. Periodic idle orphan expiry requires P1 to schedule `sweep()`. No detection, forecasting, ranking or offer feature is included.

P2 verification: the full local suite passes 57 tests, including all supplied physician and consult snapshot fields. Of these, 55 tests use synthetic inputs independent of source data. `CC_ORPHAN_HOLD_S` configures the existing service’s hold deadline (default 300 seconds); pure physician views accept an explicit cooldown, defaulting to the config constant of 120 seconds.

Organizer-aligned regressions additionally verify other service dates/ID prefixes and a March 17 append without reset. Independent practice datasets use another date and unique prefixes; judging rehearsals remain isolated March 17 extensions. See [P2 handoff](../docs/P2-Backend.md).

### Accounts

Sign-in accounts come only from `CC_USERS` and `CC_AUTH_SECRET`: the same production accounts locally (root `.env`) and on the host. Create a password hash with `python -m app.auth`. In `.env`, wrap the `CC_USERS` JSON in single quotes so the hashes' `$` separators stay literal.
