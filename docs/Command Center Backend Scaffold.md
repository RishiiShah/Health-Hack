# Command Center Backend Scaffold

Oct 10, 2026 · @Rishabh

## Architecture

One FastAPI process, one uvicorn worker, one serialized mutation coordinator, and immutable published state rebuilt from a durable ordered event log. Replay never reads the clock. API orchestration samples one `as_of` and passes it to detection and every panel builder.

**Review update (Oct 10):** the supplied fixtures differ materially from the PRD's example values. See [Backend Scaffold Review](Backend%20Scaffold%20Review.md) for verified differences and the remaining policy decisions. Source CSVs remain unchanged. Resolve those differences before freezing fixture assertions.

&#91;embedded content: backend data flow · 7 stages\]

A late event is inserted by normalized UTC `event_time`. Initially replay once per accepted **batch**, rather than once per row. Full replay is a reasonable starting point for 1,163 unique sample events; its latency is unmeasured. Benchmark before claiming milliseconds. Keep the full replay as a correctness oracle if incremental updates are introduced later.

The operations objective is to reduce unassigned waiting time and SLA breaches while balancing eligible physicians' workload and preserving coverage. Queue score orders attention; it does not select the best physician or prove staffing sufficiency. Keep assignment eligibility separate from workload ranking and from forecast assumptions.

## Repo layout

One monorepo. Backend in `backend/`, dashboard in `web/`, Flutter in `mobile/`. Each backend module has one owner, so merges rarely collide.

```
command-center/
  backend/
    app/
      main.py              # FastAPI app, lifespan, CORS, routers (P1)
      config.py            # Settings: clock mode, thresholds, paths (P1)
      clock.py             # Clock: wall, anchored, fixed (P1)
      coordinator.py       # serialized mutations, durable commit, atomic publication (P1)
      api/
        events.py          # POST /events, CSV upload (P1)
        reference.py       # reference file upload and reload (P1)
        state.py           # GET snapshots for dashboard panels (P1)
        admin.py           # reset, clock override (P1)
        ws.py              # WebSocket hub, broadcast (P1)
      ingest/
        schemas.py         # Event + reference models, G1 (P2; not present in this checkout)
        column_map.yaml    # header renames (P2; not present in this checkout)
        adapters.py        # explicit sample description mappings, reference normalization (P2)
        pipeline.py        # G2 dedupe, G3 late insert, G4 orphans (P2)
      engine/
        store.py           # ordered event log by event_time (P2)
        replay.py          # replay(events, refs, now) -> State (P2)
        consult.py         # G5 stage machine (P2)
        physician.py       # G6 derived state, G7 routable (P2)
        counters.py        # G8 counters (P2)
      detect/
        overload.py        # G8b (P3)
        timers.py          # G9 time standards (P3)
        shift_end.py       # G10 (P3)
        stuck.py           # G11 (P3)
        demand.py          # G12 (P3)
        coverage.py        # G13 forecast (P3)
        signals.py         # G14 (P3)
        queue.py           # G15 scoring, reasons (P3)
      stretch/             # G16 to G24, only after H20 (P1, P3)
      db.py                # SQLite: events, quarantine, audit (P1)
      models.py            # API response models shared with web (P1)
    tests/
      fixtures/            # base CSVs, snapshots, live_test_events.csv
      test_ingest.py       # T2, T3, T24, T25 (P6)
      test_snapshot.py     # T1 diff against snapshot_*_1820.csv (P6)
      test_detect.py       # T4 to T12, T23, T26 to T28 (P6)
      test_consistency.py  # concurrency, restart, clock cutoffs, reference revisions (P6)
    pyproject.toml
    Dockerfile
  web/                     # Vite + React (P4, P5)
  mobile/                  # Flutter web (P6, stretch)
  render.yaml
  .github/workflows/ci.yml
```

## Core interfaces

