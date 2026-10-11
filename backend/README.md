# Command Center backend scaffold

This is a runnable FastAPI foundation for the event log and consult replay. It uses PostgreSQL (Amazon RDS in deployment), one synchronous mutation coordinator, UTC timestamps, an injectable simulation clock, a separate server receipt clock, and immutable published consult state. Set `CC_DATABASE_URL`; the local default is `postgresql://postgres:postgres@127.0.0.1:5432/postgres`.

## Simple local startup

With Docker Desktop running, run this from the repository root:

```sh
make backend
```

The first run prompts for your email, name, role and password. The setup helper uses the host's standard-library Python only; the API runs in **Python 3.14.7** inside Docker, independently of an older local virtual environment. It saves salted password hashes and a random signing key in gitignored `backend/.local/auth.json` with mode 0600. It never supplies a default account password or disables authentication. Keep this file private. Subsequent starts reuse it without prompts.

Compose starts a dedicated PostgreSQL 17 service, waits for it to be healthy, and starts the API at `http://localhost:8000` with source reload. The database is not published to the host, so an existing PostgreSQL on ports 5432 or 5433 is unaffected. Compose mounts the kit's `data/` read-only as `CC_DATA_DIR` and passes the gitignored root `.env` (copy `.env.example`: demo clock, ElevenLabs key, optional role tokens) to the API. `PORT=8001 make backend` changes the host API port; use the same `API_URL` when starting Vite. Stop with Ctrl-C or `make backend-down`; the named database volume is preserved.

`make backend-account` adds another account, keeping existing accounts and the signing key. Restart the backend with the command it prints to load the new account. `make backend-test` runs the backend suite using the same pinned Python version and isolated throwaway databases; it needs no sign-in setup and never deletes the application database. Source CSVs are not mounted into the test container, so source-data tests are skipped there.

For the frontend, run `npm run dev` in `web/` (Node 24); its proxy forwards API requests to port 8000 by default. Leave `VITE_DEMO_DATA` unset to use real sign-in. `VITE_DEMO_DATA=1` uses separate in-memory demo accounts instead of this backend.

## Native setup (optional)

