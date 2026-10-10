# Command Center backend scaffold

This is a runnable FastAPI foundation for the event log and consult replay. It uses SQLite in WAL mode, one synchronous mutation coordinator, UTC timestamps, an injectable simulation clock, a separate server receipt clock, and immutable published consult state. Set `CC_DB_PATH` to a durable location in deployment. Local defaults place the database at `backend/cc.db`.

The project-local `.venv` uses Python 3.14.7 and has the test dependencies installed. From this directory, run:

```sh
.venv/bin/uvicorn app.main:app --reload
.venv/bin/python -m pytest -q
```

For a fresh checkout, install Python 3.14.7, then run:

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python --version  # Expected: Python 3.14.7
```

`backend/.python-version`, CI and the Docker image select 3.14.7. Package metadata accepts patch releases from 3.14.7 through the 3.14 series; later minor versions require validation. Use standard CPython; free-threaded/JIT builds have not been validated. Runtime performance remains unmeasured. Recreate an existing 3.12 virtual environment rather than upgrading its interpreter in place.

The Render configuration runs one worker and points SQLite at its persistent disk. The sample CSV adapter is explicit and versioned; source CSVs stay read-only. The fixture service date is March 17, 2026; `load_refs` takes it explicitly. For a deterministic snapshot run, set `CC_CLOCK_MODE=fixed` and `CC_CLOCK_FIXED=2026-03-17T18:20:00-04:00`.

Implemented now: canonical event contracts and validation; sample description normalization; SQLite persistence and dedupe; batch ordering and watermark quality counts; future-event persistence; unresolved events are durably held for five server-time minutes and causal conflicts are quarantined; deterministic monotonic consult stage/ownership replay; commit-before-publication serialization; time refresh without replay when the visible event prefix is unchanged; health, readiness, event ingest, consult snapshot and consult detail routes.

Readiness and snapshot responses expose capabilities. API wiring for physician activity and reference loading/validation, detections G8b–G15, coverage forecasts, WebSockets, upload endpoints, authentication, reset/clock administration, and stretch assignment/offer workflows are not implemented. The empty panel payloads are marked unsupported and must not be read as zero alerts, healthy staffing, or validated eligibility. Readiness means the durable consult-replay service started, not that the complete command center is operational. Serve this unauthenticated foundation locally while those features are pending.

JSON rejects unknown top-level fields and blank identifiers with 422 before ingestion. Signed Off consults retain their final owner and history when later events arrive. JSON may omit `ingested_at`; the coordinator supplies server receipt time. CSV rows require both source timestamps. Structural HTTP validation failures return 422 before coordinator ingestion; semantic failures are durably quarantined; unresolved rows are held with fixed first-receipt deadlines. `ingest_raw` adds per-row G1 quarantine and persistent quality metrics for P1 upload integration. The current typed HTTP route still returns structural 422 errors before coordinator ingestion. The sample is not automatically loaded: `app.fixture.load_fixture` supplies typed rows for `MutationCoordinator.ingest`; CSV upload is pending.

The local sample-backed test is explicitly skipped when gitignored source data is unavailable in CI. Synthetic checks still run; this is not a CI guarantee of full fixture parity. Runtime performance remains unmeasured.

Hosting preference is Render, then AWS EC2 with an EBS disk, then an Azure VM with a managed disk. The shared image reads `PORT` and defaults persistent paths to `/data`. See [Deployment](../docs/Deployment.md) for the Render Blueprint and VM Compose configuration. Network-file-backed SQLite and multiple workers/replicas are unsupported by this architecture.

Runtime dependencies are limited to FastAPI (API/OpenAPI), plain Uvicorn (ASGI serving), and Pydantic (event validation), plus their required transitive dependencies. CSV/JSON handling, SQLite, configuration, clocks and hosting probes use the standard library. Synchronous routes use FastAPI’s thread pool so ingestion does not block the event loop. Multipart uploads and WebSocket transport dependencies are deferred until those routes are implemented; optional server accelerators require measurements. See the repository `AGENTS.md` for the standard-library-first practice.

Foundation hardening: 30 tests pass, including terminal-state preservation, strict input rejection, atomic row-limit rejection, concurrent ingestion/snapshots, clock rewind with late inserts, failed-commit isolation, and database cleanup on failed startup. The coordinator caches committed events and uses standard-library binary search for the visible prefix; unchanged snapshot reads avoid database scans and replay. Restart still reconstructs from SQLite. This assumes the documented single writer; direct database mutation is unsupported. No comparative latency benchmark has been performed.

P2 now implements the G1–G8 domain layer: immutable roster/credential references, durable orphan holds and reference activation, persistent ingest quality, matched call/video/ring state, ownership history and note age, pure physician views, routing exclusions and active-shift counters. See [P2 handoff](../docs/P2-Backend.md) for the Python interfaces and remaining P1/P3 integration. The existing HTTP physician/reference panels remain unsupported until P1 wires these interfaces. Periodic idle orphan expiry requires P1 to schedule `sweep()`. No detection, forecasting, ranking or offer feature is included.

P2 verification: the full local suite passes 57 tests, including all supplied physician and consult snapshot fields. Of these, 55 tests use synthetic inputs independent of source data. `CC_ORPHAN_HOLD_S` configures the existing service’s hold deadline (default 300 seconds); pure physician views accept an explicit cooldown, defaulting to the config constant of 120 seconds.

Organizer-aligned regressions additionally verify other service dates/ID prefixes and a March 17 append without reset. Independent practice datasets use another date and unique prefixes; judging rehearsals remain isolated March 17 extensions. See [P2 handoff](../docs/P2-Backend.md).
