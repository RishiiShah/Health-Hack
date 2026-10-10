# P2 backend handoff: G1–G8

Implemented on personal branch `rishi`. This increment owns normalization, event quality, reference IDs, deterministic consult/physician state, routing eligibility and counters. Detection G8b–G15, demand/coverage forecasts, ranking, offers, frontend/mobile, and P1's upload/admin/WebSocket interfaces remain with the team.

## Domain interfaces

- `app.references.load_refs(directory, service_date)` uses standard-library CSV, date/time and zoneinfo. It loads hospitals, on-shift physicians, off-shift roster IDs and the wide credential matrix. The service date is explicit. Supplied shift columns are ET regardless of a hospital's zone. Overnight shifts cross the date boundary; ambiguous/nonexistent DST times are rejected. Missing files/headers/IDs, duplicate IDs, unknown credentials and overlapping shifts fail validation. A next start without an end creates no future shift.
- `MutationCoordinator(db, clock, refs=refs, receipt_clock=..., orphan_hold_s=300)` supplies reference-aware G4. Omitting references retains the foundation's consult-dependency checks but does **not** validate physician/hospital IDs. P1 must supply validated references before claiming G4 reference readiness.
- `ingest(rows)` accepts typed `EventInput` rows; `ingest_raw(rows, adapter='canonical-v1')` independently normalizes raw JSON rows and durably quarantines G1 failures. `adapter='sample-csv-v1'` enables the exact supplied-description mappings. Header aliases for other file formats need an explicit versioned adapter, rather than guessing or an LLM. The strict `load_fixture` helper raises on malformed data; upload routes should call `ingest_raw`.
- `activate_references(refs)` atomically saves the validated reference snapshot, increments its revision when changed, releases eligible holds and publishes committed state. Restart restores that reference snapshot. Pass matching references on restart or activate replacements explicitly. Removed reference IDs do not erase accepted history: `Published.unresolved_history` lists affected event IDs.
- `current_publication()` returns immutable consult/physician state, one `as_of`, revision, reference revision, matching immutable `refs`, cumulative quality metrics and the pending hold count. Consumers must use this bundle's references and visible event prefix together, rather than mixing independently read coordinator attributes.
- `physician_view(bundle.state, bundle.refs, physician_id, bundle.as_of, cooldown_s=120)` computes G6/G7/G8. Call it only with a replay prefix at or before `as_of`. `eligible_for_hospital(view, hospital_id)` combines G7 with hospital-specific credentials. It does not rank candidates or authorize an assignment.

```python
from datetime import date
from app.references import load_refs
from app.engine.physician import physician_view
from app.coordinator import MutationCoordinator

refs = load_refs("data", date(2026, 3, 17))
coordinator = MutationCoordinator(db, clock, refs=refs)
coordinator.ingest_raw(raw_rows, adapter="sample-csv-v1")
bundle = coordinator.current_publication()
views = [physician_view(bundle.state, bundle.refs, pid, bundle.as_of)
         for pid in bundle.refs.physicians]
```

## State and ingest behavior

Consults retain stage history, ownership changes, continuous `note_pending_since` and conflict flags. Same-stage repeats preserve timing. Same-owner assignment repeats are not new work. Signed Off is terminal. Follow-up calls change physician activity without reversing consult stage.

Calls are keyed by physician, consult and direction; videos by physician and consult. With the current event schema, there is no explicit session ID. Repeated starts while that key is open and unmatched ends raise conflicts; invalid ends do not advance consult stage or reset cooldown. Answering an incoming call clears only that consult's ring. Rings never expire implicitly. Camera events restore the agent's online signal. Availability status does not override active calls/videos.

G7 uses `[shift_start, shift_end)` and an exact cooldown boundary. Every exclusion is retained in deterministic order: off shift, busy/unavailable, ringing, cooldown; the first is the primary reason. Credential eligibility is separate. G8 consult counts are distinct assignments during the active scheduled shift, calls count valid starts including ongoing calls, and open counts reflect current ownership. Canonical state labels are separate from the supplied snapshot's display labels.

G4 holds unknown references/missing receipts for five minutes from **first server receipt**, independent of simulation time. A child earlier than its receipt is a causal conflict. Duplicate delivery never extends a hold. At the exact expiry deadline, quarantine wins over release. Expired hold tombstones prevent repeated delivery from reopening the deadline; restart preserves pending and expired records.