State is a pure function of accepted events and a reference revision. Anything that depends on now (shift membership, cooldown, workload windows, timers, forecast, queue) is computed from that state plus one captured `as_of`. Ordered replay must never apply an event with `event_time > as_of`: retain it durably and expose it as pending until due. A backward clock override rebuilds the event prefix. Live snapshots use only events accepted so far; a separate historical view may also need an ingestion cutoff.

Freeze these signatures at H2. Bodies can change; signatures cannot without telling the team.

```python
# clock.py
class Clock(Protocol):
    mode: Literal["wall", "anchored", "fixed"]
    def now(self) -> datetime: ...          # always tz-aware UTC

def make_clock(settings, newest_event_time: datetime | None) -> Clock: ...
# wall if newest event within 15 min of real time, else anchored

# engine/store.py
class EventStore:
    def add(self, e: Event) -> AddResult: ...   # G2 dedupe, G3 late flag
    def ordered(self, as_of: datetime) -> tuple[Event, ...]: ...
    # visible prefix by (event_time_utc, ingested_at_utc, event_id)
    stats: IngestStats                          # rejected, dupes, late, orphans, max_lag

# ingest/pipeline.py
def ingest(raw: list[dict], store: EventStore, refs: Refs,
           received_at: datetime) -> IngestReport: ...
# adapter -> G1 -> G2 -> G3 -> G4; invoked only through coordinator
# received_at is server wall UTC, independent of event/simulation clock

# engine/replay.py
@dataclass(frozen=True)
class State:
    consults: Mapping[str, ConsultState]     # stage, entered_at, note_pending_since, owner, flags
    physicians: Mapping[str, PhysicianState] # session sets, ring/status/agent histories, assignments
    hospitals: Mapping[str, HospitalState]   # sorted received timestamps for trailing counts

def replay(events: tuple[Event, ...], refs: Refs) -> State: ...   # no clock
# G5/G6 and histories for G7/G8; orchestration selects events <= as_of

# detect/*.py, each returns typed alerts
def detect(state: State, refs: Refs, now: datetime, cfg: Thresholds) -> Detection: ...
# Detection = timers, shift_end, stuck, overload, demand, coverage, signals, queue

# api/state.py builds every panel from one (state, detection, as_of, revision) bundle
```

**Rules for every module**

- Only clock adapters read wall time or monotonic elapsed time. Other modules take timestamps as arguments. Use monotonic elapsed time for anchored clock progression; keep server receipt time separate from simulation time.
- Never hardcode IDs. Fixture IDs live only in `tests/`.
- All instants UTC inside the engine. Interpret reference time-of-day columns in their declared zone before converting. Supplied `*_et` columns use `America/New_York`, including baseline and coverage; hospital-local reference formats must declare a different zone explicitly.
- Thresholds from `config.py`, not literals.
- `frozen=True` does not freeze nested dictionaries. Publish immutable mappings and records; readers must never see a partially rebuilt state.

## Fixture adapter and dispatch semantics

The supplied stream has `description`, but no `consult_type` or `value`. Header renaming alone cannot normalize it. Before G1, use versioned, exact mappings scoped by event type: receipt descriptions to Stroke/General Neuro, status descriptions to their enum, the explicit phone-only call ending to `phone_complete`, ordinary call endings to `continue`, and the known routing-failure description to `retry_in_5m`. Unknown descriptions required to recover a semantic field are quarantined. Preserve raw rows and adapter version. Canonical JSON events supply these fields directly; never use an LLM to infer eligibility or lifecycle state.

Normalize the wide credential matrix to `(physician_id, hospital_id, credentialed)` pairs (`Y` true, blank false). Resolve roster time-only ET shifts against an explicit dataset service date, with overnight intervals ending on the following day. Keep scheduled future shifts distinct from opt-in availability: the off-shift roster provides a next start but no end. Do not manufacture a full shift interval for forecast purposes. Actual upcoming-shift inclusion requires a configured, disclosed duration or a complete schedule feed.

Required reducer and detection rules:

