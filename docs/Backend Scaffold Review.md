# Backend scaffold review

Reviewed Oct 10, 2026 against the two design documents and all nine supplied CSVs. At the initial review, the repository contained planning documents and data without a backend implementation. This review verifies fixture facts; implementation status and runtime validation are tracked separately in the backend README.

The single-process FastAPI/SQLite architecture is a suitable starting point for this sample. The immediate risks are inconsistent fixture assumptions, unsafe state publication, and confusing potential coverage with dispatchable capacity. Address these before introducing a larger stack or a predictive model.

## Verified fixture differences

Run `python3 scripts/audit_sample_data.py --data-dir data` to reproduce the counts and consult comparisons below. It reads files without modifying them. It uses the PRD's monotonic consult-stage rules with exact sample-description mappings; it is an independent audit, not the production replay engine.

| Topic | Supplied data / calculation | Conflict or required change |
| --- | --- | --- |
| Service date | Events are March 17, 2026; snapshot is 18:20 ET (`22:20 UTC`) | Scaffold's October 9 fixed clock would invalidate shift/demand/timer calculations. Configure service date explicitly. |
| Stream size | 1,164 rows, 1,163 unique IDs; all 20 event types present | Treat these as the current fixture counts, not a volume/performance guarantee. |
| Duplicate | `EVT-00529`, same semantic fields, different ingestion timestamp | PRD T2 expects `EVT-00564`. Update assertions for this fixture. |
| Reordering | 23 unique events arrive behind the event-time watermark; 22 by only 1–3 seconds | Reordering and significant lateness are separate metrics. |
| Significant late event | `EVT-01161`: watermark lag 355 seconds (5:55); delivery lag 405 seconds (6:45) | Only one event exceeds 60 seconds by either measure, not four. PRD mixes the two lag definitions. |
| Event schema | Columns include `description`, but omit `consult_type` and `value` | Add an explicit sample adapter before strict validation. Header renames alone cannot recover these values. |
| Event zones | Every supplied event timestamp uses `-04:00`, including events for hospitals in other zones | Preserve the supplied instants. Do not reinterpret them as hospital-local clock readings. |
| Reference zones | Baseline `hour_start_et`, coverage `time_block_et`, shift `*_et` | Current baseline and coverage use ET; the PRD's hospital-local baseline lookup contradicts the source headers. |
| Consult replay | 103 received, 85 signed off, 18 open; all compared open-consult ownership/type/stage/timestamp/minute fields match | Replay is viable when the adapter and event-time order are correct. Snapshot minutes are floored, not rounded. |
| Physician counters | All eight physicians' assignment, answered-call and open-consult counts match snapshots | Ringing must not count as an answered call. Full derived physician-state verification still needs implementation. |
| IDs and credentials | No unknown reference IDs, no event before its consult receipt, no credential conflict on assignments | These edge cases need synthetic tests; this fixture does not exercise them. |
| Suncrest demand | 5 receipts in `(17:20, 18:20]`; 18:00 ET p90 is 1 | PRD T10 says p90 2. The spike still holds. |
| Lakeview demand | 1 receipt; 18:00 ET p90 is 2 (17:00 hospital-local row is also 2) | PRD's `1 = 1` is not an equality-boundary test. Add a separate synthetic equality test. |
| Suncrest requirement | Minimum is 1 in every coverage block; +1 on spike gives 2 | PRD T11 says requirement 3. Do not hardcode 3 to reproduce that example. |
| Cho credentials | `PHY-011` is credentialed at Suncrest and next shift starts at 19:00 ET | PRD says Cho does not count there. Credentials say otherwise; a complete shift interval is still needed. |
| Alvarez credentials | `PHY-010` has no Suncrest credential | Cannot be the eligible Suncrest gap responder asserted by T13. Rebuild stretch fixtures from actual credentials and offer history. |
| Upcoming shifts | Off-shift roster has `next_shift_start`, but no next end or confirmed schedule interval | Disclose a configured duration or require a complete schedule feed. An opt-in does not itself mean scheduled coverage. |
| Roster metadata | On-shift roster lacks role; off-shift roster has `offers_declined_last_30d` but no offers sent in seven days | Map the existing decline column; do not default it to zero. G17 offer-frequency eligibility is unknown until a history source is provided. |
| Live fixture | No `live_test_events.csv` exists | T23–T27 are currently unverified. Author a separate synthetic fixture with dataset-consistent timestamps. |
| Coverage queue score | A critical gap 40 minutes away scores `100 + 30 × (1 - 40/90) = 116.67` before any explicitly defined bonus | PRD's 147 implies an extra 30-point bonus and rounding. Hospital-level stroke bonus policy is not defined. |