Accepted events, hold transitions, quarantines, cumulative metrics, reference updates and the revision share one SQLite transaction. Publication changes only after a successful commit. Quality metrics are collected on acceptance, not replay, so clock changes do not recount them. Newly accepted deliveries are accounted before previously held events released by the same mutation. Released holds use first server receipt, event time and stable event ID ordering, including after restart. `history_complete=false` indicates that a database predates durable quality accounting; historical zero counters are then not evidence of zero errors.

## Team integration still required

P1 must connect reference loading/activation, raw-row ingestion, quarantine pagination and physician views to its API. The existing `/snapshot` still labels the physician/reference panels unsupported. Only the existing orphan capability/warning was updated to reflect holding rather than immediate quarantine.

P1 must call `coordinator.sweep()` periodically using its service lifecycle, including under a fixed simulation clock. Ingestion and snapshot reads already sweep due expirations; idle expiry without requests requires that scheduled call. Run synchronous SQLite/replay work outside the event loop. P1 also owns input byte/row limits, bounded request submission, reset/clock administration, authentication and WebSockets. Activation is a Python hook, not a new endpoint.

P3 consumes the published state, reference revision, shifts, credentials, assignment/session history, `note_pending_since`, conflicts and quality metrics. Baseline/coverage reference files and future-shift assumptions remain P3's concern; this loader deliberately does not infer future end times. No alerts, overload thresholds, coverage predictions or dispatch ranking are added here.

## Verification

Synthetic tests cover G1 rejection, exact adapters, G2 dedupe, persistent G3 metrics, G4 release/expiry/restart/reference activation/failed commits, matched concurrent sessions, G5 history and timers, G6 precedence, G7 ring/cooldown/shift boundaries, G8 distinct counters, overnight/DST reference validation and immutable references. Source-data tests additionally compare every supplied field in all eight physician and eighteen open-consult rows at March 17, 2026, 18:20 ET. They remain skipped in CI when the deliberately gitignored data is absent; synthetic boundary tests run without it.

The full local suite passes 57 tests on Python 3.14.7, including two source-data tests; the other 55 use synthetic inputs. No dependencies were added. Full replay remains the correctness oracle; operational latency and throughput remain unmeasured; a limited local domain timing check is recorded below. Container/cloud verification is separate from these domain checks.

### Local domain timing check

On Python 3.14.7, macOS arm64, with in-memory SQLite and pre-normalized rows:

| Input | Unique accepted events | Single typed-ingest run | Cached bundle refresh p95 (100 reads) | All 14 physician views, single run |
| --- | ---: | ---: | ---: | ---: |
| Supplied sample | 1,163 | 20.48 ms | 0.002 ms | 0.21 ms |
| 10× cloned sample | 11,630 | 213.72 ms | 0.002 ms | 1.57 ms |

These are small local domain checks, not deployment benchmarks. They exclude CSV parsing, HTTP validation/serialization, network traffic, disk durability and concurrent-client load. The ingest/view columns each contain one observation; only the cached refresh column samples multiple reads. The 10× rows retain the same reference physicians and duplicate pattern while assigning unique consult/event suffixes. Do not treat these measurements as proof of the PRD's operational p95 targets.

## Organizer insights and judging rehearsal

Carl confirmed a held-out March 17 calls/consults extension and said single-day scenarios are sufficient. His recommendation for independently generated datasets is another date and distinct ID prefixes. The domain has no fixed service date or prefix check; regression tests now run complete consult/call sequences on April 7 and November 2 using `EVT-T*`, `CON-T*`, `PHY-T*` and `H-T*` IDs. Another test appends March 17 events without reset, retains the earlier consult, advances visibility with the injected clock and verifies duplicate redelivery. These use disposable synthetic references and do not modify the supplied files.

P1 still needs to test the actual judging delivery path end to end, including reference activation and clock control. Organizer confirmation is needed for transport, schema/description compatibility, timestamp conventions and whether new physician/hospital IDs bring reference updates. P3 projections should retain explicit roster/baseline assumptions; fabricated multi-day history is not evidence for prediction accuracy.

## Routing implementation constraint

This is a deterministic routing/operations optimization problem with no AI/ML runtime dependency. P2 supplies validated state, credentials and routing eligibility. The team owns documented assignment capacities, objective costs, shared-coverage constraints and stable tie-breakers for ranking/matching. Schedule-based coverage scenarios require explicit assumptions, not model training. Pydantic is used only for schema validation.