- Track open calls/videos by physician, consult and direction/session where available. An ending closes only its matching session. Starts/ends without a compatible session raise conflicts. Answering clears the corresponding ring; stale rings remain visible until answered or an explicit configured expiry policy fires. Sample data has no ring-cancel event.
- Keep call/video/camera signals separate from consult stage. A follow-up call during Imaging Pending makes the physician busy without reversing the consult stage. Repeated same-stage events do not reset the stage timer. Preserve a stage history and `note_pending_since` through Documentation so starting a note cannot reset G9's documentation deadline.
- Reassignment changes current ownership without erasing history. Repeated assignment to the same owner is not new work. Define consult counters as distinct consults assigned to a physician in the active shift; preserve handoff history. Match snapshots through an output-label adapter rather than raw enum string equality.
- G7 uses `[shift_start, shift_end)`, the G6 classification, active rings and `as_of - last_call_end >= cooldown`. Keep all exclusion reasons with one deterministic primary reason. Credential eligibility is hospital-specific and checked separately. A self-reported Available status does not override video/call signals.
- Demand uses unique received consults in `(as_of - 60 min, as_of]`; consult assignment rate uses `(as_of - 2 h, as_of]`. Do not round minutes before comparing thresholds. Use floor only for snapshot display comparisons.
- G10's within-shift window is `0 <= shift_end - as_of <= 60 min`; overdue unfinished work remains separately flagged after the shift ends. Configure the overload peer cohort and zero-median/minimum-sample behavior; a raw median over unmatched shifts is not a reliable load comparison.
- Preserve G15's documented scoring until the policy is explicitly changed. Give stable item IDs, group alerts for the same consult/hospital, retain every reason, and tie-break by oldest relevant timestamp then stable ID. Hospital gap items get a stroke bonus only under an explicit documented rule.

## Mutation, publication and recovery

One uvicorn worker still serves concurrent requests. Route event ingestion, orphan sweeps, reference activation, reset and clock overrides through a single mutation coordinator. Use a bounded submission queue with explicit overload rejection, and keep blocking SQLite/file I/O and expensive replay outside async request handlers.

For each batch: normalize and validate rows; deduplicate against accepted and held IDs; stage reference/consult dependency resolution; build candidate state without changing published objects; transactionally persist accepted events, held/quarantined outcomes and revision; then atomically publish the committed bundle. Acknowledge only after durable commit and publication. On a crash between commit and publication, restart reconstructs from durable data. Failed commits leave the previous state published. Readers use one bundle and WebSocket sends never hold the mutation coordinator.

Resolve orphans by dependency to a fixed point, so a parent and child uploaded in either order produce the same eventual state. A child timestamped before its receipt remains a causal conflict even after both arrive. Sweep orphan deadlines periodically, including while the simulation clock is fixed; a repeated delivery never extends the original hold deadline. Re-evaluate held rows after new events or reference activation. Count pending orphans separately from expired quarantines.

G3 metrics are distinct: `reordered` counts any insertion earlier than the prior accepted event-time watermark; `late` counts those whose watermark lag exceeds `late_lag_s`; `max_reorder_lag_s` measures watermark lag; `max_delivery_lag_s` measures `ingested_at - event_time`. Compute ingest-quality metrics in arrival order, persist them, and do not recount them during event-time replay. An identical event ID with a changed semantic payload is a conflict, even though it is not applied twice.

Reference activation validates complete candidate references, rejects ambiguous duplicate keys or overlapping coverage blocks, rebuilds state, and atomically publishes a new reference revision. Preserve historical accepted events if an updated reference removes an ID; flag unresolved history and exclude unsafe recommendations. Missing baseline or requirements is `unknown`, never healthy zero.

## API and WebSocket

REST for commands and first load; one WebSocket for pushes. P4 and P5 build against mocked responses of these exact shapes from H2.