For a fresh native environment, install Python 3.14.7, then run from `backend/`:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python --version  # Expected: Python 3.14.7
```

Provide `CC_DATABASE_URL` for your PostgreSQL server and either `CC_USERS` plus `CC_AUTH_SECRET` or `CC_AUTH_CONFIG` pointing to your private local auth JSON. Start with `.venv/bin/python -m app`. For native tests, set `CC_TEST_DATABASE_URL` and run `.venv/bin/python -m pytest -q`. Tests create and drop a throwaway database per test. Verify the interpreter before reusing an existing `.venv`; its presence does not guarantee the correct version.

`backend/.python-version`, CI and the Docker image select 3.14.7. Package metadata accepts patch releases from 3.14.7 through the 3.14 series; later minor versions require validation. Use standard CPython; free-threaded/JIT builds have not been validated. Runtime performance remains unmeasured. Recreate an existing 3.12 virtual environment rather than upgrading its interpreter in place.

The Render configuration runs one worker and reads `CC_DATABASE_URL` from the dashboard. The sample CSV adapter is explicit and versioned; source CSVs stay read-only. The fixture service date is March 17, 2026; `load_refs` takes it explicitly. For a deterministic snapshot run, set `CC_CLOCK_MODE=fixed` and `CC_CLOCK_FIXED=2026-03-17T18:20:00-04:00`.

Implemented now: canonical event contracts and validation; sample description normalization; PostgreSQL persistence and dedupe; batch ordering and watermark quality counts; future-event persistence; unresolved events are durably held for five server-time minutes and causal conflicts are quarantined; deterministic monotonic consult stage/ownership replay; commit-before-publication serialization; time refresh without replay when the visible event prefix is unchanged; health, readiness, event ingest, consult snapshot and consult detail routes.

**API (step 9).** Every route in the API contract of [00-Boundaries](../docs/00-Boundaries-and-Contracts.md) is implemented: `/me`, `/snapshot` (queue, coverage, physicians, hospitals, offers), `WS /ws?token=`, `/schedule` (the day's roster for the web Schedule screen), `/gaps/{id}/candidates`, `/gaps/{id}/trap-check`, `/interventions` (+ `/authorize`), `/offers` (propose, approve-and-send, reject, accept, decline, audio), `/audit`, `/alerts/{id}/audio`, `/events`, `/events/csv`, `/admin/reset`, `/admin/clock`, `/admin/physician-tokens`. Every route except `/health`, `/ready` and `/auth/login` needs `Authorization: Bearer <token>`: an account token from `POST /auth/login` (web and mobile; accounts in `CC_USERS`, see `make backend`), a physician link from `/admin/physician-tokens`, or a fixed role token for scripts; the server checks the permission table on each request (401 bad token, 403 wrong role, 404 for another physician's offer). Commands accept an `Idempotency-Key` header. Decisions need the reference CSVs in `CC_DATA_DIR`; without them `/ready` reports detection unavailable and decision routes return 503. See [Deployment](../docs/Deployment.md) for all settings, and [Decision engine](../docs/Decision-Engine.md) for the rules.

Run against a scenario pack, then load its events:

```sh
CC_DATA_DIR=../test_data/01_development/inputs CC_CLOCK_MODE=anchored CC_CLOCK_FIXED=2026-03-17T18:20:00-04:00 \
CC_COORDINATOR_TOKEN=c CC_LEAD_TOKEN=l CC_ADMIN_TOKEN=a CC_TOKEN_SECRET=s .venv/bin/python -m app
curl -H 'Authorization: Bearer a' -H 'Content-Type: text/csv' --data-binary @../test_data/01_development/inputs/event_stream.csv localhost:8000/events/csv
```

Measured locally (Postgres in Docker, development pack): ingest of the 1,710-row base file 53 ms; one appended event 6 ms; `/snapshot` recompute median 20 ms, cached 0.5 ms.

JSON rejects unknown top-level fields and blank identifiers with 422 before ingestion. Signed Off consults retain their final owner and history when later events arrive. JSON may omit `ingested_at`; the coordinator supplies server receipt time. CSV rows require both source timestamps. Structural HTTP validation failures return 422 before coordinator ingestion; semantic failures are durably quarantined; unresolved rows are held with fixed first-receipt deadlines. `ingest_raw` adds per-row G1 quarantine and persistent quality metrics for P1 upload integration. The current typed HTTP route still returns structural 422 errors before coordinator ingestion. The sample is not automatically loaded: `app.fixture.load_fixture` supplies typed rows for `MutationCoordinator.ingest`; CSV upload is pending.

The local sample-backed test is explicitly skipped when gitignored source data is unavailable in CI. Synthetic checks still run; this is not a CI guarantee of full fixture parity. Runtime performance remains unmeasured.

Sign-in and roles: `POST /auth/login {email, password}` returns a 12-hour HMAC-signed bearer token; `GET /auth/me` returns the account. Roles are `coordinator`, `lead` and `physician`; the web app opens the account's workspace automatically. The optional legacy `portal` field still checks an explicitly selected portal and returns 403 on a mismatch. Each route checks the permission table in `app/auth.py`; `/health` and `/ready` stay open. Accounts come from `CC_USERS` plus `CC_AUTH_SECRET`, or the JSON file at `CC_AUTH_CONFIG`. Explicit `CC_USERS` takes precedence over that file. Missing configuration fails closed: with no accounts and no role tokens the server refuses to start, and there is no switch that turns sign-in off. The smoke script sends `CC_ADMIN_TOKEN` and `CC_COORDINATOR_TOKEN`; the stress script sends `CC_TOKEN`.

New password hashes use PBKDF2-HMAC-SHA256 with 600,000 iterations, following [OWASP's password-storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2). Existing valid hashes keep their stored work factors. Malformed hashes fail at startup. Auth responses use `Cache-Control: no-store`; malformed tokens fail closed. Each login gets a distinct token. The web client retains sessions within the tab, including an in-memory fallback when storage is blocked, revalidates the user on reload, and handles expiry without allowing a late response to clear a newer login. A connection failure offers retry without discarding credentials. Sign-out removes the browser session; server-side revocation, refresh tokens, password recovery and login rate limiting remain unimplemented. Use TLS and an authenticated/rate-limited gateway before exposing this demo to the internet.

Hosting preference is Render, then AWS EC2, then an Azure VM, all using RDS. The shared image reads `PORT` and `CC_DATABASE_URL`. See [Deployment](../docs/Deployment.md) for the Render Blueprint and VM Compose configuration. Multiple workers/replicas are unsupported by this architecture.

Runtime dependencies are limited to FastAPI (API/OpenAPI), plain Uvicorn (ASGI serving), Pydantic (event validation) and psycopg (PostgreSQL client; the standard library has none), plus their required transitive dependencies. CSV/JSON handling, configuration, clocks and hosting probes use the standard library. Synchronous routes use FastAPI’s thread pool so ingestion does not block the event loop. Multipart uploads and WebSocket transport dependencies are deferred until those routes are implemented; optional server accelerators require measurements. See the repository `AGENTS.md` for the standard-library-first practice.

Foundation hardening: 30 tests pass, including terminal-state preservation, strict input rejection, atomic row-limit rejection, concurrent ingestion/snapshots, clock rewind with late inserts, failed-commit isolation, and database cleanup on failed startup. The coordinator caches committed events and uses standard-library binary search for the visible prefix; unchanged snapshot reads avoid database scans and replay. Restart still reconstructs from the database. `/snapshot` caches its encoded response per revision, visible state and clock second; see [Deployment](../docs/Deployment.md#caching) for measurements. This assumes the documented single writer; direct database mutation is unsupported. No comparative latency benchmark has been performed.

P2 now implements the G1–G8 domain layer: immutable roster/credential references, durable orphan holds and reference activation, persistent ingest quality, matched call/video/ring state, ownership history and note age, pure physician views, routing exclusions and active-shift counters. See [P2 handoff](../docs/P2-Backend.md) for the Python interfaces and remaining P1/P3 integration. The existing HTTP physician/reference panels remain unsupported until P1 wires these interfaces. Periodic idle orphan expiry requires P1 to schedule `sweep()`. No detection, forecasting, ranking or offer feature is included.

P2 verification: the full local suite passes 57 tests, including all supplied physician and consult snapshot fields. Of these, 55 tests use synthetic inputs independent of source data. `CC_ORPHAN_HOLD_S` configures the existing service’s hold deadline (default 300 seconds); pure physician views accept an explicit cooldown, defaulting to the config constant of 120 seconds.

Organizer-aligned regressions additionally verify other service dates/ID prefixes and a March 17 append without reset. Independent practice datasets use another date and unique prefixes; judging rehearsals remain isolated March 17 extensions. See [P2 handoff](../docs/P2-Backend.md).

### Local account configuration precedence

`make backend` mounts `backend/.local/auth.json` as `CC_AUTH_CONFIG`. That explicit file takes precedence over `CC_USERS` and `CC_AUTH_SECRET`, so old environment accounts cannot override accounts created by `make backend-account`. Without `CC_AUTH_CONFIG`, deployments continue to use the environment accounts.

If supplying `CC_USERS` in a Compose `.env` file, wrap the entire JSON value in single quotes to preserve the password hashes’ literal `$` separators. [Docker documents single-quoted values as literal](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
