# Deployment: Render first, AWS second, Azure last

The same Python 3.14.7 Docker image runs on all three providers. It binds `0.0.0.0:$PORT` (default 8000), keeps one uvicorn worker, writes logs to stdout/stderr, handles SIGTERM directly and closes its database connections during application shutdown. `/health` is liveness; `/ready` checks startup and reports capabilities. Sign-in and role checks protect the implemented operations routes; [document authority](README.md) records current functionality and open policy differences.

Events, holds, quarantine and metrics live in **Amazon RDS for PostgreSQL** (see the decision record in [Boundaries and Contracts](00-Boundaries-and-Contracts.md)). The application process has no local durable state, so any host that can reach RDS can run it.

| Preference | Deployment | Durable storage | Process count |
| --- | --- | --- | --- |
| 1 | Render Docker web service, root `render.yaml`, Oregon region | RDS PostgreSQL in us-west-2, database `commandcenter_v2` | 1 service instance, 1 worker |
| 2 | AWS EC2 Linux VM in us-west-2 running `deploy/compose.yaml` | Same RDS instance | 1 container, 1 worker |
| 3 | Azure Linux VM running the same Compose file | Same RDS instance (cross-cloud latency; measure first) | 1 container, 1 worker |

These are executable application deployment configurations, not verified hosted application deployments. The RDS instance is in **us-west-2**, and `render.yaml` targets the matching Oregon region. This code uses the database **commandcenter_v2** on that instance: the official Sevaro kit, its 1,163 events with the replay clock paused at 18:20 ET, and the four `test_data` packs stored as switchable kits (see [Reference data](Reference-Data.md)). The older **commandcenter** database on the same instance was written by a different, unpushed backend version with its own tables and reference format; this code cannot read that format, so it is left untouched. Use private access or a TLS and rate-limited gateway for hosted demos; session revocation, refresh, password recovery and login rate limiting are not implemented in the app.

Local development uses the same production database and accounts: `make backend` runs `python -m app` from the backend virtual environment, reading the root `.env`. There is no local Docker stack or local database; only the test suite uses a disposable local PostgreSQL. See the [backend guide](../backend/README.md).

The runtime is pinned to standard CPython 3.14.7 in `backend/Dockerfile` (`python:3.14.7-slim`), CI and `backend/.python-version`. Package metadata allows Python >=3.14.7,<3.15.

## One process, by design