| Method | Path | Body or query | Returns |
| --- | --- | --- | --- |
| POST | `/events` | One event or a list (JSON) | IngestReport: accepted, pending-future, held-orphan, duplicates, conflicts, reordered, late, quarantined with reasons and committed revision |
| POST | `/events/upload` | CSV file | IngestReport |
| POST | `/reference/{name}` | CSV file; name = hospitals, on\_shift, off\_shift, credentials, baseline, coverage | Rows loaded, rows quarantined |
| GET | `/snapshot` | none | Full dashboard payload (all panels + headline numbers + clock) |
| GET | `/consults/{id}` | none | Stage history, timers, flags |
| GET | `/physicians/{id}` | none | Signals, derived state, counters, exclusion reason |
| GET | `/quarantine` | `?limit=&cursor=` | Paginated rejected/expired rows with reasons; pending orphans counted separately |
| POST | `/admin/reset` | none | Reloads base stream and references, resets clock |
| POST | `/admin/clock` | mode, anchor | New clock state |
| GET | `/health` | none | Liveness |
| GET | `/ready` | none | Ready only after reference validation and durable replay; revision, event count, clock mode |
| WS | `/ws` | none | Push messages below |

**WebSocket messages** (server to client, JSON, each with `type`, `now`, `revision`, `reference_revision`, `clock_revision`, and monotonic `sequence` within a server epoch). Include an epoch ID so restart/reset cannot silently reuse an old sequence. REST snapshot carries the same metadata. Reconnect obtains a fresh snapshot; clients discard old-epoch or stale pushes.

| type | When | Payload |
| --- | --- | --- |
| `snapshot` | On connect and after reset | Same as GET `/snapshot` |
| `delta` | After each accepted event batch | Changed consults, physicians, hospitals, queue |
| `tick` | On next relevant deadline, with a configurable refresh interval cap | Recomputed shifts, cooldowns, timers, coverage, queue |
| `ingest` | After each ingest call | IngestReport, for the data-quality panel |

First version may send a full `snapshot` instead of `delta`. Payload is small; optimise only if needed.

Use one bounded outgoing queue per WebSocket client; coalesce replaceable snapshots, and disconnect/resync lagging clients. A slow dashboard must not block ingest or other clients. Authenticate mutations and administrative routes, and enforce upload byte/row limits; CORS is not authorization. Keep demo reset/clock controls explicitly gated by environment and role.

## Storage

SQLite on the Render disk at `/data/cc.db` is the authoritative durable record; memory is a derived serving view. On start, reload the active reference revision and replay accepted events. Use WAL, a bounded busy timeout and one coordinated writer. Start with `synchronous=FULL` for acknowledged-write durability and measure commit latency. Events and quarantine are append-only within a dataset generation; orphan rows and active metadata may change transactionally. Reset creates a new dataset generation rather than partially deleting live tables.

```sql
CREATE TABLE events (
  dataset_generation INTEGER NOT NULL,
  event_id      TEXT NOT NULL,      -- G2 dedupe within dataset generation
  event_time    TEXT NOT NULL,      -- canonical UTC ISO, identical precision and +00:00 suffix
  time_offset   TEXT,               -- original offset, for local display
  ingested_at   TEXT NOT NULL,
  event_type    TEXT NOT NULL,
  consult_id    TEXT,
  physician_id  TEXT,
  hospital_id   TEXT,
  consult_type  TEXT,
  value         TEXT,
  source        TEXT NOT NULL,      -- base | upload | api | live_test
  received_at   TEXT NOT NULL,      -- server wall UTC, independent of simulation
  raw_json      TEXT NOT NULL,
  adapter_version TEXT NOT NULL,
  PRIMARY KEY (dataset_generation, event_id)
);
CREATE INDEX events_by_time ON events(dataset_generation, event_time, ingested_at, event_id);

CREATE TABLE quarantine (
  id INTEGER PRIMARY KEY, dataset_generation INTEGER NOT NULL,
  received_at TEXT, gate TEXT, reason TEXT, raw_json TEXT
);

CREATE TABLE orphans (
  dataset_generation INTEGER NOT NULL, event_id TEXT NOT NULL,
  held_since TEXT NOT NULL, expires_at TEXT NOT NULL,
  reason TEXT NOT NULL, raw_json TEXT NOT NULL,
  PRIMARY KEY (dataset_generation, event_id)
);

CREATE TABLE reference_loads (
  id INTEGER PRIMARY KEY, name TEXT, loaded_at TEXT, rows_ok INTEGER, rows_bad INTEGER
);

-- stretch only
CREATE TABLE audit (
  id INTEGER PRIMARY KEY, at TEXT, offer_id TEXT, actor TEXT, action TEXT, detail_json TEXT
);
```