These differences describe the original PRD v2. PRD v2.1 now corrects fixture assertions, makes ET reference semantics explicit, treats incomplete schedules as uncertain, and defines consult-only stroke bonuses. Source data remains unchanged. Future complete shift intervals, offer history and operations policy validation remain outstanding.

## Changes made to the scaffold

1. Added a single mutation coordinator and immutable, versioned snapshots. One uvicorn worker does not serialize concurrent API requests. Normalize/validate, stage changes, commit durably, publish atomically, then acknowledge. Reset, references and clock overrides use the same coordinator.
2. Separated event time, source ingestion time and server receipt time. Future events remain pending until the captured `as_of`; orphan expiry uses server receipt deadlines so fixed-clock demos cannot hold orphans forever. Quality counters survive restart and are not recomputed during replay.
3. Added explicit adapter rules, reference zones, shift intervals, session tracking, ring handling, note timer continuity and reassignment semantics. The supplied follow-up call during Imaging Pending must change physician activity without reversing the consult stage.
4. Replaced unsupported “milliseconds” claims with measured performance targets. Replay once per accepted batch, share one computed dashboard bundle across panels/clients, pre-index reference joins and time windows, and keep slow clients outside the mutation path.
5. Added persistent reference revisions, dataset generations and recovery checks. A raw CSV overwrite plus a separate SQLite commit can leave restart using mismatched references. Canonical UTC strings must use one precision for database sorting.
6. Added WebSocket sequence/epoch handling, bounded queues, readiness, upload bounds and mutation authorization. Fixed Docker's build order so app source is present when the local package is installed.