The backend keeps replay state in memory and is the single writer. RDS makes data durable; it does not make a second process safe. Keep `numInstances: 1` and one worker. Every commit checks the database revision it last loaded. If another instance has written since (for example, Render's old and new instances overlapping during a zero-downtime deploy), the writer reloads the event log from RDS and retries once instead of overwriting it. A reader on the instance that did not write may serve the older state until its next write or restart.

Admin clock changes persist their override before publishing it. CSV uploads with `advance_clock=true` commit newly accepted events, any safe clock advance and the durable upload receipt in one PostgreSQL transaction. Only accepted events advance the clock, and automatic advances over 24 hours require explicit date review and clock control. See [CSV audit](CSV-Ingestion-Audit.md). On restart, a saved override takes precedence over `CC_CLOCK_MODE`/`CC_CLOCK_FIXED`. A paused clock resumes at exactly its saved time; a running anchored clock adds elapsed receipt-clock time, including downtime, with negative elapsed time clamped to zero. Its monotonic timer restarts in the new process. Explicit clocks injected by tests take precedence over saved metadata. Receipt and authentication clocks remain independent of simulation time. See `backend/tests/test_clock_recovery.py` for restart and failed-commit checks.

## Database connection

Set `CC_DATABASE_URL` to a libpq URL. For RDS, require certificate verification with the CA bundle baked into the image:

```text
postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem
```

The tables are created at startup (`CREATE TABLE IF NOT EXISTS`); there is no migration tool. Restrict the RDS security group to the backend's outbound addresses. Each commit is a few network round trips (inserts are batched), so keep the backend in the same region as RDS.

## Caching

`GET /snapshot` caches its encoded JSON in process. A commit or a newly visible event re-encodes it immediately; otherwise readers in the same second share one encoding, so only `clock.now` and the minute counters can lag by under a second. Reads never touch the database. No external cache (Redis/ElastiCache) is used: with one process it would add a network hop and a dependency without removing any work.

Measured locally (macOS arm64, Docker Postgres 17, 2,000 open consults, 16 keep-alive readers plus 5 single-event writes/s for 15 s, `scripts/stress.py`):

| Build | Snapshot throughput | Snapshot p95 | Ingest p95 |
| --- | --- | --- | --- |
| Before: SQLite, no cache | 62/s | 333 ms | 324 ms |
| After: Postgres + snapshot cache | 5,615/s | 3.5 ms | 28 ms |

Local Postgres has sub-millisecond round trips; repeat the run against the deployed service and RDS before quoting ingest latency. Run the stress script only against a disposable database; it writes synthetic consults:

```sh
python3 scripts/stress.py --url https://YOUR-SERVICE --seed 2000 --readers 16 --seconds 30 --write-rate 5
```

## Render

1. Use the RDS database **commandcenter_v2** in **us-west-2**, whose official reference kit and 1,163 events are already persisted. Its URL is the existing RDS URL with the database name changed; keep `sslmode=verify-full` and the RDS CA bundle (`sslrootcert`).
2. Create a Render Blueprint from the repository's root `render.yaml` (Oregon, matching the database). It builds `backend/Dockerfile` from the repository root, so one service serves the API and the built web app on the same origin (`CC_WEB_DIR`); the web app needs no CORS or separate host. One instance, `/ready` as the health check.
3. Set `CC_DATABASE_URL` in the Render dashboard (it is marked `sync: false`, so it never lives in Git). Keep `PORT` managed by Render. Do not run more than one worker or instance.
4. Confirm `/ready` responds and `/` shows the sign-in page. If the stored replay clock was saved paused, press Resume on the Data page once; a stored clock overrides `CC_CLOCK_MODE`. A new database starts with an empty event log and, since the image has no reference CSVs, with decisions off (`detection: false`).
5. Upload the six reference CSVs once: `python3 scripts/upload_references.py data --url https://YOUR-SERVICE --service-date 2026-03-17` (`--service-date` only for the kit's sample layout). They are stored in the database, so restarts and redeploys keep them; `/ready` then reports `detection: true`. Repeat with `--check` to compare the stored fingerprint with localhost. Matching uploads do not write. The first kit must be the official Sevaro kit; later kits are stored beside it and never replace it. See [persistent reference data](Reference-Data.md) for exact commands, the local kit fingerprint, and replay-clock setup.
6. Verify persistence with `scripts/hosting_smoke.py seed`, a manual redeploy, then `verify`, against a disposable database before loading real operational data.

## AWS fallback

Use an EC2 Linux VM in us-west-2 with Docker Engine and Compose installed. From the repository root:

```sh
export CC_DATABASE_URL='postgresql://...?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem'
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml ps
curl --fail http://127.0.0.1:8000/ready
```

Install a TLS reverse proxy on the same host that forwards to `127.0.0.1:8000`, or place a load balancer in front of it. The Compose service exposes the application only on loopback. The proxy must preserve forwarding headers and support WebSockets for clients using the implemented `/ws` transport.

## Azure last resort

Use an Azure Linux VM with Docker Engine and Compose and the same commands. The database stays in RDS, so every commit crosses clouds; measure ingest latency with the stress script before relying on it.

## Environment

| Variable | Meaning | Container / deployment default |
| --- | --- | --- |
| `PORT` | HTTP port; integer 1–65535 | 8000; Render supplies its own |
| `CC_DATABASE_URL` | PostgreSQL URL (RDS in deployment) | local `postgres:postgres@127.0.0.1:5432/postgres` |
| `CC_USERS` | JSON list of accounts: `email`, `name`, `role` (`coordinator`, `lead` or `physician`), `password_hash` from `python -m app.auth`, and `physician_id` for physicians | needed for web and mobile sign-in; without accounts only the fixed role tokens work, and with neither the server refuses to start |
| `CC_AUTH_SECRET` | 32+ random characters that sign sign-in tokens (`python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) | required with `CC_USERS` |
| `CC_DATA_DIR` | Reference CSVs (hospitals, shifts, off-shift roster, credentials, baseline volume, coverage requirements), sample or scenario-pack layout. Missing: the API runs, `/ready` reports detection unavailable, decision routes return 503. References uploaded with `POST /admin/references` are kept in the database and take precedence; hosted deployments use only the upload | unset |
| `CC_CLOCK_MODE` | `auto`, `wall`, `anchored`, `fixed` | `auto` |
| `CC_CLOCK_FIXED` | Offset-aware fixed/anchor time, when needed | unset |
| `CC_OFFER_HISTORY` | Offers sent outside this tool (`offer_id, physician_id, sent_at, status`), counted for R7/R8 | unset |
| `CC_COORDINATOR_TOKEN`, `CC_LEAD_TOKEN`, `CC_ADMIN_TOKEN` | Fixed demo tokens per role; an unset token means that role cannot sign in | unset |
| `CC_LEAD_NAME` | Clinical lead's display name, written to the audit log as approver | `Clinical lead` |
| `CC_TOKEN_SECRET` | Signs physician tokens (`POST /admin/physician-tokens`); unset = no physician sign-in | unset |
| `CC_SWEEP_S` | Seconds between background sweeps (offer expiry, orphan deadlines); 0 = only on requests | `5` |
| `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_MODEL_ID` | Text-to-speech; unset = audio routes return 503 and clients show the text | unset |
| `CC_SERVICE_DATE` | Service date for the sample layout, whose shift times have no date (pack layout ignores it) | unset |

Backups use RDS automated backups and snapshots. To move providers, point the new host at the same RDS instance, stop the old one, and verify replay before switching traffic.

## Verification

CI runs the backend tests against a `postgres:17` service container, then builds the image, starts it against Postgres, commits a synthetic consult, replaces the container and checks recovery from the database.

The latest local validation passed 337 backend tests against PostgreSQL; a source-only checkout passed 169 tests with 36 protected-source/pack skips. Current cohort results are recorded in [Decision-engine gap fixes](Decision-Engine-Gap-Fixes.md). The earlier image-level flow (build, seed, health probe, replace, verify) passed against local PostgreSQL, and the image loads the RDS CA bundle. The production RDS reference load verified certificate and hostname validation over TLS 1.3, durable reconnect recovery, and unchanged operational state. No hosted application deployment was performed in this step; application-level recovery on Render remains unverified.
