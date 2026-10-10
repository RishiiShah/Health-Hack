# Deployment: Render first, AWS second, Azure last

The same Python 3.14.7 Docker image runs on all three providers. It binds `0.0.0.0:$PORT` (default 8000), keeps one uvicorn worker, writes logs to stdout/stderr, handles SIGTERM directly and closes its database connection during application shutdown. `/health` is liveness; `/ready` checks startup of the implemented consult-replay foundation and reports unsupported capabilities. Authentication and the remaining operations gates are still pending.

Events, holds, quarantine and metrics live in **Amazon RDS for PostgreSQL** (see the decision record in [Boundaries and Contracts](00-Boundaries-and-Contracts.md)). The application process has no local durable state, so any host that can reach RDS can run it.

| Preference | Deployment | Durable storage | Process count |
| --- | --- | --- | --- |
| 1 | Render Docker web service, root `render.yaml`, Virginia region | RDS PostgreSQL in us-east-1 | 1 service instance, 1 worker |
| 2 | AWS EC2 Linux VM in us-east-1 running `deploy/compose.yaml` | Same RDS instance | 1 container, 1 worker |
| 3 | Azure Linux VM running the same Compose file | Same RDS instance (cross-cloud latency; measure first) | 1 container, 1 worker |

These are executable deployment configurations, not completed cloud deployments. No infrastructure has been provisioned, including the RDS instance. Until mutation authentication is implemented, use private access or an authenticated gateway for hosted demos.

The runtime is pinned to standard CPython 3.14.7 in `backend/Dockerfile` (`python:3.14.7-slim`), CI and `backend/.python-version`. Package metadata allows Python >=3.14.7,<3.15.

## One process, by design

The backend keeps replay state in memory and is the single writer. RDS makes data durable; it does not make a second process safe. Keep `numInstances: 1` and one worker. Every commit checks the database revision it last loaded. If another instance has written since (for example, Render's old and new instances overlapping during a zero-downtime deploy), the writer reloads the event log from RDS and retries once instead of overwriting it. A reader on the instance that did not write may serve the older state until its next write or restart.

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

1. Create the RDS instance in us-east-1 and a database for the service.
2. Create a Render Blueprint from the repository's root `render.yaml`. It runs the Dockerfile in the Virginia region with one instance and `/ready` as the health check.
3. Set `CC_DATABASE_URL` in the Render dashboard (it is marked `sync: false`, so it never lives in Git). Keep `PORT` managed by Render. Do not run more than one worker or instance.
4. Confirm `/ready` responds. A new database starts with an empty event log.
5. Verify persistence with `scripts/hosting_smoke.py seed`, a manual redeploy, then `verify`, against a disposable database before loading real operational data.

## AWS fallback

Use an EC2 Linux VM in us-east-1 with Docker Engine and Compose installed. From the repository root:

```sh
export CC_DATABASE_URL='postgresql://...?sslmode=verify-full&sslrootcert=/etc/ssl/certs/rds-global-bundle.pem'
docker compose -f deploy/compose.yaml up -d --build
docker compose -f deploy/compose.yaml ps
curl --fail http://127.0.0.1:8000/ready
```

Install a TLS reverse proxy on the same host that forwards to `127.0.0.1:8000`, or place a load balancer in front of it. The Compose service exposes the application only on loopback. The proxy must preserve forwarding headers and support WebSockets when those routes are implemented.

## Azure last resort

Use an Azure Linux VM with Docker Engine and Compose and the same commands. The database stays in RDS, so every commit crosses clouds; measure ingest latency with the stress script before relying on it.

## Environment

| Variable | Meaning | Container / deployment default |
| --- | --- | --- |
| `PORT` | HTTP port; integer 1–65535 | 8000; Render supplies its own |
| `CC_DATABASE_URL` | PostgreSQL URL (RDS in deployment) | local `postgres:postgres@127.0.0.1:5432/postgres` |
| `CC_DATA_DIR` | Reference CSVs (hospitals, shifts, off-shift roster, credentials, baseline volume, coverage requirements), sample or scenario-pack layout. Missing: the API runs, `/ready` reports detection unavailable, decision routes return 503 | `/data/ref` |
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

Locally, the suite passes 59 tests against Postgres 17, including both source-data tests. The same image-level flow (build, seed, health probe, replace, verify) passed against a local Postgres, and the image loads the RDS CA bundle. No Render, AWS or Azure deployment was performed, and TLS against a real RDS endpoint has not been exercised.