Blocking work inside an async handler can block the event loop; the coordinator should run its synchronous work outside that handler. This follows [FastAPI's concurrency documentation](https://fastapi.tiangolo.com/async/). WAL allows readers and a writer to proceed concurrently but still has one writer, which supports the coordinated-write design. See [SQLite WAL](https://www.sqlite.org/wal.html). UTC normalization and explicit offset handling follow [Python datetime](https://docs.python.org/3/library/datetime.html).

## Operations optimization priorities

**First, make eligibility and waiting time trustworthy.** A dispatcher needs to see why each credentialed physician is excluded, the latest state revision, and when a consult crosses its deadline. The camera/session discrepancy and unanswered ring in this sample show why self-reported Available cannot drive matching. `PHY-007` is unverified and derived Available, but the active ring still blocks G7 routing.

**Next, add explainable assignment recommendations.** This is a proposed extension to the PRD's monitoring core, before the external offer loop if time permits. For each queued consult, filter by credentials, complete shift interval, G7 availability and any explicit concurrency cap. Rank feasible choices by current active work, open consults, note backlog, remaining shift and the coverage lost by using that physician. Return exclusions and the component values with every recommendation. Do not treat the sample's overload-warning threshold as an assignment ban without an explicit policy decision. Any future reassignment command must re-check eligibility and state revision and reserve capacity in one transaction.

**Optimize the queue jointly when several consults await assignment.** Ranking a physician separately for each consult can recommend the same person repeatedly or consume the only provider credentialed at a constrained hospital. A small capacity-constrained matching calculation can prioritize the PRD's urgency policy, then waiting time and load balance. Include “unassigned” as a valid outcome and explain infeasibility; never force an ineligible match. Benchmark a simple deterministic matcher before adding a general solver. Keep automated assignment outside the current PRD scope.

**Label forecasts according to what they count.** Current coverage uses G7; projected coverage uses scheduled credentialed headcount excluding Temporarily Unavailable under the PRD. A physician busy now can therefore appear available in the very next projected cell. Mark that as potential scheduled coverage, with the explicit assumption that current calls/video are released. Do not display it as a guaranteed dispatchable forecast.

**Account for shared capacity.** Per-hospital credentialed counts can count the same physician at several hospitals. They measure potential eligibility and cannot prove simultaneous demand can be served. If showing a system-wide staffing deficit, add a separate shared-capacity feasibility calculation with explicit service/concurrency assumptions. Preserve the PRD G13 panel for compatibility while exposing this limitation.

**Measure outcomes and speed separately.** Operational measures: arrival-to-assignment, assignment-to-first-contact, stage breach counts, oldest unassigned age, backlog carried past shift end, workload distribution, recommendation feasibility and coverage impact. Technical measures: ingest-to-publication latency, stale snapshot age, durable commit latency, replay/detection time and late-correction latency. The sample has no counterfactual control group or sufficient service-time history to prove improvement or calibrate a reliable predictive model.

## Decisions still needed

- Run corrected PRD v2.1 core assertions before declaring the core green. T13/T14 are now explicitly stretch tests and need separate complete fixtures.
- Confirm ET versus hospital-local reference semantics for future feeds; supplied `*_et` fields are ET.
- Supply complete upcoming shifts and offer history before claiming G13 future staffing or G17 eligibility is complete.
- Validate the PRD v2.1 proposed overload peer cohort and minimum sample size with operations, and define ring expiration. Hospital gaps now receive no stroke bonus. Keep unresolved rules visible as assumptions rather than tuning to named fixture IDs.

The initial review performed no runtime benchmark. The independent audit establishes fixture consistency for consult fields and workload counts only. Backend integration tests and any measured performance are separate from that audit; production load tests remain required before treating proposed latency targets as achieved.

Subsequent scaffold verification: the Python 3.12 foundation passes 15 tests covering fixture import, temporal visibility, semantic duplicates, causal rejection, commit failure, durable restart and cached state reuse. An independent comparison also matches all 18 open-consult fixture fields through the stage-label adapter. Physician state/detection/coverage remain unsupported; this is not a full T1 or core-completion claim.

Runtime update: the deployment baseline is now standard CPython 3.14.7. All 20 current tests pass on 3.14.7, including the real HTTP process restart/persistence test. The earlier 3.12 verification above is historical. Docker and cloud verification remain pending; no comparative runtime benchmark has been performed.

Dependency and logic review: removed unused multipart/server extras, an unused response model and API package, and configuration fields for deferred capabilities. Ingestion now reads the durable log once per batch and filters causal rejects in one pass. The API uses synchronous routes with FastAPI-managed thread-pool execution. Core runtime dependencies are FastAPI, plain Uvicorn and Pydantic; optional accelerators are deferred pending measurement.

Existing-foundation corrections: Signed Off now preserves final ownership, input rejects blank IDs and unknown fields, and failed startup closes SQLite. Snapshot refreshes use the committed event cache and binary search rather than reloading the database. Publication/cache changes still follow successful commit. All 30 tests pass, including concurrent ingestion, backward clocks, late insertion, row-limit rejection and restart. No unimplemented dispatch, physician-state, orphan-hold or authentication capability was added. Request-body byte limiting and full fixture parity in CI remain outside the completed foundation; no performance claim is made from test duration.

P2 branch update: G1–G8 domain implementations now include reference normalization/activation, durable timed holds, persistent quality metrics, physician sessions/classification, routing eligibility and counters. All supplied physician/consult snapshot fields match through display adapters. The earlier unsupported-domain statements are historical; current API wiring and team boundaries are recorded in [P2 handoff](P2-Backend.md). P1 must schedule idle expiry and expose the reference/physician/upload hooks; P3 detection and coverage work remains separate.