Persist versioned raw reference CSVs, normalized content and their checksums in SQLite (or use a durable version manifest with equivalent atomic activation). Store the active reference pointer and dataset generation transactionally. Add durable ingest outcomes/counters and publication metadata before implementing restart tests. The SQL above describes core row shapes; the implemented migrations must include dataset-generation scoping, reference revisions and metadata. Backups must capture committed WAL data, not just copy `cc.db` while writes are active. Raw reference-file overwrites cannot provide restart consistency.

## Config, tests and deploy

**Config** (`app/config.py`, pydantic-settings, every value overridable by env var)

```python
class Settings(BaseSettings):
    clock_mode: Literal["auto", "wall", "anchored", "fixed"] = "auto"
    clock_anchor: datetime | None = None
    clock_fixed: datetime | None = None  # fixture runner sets dataset service date + 18:20 ET
    service_date: date | None = None     # required/derived explicitly for time-only shift rows
    reference_timezone: str = "America/New_York"  # supplied *_et columns
    late_lag_s: int = 60            # G3
    orphan_hold_min: int = 5        # G4
    ring_unanswered_min: int = 2    # G11
    call_cooldown_min: int = 2      # G7
    overload_open_warn: int = 3     # G8b
    overload_open_crit: int = 4
    overload_rate_factor: float = 1.5
    forecast_horizon_min: int = 90  # G13
    forecast_step_min: int = 15
    refresh_max_s: int = 5          # proposed UI freshness target; validate under load
    max_upload_bytes: int = 10_000_000
    max_batch_rows: int = 10_000
    mutation_queue_limit: int = 100
    websocket_queue_limit: int = 2
    db_path: str = "/data/cc.db"
    data_dir: str = "/data/ref"
    cors_origins: list[str] = ["http://localhost:5173"]
```

**Tests**

- `test_snapshot.py`: replay base stream with fixed clock, diff physician and consult rows against `snapshot_*_1820.csv`. This is T1 and the first test in CI.
- `test_ingest.py`: duplicates, late inserts, naive timestamps, unknown types, orphan release.
- `test_detect.py`: one test per T row in the PRD, asserting the gate output, not UI text.
- `test_live.py`: feed `live_test_events.csv` one row at a time into a running app via `TestClient`, no restart.
- `test_consistency.py`: concurrent ingest/ref/reset; failed commit; crash/restart; orphan release/expiry under fixed clock; identical versus conflicting duplicate IDs; future events; backward clock; matching-session endings; reassignment; note timer continuity; ET/DST and overnight boundaries. A child-first batch and parent-first batch converge to identical state.
- The supplied data folder has no `live_test_events.csv`. Create a separate synthetic fixture for T23 to T27; do not claim those tests passed from the base stream. All nine provided CSVs must be copied into CI fixtures (the current `data/` directory is gitignored).
- `scripts/audit_sample_data.py` is a read-only independent fixture audit. It checks consult stages/ownership/timing and physician workload counts; it does not replace backend integration tests or performance measurements.

**Performance validation:** pre-index references by ID, credentials in both directions, shift intervals and baseline/coverage keys. Store received and assignment timestamps sorted, using binary search for bounded windows. Cache a published dashboard bundle until an accepted batch, reference/clock revision or relevant deadline changes it; never replay separately for each panel/client. Initially sort the batch once, merge with the event log, and replay once. Replaying every growing prefix of an N-row upload performs O(N²) reducer work.

Proposed acceptance targets on the intended deployment, to be measured rather than assumed: p95 single-event ingest-to-published-snapshot <= 250 ms; p95 cached snapshot <= 100 ms; deadline visibility <= 5 s; base import <= 2 s. Measure validation, ordering, replay, detection, durable commit and serialization separately at the base volume and at 10x/100x generated volumes with concurrent dashboard clients, late events and a slow client. Record hardware, batch size and event rate. Move to incremental replay/checkpoints when measurements require it, retaining differential tests against full replay. Multiple processes require shared durable coordination and pub/sub; adding uvicorn workers to this design is not a scaling fix.

**CI** (`.github/workflows/ci.yml`)

```yaml
name: ci
on: [push, pull_request]
jobs:
  backend:
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: backend } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.14.7" }
      - run: pip install -e '.[test]'
      - run: pytest -q
```

**Dockerfile** (`backend/Dockerfile`)

```docker
FROM python:3.14.7-slim
WORKDIR /app
COPY pyproject.toml .
COPY app ./app
# Copy README/package data too if required by pyproject.toml's build configuration.
RUN pip install --no-cache-dir .
CMD ["python", "-m", "app"]
```

**Render Blueprint** (`render.yaml`)

```yaml
services:
  - type: web
    name: cc-backend
    runtime: docker
    rootDir: backend
    plan: starter
    healthCheckPath: /ready
    disk:
      name: cc-data
      mountPath: /data
      sizeGB: 1
    envVars:
      - key: CORS_ORIGINS
        value: '["https://<your-app>.vercel.app"]'
```

`--workers 1` is required. State lives in memory; two workers would hold two different states.

`app/__main__.py` reads `PORT` and launches one worker on `0.0.0.0`. The implemented image includes a `/ready` health probe, persistent `/data` defaults and an excluded local build context. Provider order is Render, AWS EC2 + EBS, then Azure VM + managed disk. See [Deployment](Deployment.md); avoid SQLite WAL on shared network filesystems. Future managed-container scaling needs a different durable coordination/storage implementation.

**Dependencies** (`pyproject.toml`): FastAPI for the ASGI/OpenAPI API, plain Uvicorn for serving it, and Pydantic for validated event contracts. Tests: pytest and httpx. Prefer standard-library `csv`, `json`, `sqlite3`, `dataclasses`, `os`, `datetime` and `urllib` for the remaining work. Add dependencies only when an implemented requirement needs them; multipart upload and WebSocket transport packages are deferred until those routes exist. Benchmark before adding optional server accelerators.

## H0 to H2 checklist

At H2 every box is ticked, or the person behind it says why.

- [ ] P1: create repo with the layout above, branch protection on `main`, CI green on an empty test
- [ ] P1: `main.py` with `/health`, `/snapshot` returning a mock payload, `/ws` sending a mock `snapshot`
- [ ] P1: deploy backend to Render via `render.yaml`; confirm disk mounted at `/data`
- [ ] P1: `clock.py` with all three modes and `/admin/clock`
- [ ] P1: `models.py` response models frozen; publish OpenAPI URL to the team
- [ ] P2: move `schemas.py` and `column_map.yaml` into `app/ingest/`; add `EventStore` and `replay()` stubs with frozen signatures
- [ ] P3: `detect()` stub returning empty `Detection`; start G9 to G12 against snapshot CSVs
- [ ] P4, P5: Vite app on Vercel, types generated with `openapi-typescript`, panels rendering mock data
- [ ] P6: fixtures copied into `tests/fixtures/`; `test_snapshot.py` written and failing for the right reason
- [ ] P1/P2/P3: reconcile the supplied fixture differences in the review before freezing H2 assertions, adapters and time-zone semantics
- [ ] All: confirm open questions in the PRD (data arrival, judging criteria) with organisers
