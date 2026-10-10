# Sevaro Command Center PRD v2.2

Oct 10, 2026 · @Rishabh

Updated against the supplied March 17, 2026 fixtures. [Backend Scaffold Review](Backend%20Scaffold%20Review.md) records the original discrepancies; [Command Center Backend Scaffold](Command%20Center%20Backend%20Scaffold.md) defines the implementation contract. The source CSVs remain unchanged. Expected values below describe this dataset; synthetic cases are explicitly identified.

## Organizer clarification and testing data

Carl Dugart confirmed that judging will introduce held-out data covering the same operational scenarios, including additional March 17, 2026 calls/consults. Longer-term history is unnecessary: these scenarios can occur within one day. For team-generated dataset extensions, he recommends a different date and different ID prefixes, such as `EVT-T0001`. Exact delivery format, clock control, reference changes and schema/value compatibility have not yet been confirmed.

Maintain three separate uses: the unchanged March 17 base/snapshot fixtures; controlled March 17 append rehearsals in a disposable test database to prepare for judging; and independently generated single-day practice datasets on another service date with unique event/consult prefixes and consistent references. Generated rows must preserve scenario/schema relationships, not add invented external factors. Do not mix practice data into the judging base or replace it with a generated history.

Generality is tested with other dates and ID prefixes. Live correctness is tested by appending new events without restart/reset, preserving prior state, enforcing event-time visibility, and handling repeated/late deliveries. No seven-day/month-long synthetic history is required. Near-term operational projections use current workload, roster intervals and supplied baseline/coverage inputs with explicit assumptions; synthetic scenarios verify rule/constraint behavior; they do not prove real-world assignment improvements. [P2 handoff](P2-Backend.md) distinguishes domain verification from the P1/P3 integration still required.

## Overview

We build a real-time command center that rebuilds physician state and consult lifecycle from an event stream, and surfaces the four hidden situations the brief scores on. Core scope is G1 to G15 plus G8b. The split-shift offer loop (G16 to G24) is a stretch goal, started only if core is green at H20.

**Problem.** Physicians juggle calls, video, imaging and notes while consults keep arriving. Operations has no live picture of who is available, who is overloaded and which consults are stuck.

**Operations objective.** Reduce arrival-to-assignment and assignment-to-contact time, prevent stage breaches, balance active work and unfinished notes, and preserve hospital coverage. Clinical urgency follows the supplied consult type and configured operations standards. A queue score orders attention; physician eligibility and matching are separate decisions.

**Winning cases (from the brief)**

| # | Hidden situation | Detected by |
| --- | --- | --- |
| W1 | Consult aging in triage, unassigned | G9, G11 |
| W2 | Overloaded physician | G8b |
| W3 | "Available" physician actually on video | G6, G14 |
| W4 | Notes piling up before shift end | G10 |

**Users**

| User | Sees | May do |
| --- | --- | --- |
| Operations coordinator | Queue, breaches, physician activity, projected gaps | Act on alerts, reassign (stretch) |
| Clinical lead on duty | Stroke-risk items, proposed interventions | Approve or reject offers (stretch) |
| Off-shift physician | One offer: hospitals, hours, start | Accept or decline (stretch) |

**In scope (core):** state rebuild from events, consult and physician state kept separately, time in stage, per-physician workload, alerts, 90-minute coverage forecast, attention queue, live event ingest, dashboard.

**Next priority after core:** read-only, explainable assignment recommendations and shared-capacity checks. These precede the external offer loop when time permits. They do not change the production router.

**Stretch:** reassignment actions, split-shift offers, approval, Flutter physician app.

**Out of scope:** clinical decisions, real scheduling, credentialing or messaging systems, compensation, changing the production routing engine.

## Stack and runtime

FastAPI backend on Render, Vite + React dashboard on Vercel, one deterministic engine with an injectable clock.

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python 3.14.7, FastAPI, Pydantic v2 | Native async and WebSockets; OpenAPI schema lets frontend generate types and work in parallel |
| Engine | Pure Python replay functions, stdlib csv for reference loads | Deterministic, testable against snapshots |
| Storage | Amazon RDS for PostgreSQL | Event log, quarantine, audit; append-only |
| Dashboard | Vite, React, TypeScript, Tailwind, ECharts | Client-only app; server rendering adds nothing |
| Contract | `openapi-typescript` | Frontend types generated from backend schema |
| Physician app (stretch) | Flutter web | Judges open a URL on any phone |
| Tests and CI | pytest, GitHub Actions | Core fixtures, synthetic boundaries, recovery and consistency checks run on every push; stretch tests only when implemented |

**Hosting**

- Backend: Render paid web service in Virginia, 1 uvicorn worker, events in RDS PostgreSQL (us-east-1). The free tier spins down after 15 min idle.
- Dashboard and Flutter web: Vercel, preview URL per pull request.
- First fallback: AWS EC2 with the same Docker image and a local-filesystem EBS data volume.
- Last resort: Azure Linux VM with the same image and a managed data disk. See [Deployment](Deployment.md) for configurations and storage constraints.

**Clock**

Only clock adapters read wall or monotonic time; reducers and detectors take timestamps as arguments. A `Clock` service has three modes:

- **Wall:** now = real time. Used when the newest `event_time` is within 15 min of wall time at load.
- **Anchored:** now = anchor + monotonic elapsed time since load. Anchor = operator-set "as of" time, or newest `event_time` at load. Set once, never jumps to each new event.
- **Fixed:** explicit dataset date and time; base snapshot tests use March 17, 2026 at 18:20:00 `America/New_York` (`22:20 UTC`). Live tests advance the clock explicitly. A fixed mode may also be used in controlled demos.

The dashboard header shows the mode and current now, with a manual override.

Each snapshot captures one `as_of`, event revision, reference revision and clock revision. Store future events but apply only the accepted event prefix with `event_time <= as_of`. Backward overrides rebuild that prefix. Server receipt time and orphan expiry are independent of this simulation clock.

**Ingest**

All paths normalize into the same canonical event schema before G1.

- CSV upload of events through the dashboard.
- `POST /events`, single or batch JSON.
- Reference file upload, reloadable without restart.
- Header renames handled in `column_map.yaml`, not code.
- Supplied CSV semantics recovered through versioned, exact event-type/description mappings: consult type, physician status, phone-only call completion and routing retry. Unknown descriptions needed for a required field are quarantined. Canonical JSON supplies those fields directly.
- Ingest, reference activation, reset and clock overrides are serialized. A batch is durably committed and atomically published before acknowledgment; readers never observe a partial update. Replay once per accepted batch.

## Inputs

One event stream (1,164 rows, 1,163 unique IDs, March 17, 2026, 07:00 to 18:19:40 ET, sorted by `ingested_at`), six reference files and two snapshot files. Real test data may differ in volume and header names; the schema is strict on meaning and lenient on shape.

| File | Used for |
| --- | --- |
| `event_stream.csv` | Source of truth for everything that happened |
| `hospitals.csv` | 12 hospitals: time zone, coverage tier |
| `physicians_on_shift.csv` | 8 physicians: time-only ET shift starts and ends; no day/night role column |
| `physicians_off_shift_roster.csv` | 6 physicians: opt-in, last shift end, next start, hours in 7 days, time to online, channel, declines in 30 days; no next shift end or offers sent this week |
| `credentialing_matrix.csv` | Which of 14 physicians may take consults from which of 12 hospitals |
| `baseline_hourly_volume.csv` | 12-week weekday mean and p90 per hospital per ET hour (`hour_start_et`) |
| `coverage_requirements.csv` | Minimum credentialed available physicians per hospital per ET time block (`time_block_et`) |
| `snapshot_*_1820.csv` | Reference state at 18:20; replay must reproduce it |

**Event fields**

| Field | Rule |
| --- | --- |
| `event_id` | Unique within dataset generation; identical semantic payload is a repeat, changed semantic payload is a conflict |
| `event_time` | ISO 8601 with offset; preserve the instant and normalize to UTC. All supplied rows use `-04:00`, regardless of hospital zone |
| `ingested_at` | CSV: required ISO 8601 with offset. JSON may omit it, in which case the adapter uses server receipt time; preserve that provenance. Supplied source delivery time remains distinct from server receipt time |
| `consult_id` | Required on all types except physician-only events |
| `event_type` | One of 20 types (below) |
| `physician_id` | Required on assignment, call, video, note, status, camera, heartbeat and shift events |
| `hospital_id` | Required on `consult_received` |
| `consult_type` | Stroke or General Neuro; required on `consult_received` |
| `value` | Status for `physician_status_changed`; `phone_complete` or `continue` for call ends; `retry_in_5m` for routing failures |

**Event types (20):** consult\_received, consult\_triaged, physician\_assigned, incoming\_call\_ringing, incoming\_call\_started, incoming\_call\_ended, outgoing\_call\_started, outgoing\_call\_ended, imaging\_requested, imaging\_returned, video\_started, video\_ended, note\_started, note\_signed, routing\_attempt\_failed, physician\_status\_changed, camera\_active, camera\_inactive, agent\_heartbeat\_lost, shift\_started.

**Physician-only types (no consult\_id):** physician\_status\_changed, camera\_active, camera\_inactive, agent\_heartbeat\_lost, shift\_started.

Resolve time-only shifts against the dataset service date in `America/New_York`, including overnight intervals. A future shift needs a complete interval; `next_shift_start` alone is insufficient. A configured duration must be explicit and labeled as an assumption. Normalize the wide credential matrix (`Y`/blank) to keyed physician/hospital eligibility pairs. Missing references or ambiguous duplicate keys cannot become a healthy zero or silently select the first row.

## Core gates

Every event passes gates in order. Each gate answers one question, applies one rule and writes dashboard values. Stage C runs on accepted changes and relevant deadlines, with a proposed maximum refresh delay of five seconds. Orphan expiry runs on server time even in fixed mode.

### Stage A: Ingest

| Gate | Question | Rule | On fail | Writes |
| --- | --- | --- | --- | --- |
| G1 Well formed | Can we read it? | Required fields per type present; both timestamps have a UTC offset; type is one of 20 | Quarantine with reason | Rejected count, latest reason |
| G2 Duplicate | Seen this `event_id`? | Check accepted and held IDs; same semantic payload is duplicate even if `ingested_at` differs. Changed semantic payload is a conflict | Do not apply twice; retain conflict reason | 1 duplicate: EVT-00529; separate conflict count |
| G3 Late | Earlier than prior accepted event-time watermark? | Normalize UTC, sort by `(event_time, ingested_at, event_id)`; every backward insertion is reordered, watermark lag >60 s is late | Insert and replay batch once | 23 reordered, 1 late; max reorder lag 5:55, max delivery lag 6:45 |
| G4 Known | Physician, hospital, consult exist? | IDs in reference files; non-received consult events need a receipt at or before their event time. Resolve held dependencies after ingest/reference changes | Hold 5 min from first server receipt, then quarantine; repeated deliveries never extend deadline | Pending and expired counts separately; base pending 0 |

### Stage B: State

Consult state and physician state are kept separately. One physician can hold several open consults.

**G5 Consult stage.** Stages may be skipped, never reversed. A backward move keeps the current stage and raises a data-conflict flag. Writes current stage and minutes in stage.

Same-stage repeats do not reset entered time. Keep `note_pending_since` through Documentation for G9. Assignment changes current ownership while preserving handoff history; a follow-up call during imaging changes physician activity without reverting the consult stage. Signed Off remains terminal unless an explicit reopening event is later added to the schema.

| Event | Stage |
| --- | --- |
| consult\_received | Received |
| consult\_triaged | Triaged |
| physician\_assigned | Assigned |
| first call started while Assigned | Provider Contacted |
| imaging\_requested | Imaging Pending |
| imaging\_returned | Imaging Review |
| video\_started | Video In Progress |
| video\_ended, or call ended with phone\_complete | Note Pending |
| note\_started | Documentation |
| note\_signed | Signed Off (closed) |

**G6 Physician state.** First match wins. Self-reported status is shown beside the derived state, never in place of it.

| Order | Signals | Derived state | Routable | Flag |
| --- | --- | --- | --- | --- |
| 1 | Video session open | Video Consult | No |  |
| 2 | Call open | Hospital Call | No |  |
| 3 | Status Temporarily Unavailable | Temporarily Unavailable | No | Stranded consults |
| 4 | Camera active, no session, not In Meeting | Camera Active, No Session | No | External platform |
| 5 | Own consult in Documentation | Documentation | Yes |  |
| 6 | Camera active and In Meeting | Available (meeting) | Yes |  |
| 7 | Agent heartbeat lost | Available | Yes | Unverified |
| 8 | None | Available | Yes |  |

**G7 Routable now.** On shift, routable in G6, phone not ringing, last call ended 2+ min ago. Keeps the exclusion reason (busy, ringing, cooldown, unavailable, off shift).

Shifts use `[start, end)`. Track concurrent sessions and rings by physician and consult (and call direction/session where available); an ending clears only its corresponding session. Answering clears the corresponding ring. Retain all exclusions and one deterministic primary reason; credentials are checked separately per hospital. The sample's PHY-007 is derived Available and unverified, but not G7-routable while its ring is active. Do not silently expire rings without a configured policy.

**G8 Counters.** Consults = distinct consults assigned to that physician in the active shift (same-owner assignment repeats excluded). Calls = valid call starts since shift start, including calls still open (unanswered rings excluded). Open = current own consults not Signed Off. Preserve assignment/session history and last answered time. Snapshot output labels may map canonical enums to fixture labels.

**G8b Overload (new).** Thresholds in config, tuned against the snapshot.

- Warning: 3+ open consults, or consults in last 2 h above 1.5 x the peer median.
- Critical: 4+ open consults, or Warning plus a G10 shift-end risk.

Rate comparison uses distinct assignments in `(as_of - 2 h, as_of]`. Proposed cohort: other on-shift physicians observed for the entire two-hour window, with at least three peers; use an explicit comparable-role cohort when role data becomes available. If the cohort is too small or the median is zero, expose the rate comparison as unavailable and retain the open-work threshold. The warning threshold is not an assignment ban. Validate this policy with operations rather than tuning named IDs.

### Stage C: Detection

**G9 Time standards.** At or over warning = Warning; at or over critical = Critical. Note rows start at Note Pending and run through Documentation.

Evaluate thresholds in seconds without rounding. Floor whole minutes only for display/snapshot comparisons. Starting documentation must not clear accumulated note age.

| Stage | Applies to | Warning | Critical |
| --- | --- | --- | --- |
| Triaged, unassigned | All | 5 min | 10 min |
| Assigned, not contacted | Stroke | 3 min | 8 min |
| Imaging Pending | Stroke | 12 min | 20 min |
| Imaging Review | Stroke | 6 min | 12 min |
| Note Pending + Documentation | Stroke | 30 min | 45 min |
| Note Pending + Documentation | General Neuro | 45 min | 90 min |

**G10 Shift-end notes.** Within 60 min of shift end: 2+ consults in Note Pending or Documentation = Critical; any open consult = Warning.

This window is `0 <= shift_end - as_of <= 60 min`; unfinished work after shift end remains a separate overdue-work alert.

**G11 Stuck consult.** Fires on: triaged, unassigned, with 1+ routing failures (next retry 5 min after last); assigned to a Temporarily Unavailable physician (stranded); assigned with a ring unanswered over 2 min. Lists each credentialed physician with their G7 exclusion reason.

**G12 Demand spike.** Unique received consults in `(as_of - 60 min, as_of]`, against p90 for the reference's declared zone and day category. The supplied `hour_start_et` uses `America/New_York`; hospital-local formats require explicit metadata. Spike only if strictly greater. Spike raises that hospital's current requirement by 1 in G13. Missing day/hour baseline yields unknown demand comparison, not no spike.

**G13 Coverage, now and +90 min.** In 15-min steps.

- Now: on shift, credentialed, routable (G7).
- Projected at t: credentialed and scheduled on shift at t; drop shifts ending at or before t; add complete shift intervals starting by t; exclude Temporarily Unavailable until status changes. A next start without an end is incomplete schedule data, shown explicitly and excluded from confirmed counts.
- Requirement from the ET block containing t, including blocks that cross midnight. For the core scenario, carry the current +1 spike uplift across the horizon and label that assumption; this is not a prediction of future arrivals. Missing requirements yield unknown coverage.
- Gap = requirement minus count, when above 0. Agent-offline physicians count but the cell is marked unverified.

Projected cells represent potential scheduled coverage: they assume current calls/videos have ended, rather than predicting their remaining duration. Show the counted physician IDs and schedule completeness. Incomplete schedule yields an observed lower bound on capacity, not a confirmed staffing deficit. Per-hospital counts reuse physicians across hospitals and cannot prove simultaneous demand feasibility; shared-capacity checks are a separate next-priority feature.

**G14 Signal conflicts.** Camera active with no session and not In Meeting; agent heartbeat lost; status Available while derived busy for 30+ min (info).

**G15 Attention queue.** Score = level (Critical 100, Warning 50, Info 10) + 30 if stroke + 10 per routing failure (max 30) + for projected gaps 30 x (1 minus minutes to gap / 90). Ties: oldest first. Gap now or within 60 min = Critical; 60 to 90 min = Warning. Stuck stroke consult = Critical, others Warning. Overload (G8b) uses its own level. Each item carries a plain-language reason.

The stroke bonus applies to consult items with supplied type Stroke; hospital gaps receive no inferred stroke bonus. Keep numeric scores unrounded for sorting and display two decimals when fractional. Use stable item IDs, group duplicate reasons for the same entity, choose the highest severity, and break equal score/age by stable ID. Schedule-incomplete gaps carry an uncertainty label. A hypothetical confirmed gap 40 minutes away scores 116.67, not 147. G15 orders attention; it does not reserve physician capacity.

## Dashboard

Every value is written by one gate. If a number looks wrong, check the gate beside it.

**Headline numbers:** open consults, consults past Critical, unassigned consults, overloaded physicians, hospitals with a gap now, hospitals with a gap in the next 90 min. Header also shows clock mode and current now.

| Panel | Shows | Gate | Expected at 18:20 |
| --- | --- | --- | --- |
| Attention queue | Rank, score, reason, uncertainty | G15 | CON-2105 scores 160; remaining order derived from rules, not a hardcoded second item |
| Consult board | Stage, minutes in stage, timer colour | G5, G9 | 18 open; CON-2102 imaging 26 min (Critical) |
| Stuck consults | Unassigned, stranded, routing failures, exclusions | G11, G7 | CON-2105 (3 failures), CON-2114 (1), CON-2110 stranded |
| Physician board | Derived state vs self-reported, agent, confidence, routable, reason | G6, G7 | PHY-001 camera, no session; PHY-007 agent offline and excluded while ringing |
| Workload | Consults, calls, open, minutes to shift end, overload badge | G8, G8b | PHY-003: 14, 17, 3, 40 min |
| Shift-end risk | Leaving within 60 min with open notes | G10 | PHY-003 Critical, PHY-006 Warning |
| Demand | Trailing 60-min count vs p90, surge badge | G12 | Suncrest 5 vs 1 (surge); Lakeview 1 vs 2 (none) |
| Coverage forecast | Now plus potential scheduled coverage, hospitals x 15-min steps to +90 min; completeness and physician IDs | G13 | At 19:00 Suncrest requires 2 in the surge scenario; supplied complete intervals count only PHY-005. Cho is credentialed but has an incomplete future interval |
| Signal flags | Contradicting or unverified signals | G14 | PHY-001 external platform; PHY-007 offline |
| Data quality | Rejected, duplicates, conflicts, reordered, late, pending/expired orphans, both lag measures | G1 to G4 | 0 rejected, 1 duplicate, 0 semantic conflicts, 23 reordered, 1 late, 0 pending orphans; reorder lag 5:55, delivery lag 6:45 |
| Live injector | Upload or post events, reset to base | Ingest | Used for T23 to T27 |

Expected values are test fixtures. App code never references specific IDs.

The sample's source snapshot shows PHY-007 with 6 calls, not an unanswered-ring call. Headline gap counts distinguish confirmed gaps from possible gaps with incomplete schedules. Snapshot and pushes include server epoch and ordered sequence; reconnect reloads a snapshot, and a slow client cannot block ingestion. Mutations and demo admin controls require server-side authorization.

## Operations recommendations after core

**Implementation constraint:** routing is a deterministic constrained-allocation problem. Use current state, credentials, shift membership, availability and explicit per-physician capacity to define feasible assignments; use documented operational costs and stable tie-breakers to compare them. No AI/ML model, training pipeline, inference service or model-provider dependency is required or allowed in this design. Coverage forecasts are explicit schedule/demand scenarios. Pydantic schemas validate input data and are unrelated to learned models. This does not expand P2 beyond eligibility and state/counters; recommendation ranking remains with the team.

Provide a read-only recommendation for each waiting consult with feasible physician IDs, every exclusion and the state revision used. Filter credentials and G7 first. Rank feasible candidates by active work, open consults, unfinished notes, remaining shift and lost coverage; show component values so an operator can understand the choice. Define and version any weights with operations rather than inventing them from this small sample.

When multiple consults are waiting, evaluate them together with an explicit per-physician assignment capacity. Preserve a feasible unassigned outcome and avoid repeatedly recommending the same sole eligible physician. A shared-capacity feasibility view must account for physicians credentialed at several hospitals. Automated dispatch remains outside scope; any future assignment command revalidates the revision/eligibility and reserves capacity transactionally.

Success measures: arrival-to-assignment, assignment-to-first-contact, oldest unassigned age, stage breaches, unfinished work after shift end and workload distribution. Establish a replay baseline first; the sample does not establish a counterfactual improvement or validated evidence for service-time estimates.

## Stretch: intervention loop

Started only if core tests T1–T12, T23–T28 and consistency checks pass at H20. T13/T14 belong to stretch and cannot block core completion. The external offer loop also requires complete schedule intervals and offer history; missing eligibility inputs are Unknown and block sending.

| Gate | Rule |
| --- | --- |
| G16 Cheapest fix | Try in order: reassign to a routable credentialed physician; escalate a Critical stroke item; show scheduled coverage that closes the gap; else build a split-shift offer |
| G17 Eligibility | Test every off-shift physician on R1 opt-in, R2 credentialed at a gap hospital, R3 10 h rest, R4 7-day hours + offer at most 60, R5 no overlap, R6 2 h minimum and can come online, R7 one open offer, R8 under 3 offers in 7 days. Keep every result |
| G18 Rank | Most gap hospitals, fewest minutes to online, fewest declines in 30 days, fewest hours in 7 days |
| G19 Trap guard | Joiner routable only at gap hospitals; seeded at lowest peer count at the gap hospital; simulate 90 min of baseline demand with and without; pass if gap closes, no other gap worsens, joiner load at most busiest peer |
| G20 Approval | Only the clinical lead approves, enforced server side. No auto path |
| G21 Pre-send check | Re-check R1 to R8 and gap; message holds hospital, hours, start only; lock offer slot; 10-min timer |
| G22 Response | Accept with gap open = Accepted (one transaction). Accept after fill = Already filled. Decline or 10-min timeout = next candidate |
| G23 Close | Add physician with G19 limit and seed; re-run G13; withdraw other offers when closed |
| G24 Audit | Append-only log of gap, every physician, every rule result, proposer, approver, send, answer, final coverage |

**Offer states:** Proposed, Approved, Rejected, Sent, Cancelled, Accepted, Already filled, Declined, Expired, Withdrawn.

## Acceptance tests

Core is done when T1–T12 and T23–T28 pass with no restart between base load and live test, plus the boundary/recovery checks below. T13–T22 apply only if stretch is built. Implemented endpoints or passing scaffold smoke tests alone do not establish core completion.

**Core, base stream at 18:20 (fixed clock)**

| # | Test | Gate | Expected |
| --- | --- | --- | --- |
| T1 | Replay matches snapshots | G1 to G8 | At March 17, 2026, 18:20 ET, 8 physician rows and 18 open-consult rows match `snapshot_*_1820.csv` through the display-label adapter; compare all supplied fields |
| T2 | Duplicate dropped | G2 | EVT-00529 applied once; 1 duplicate, 1,163 unique events |
| T3 | Late video placed by event time | G3, G5 | CON-2107 in Video since 18:11:20; PHY-006 on video |
| T4 | Camera, no session (W3) | G6, G14 | PHY-001 busy and flagged |
| T5 | Agent offline and ringing | G6, G7, G14 | PHY-007 derived Available, unverified, not routable while its ring is active; 6 answered calls |
| T6 | In Meeting with camera (synthetic) | G6, G7 | With no active call/video/ring, on shift and out of cooldown, remains routable |
| T7 | Stranded stroke consult | G11 | CON-2110: PHY-008 Temporarily Unavailable, Assigned 12 min, Critical |
| T8 | Nobody can take it (W1) | G11 | CON-2105: 3 failures, each credentialed physician with reason |
| T9 | Shift-end notes (W4) | G10 | PHY-003 Critical, 2 open notes, 40 min left |
| T10 | Spike and equality boundary | G12 | Base: Suncrest 5 > 1 surge; Lakeview 1 < 2 no surge. Synthetic: count equal to p90 produces no surge |
| T11 | Projected coverage and schedule completeness | G13 | Surge scenario at 19:00: Suncrest requirement 2, complete-interval count 1 (PHY-005), schedule incomplete. Synthetic confirmed interval for Cho covering 19:00 gives count 2 and no gap; Cho is credentialed there |
| T12 | Workload from credentials | G8, G6 | PHY-007: 6 consults, 2 credentialed sites |
| T28 | Overload (W2) | G8b | Open-work warning includes PHY-002, PHY-003, PHY-006; G10 risk escalates PHY-003 and PHY-006 to Critical. Separate synthetic tests cover rate cohort, zero median and insufficient peers |

**Live test (new synthetic `live_test_events.csv`, fed one at a time)**

This file is absent from the supplied data. The cases below are a controlled March 17 append rehearsal in a disposable test database, reflecting the announced judging extension; they are not a generated replacement/extension distributed with the official dataset. Independent generated practice datasets must use another service date and a distinct event/consult ID namespace, following the organizer guidance. Record explicit clock advancement per test; it must pass events' times and delivery times consistently. T23 count assertions require that no prior Suncrest receipt expires from the trailing window during the two injections.

| # | Events | Expected |
| --- | --- | --- |
| T23 | Stroke consults CON-2119, CON-2120 at Suncrest, routing fails | Trailing count 6 then 7; both Critical in queue |
| T24 | CON-2119 received twice | Counted once |
| T25 | CON-2101 video\_ended 3 min late | Note Pending from 18:21:10, not arrival |
| T26 | PHY-007 answers CON-2109 | PHY-007 busy, ring cleared, answered-call count increments; base G7 coverage does not decrease because the existing ring already excluded it. A separate synthetic no-ring/out-of-cooldown precondition tests a real current-coverage drop |
| T27 | PHY-008 Available, calls on CON-2110 | Stranded clears; CON-2110 to Provider Contacted |

**Core boundary and consistency checks:** exact warning/critical thresholds; continuous Note Pending-to-Documentation age; same-stage repeats; matched session endings; same-owner/reassignment history; ET, overnight and DST shifts; future-event exclusion and backward-clock rebuild; child-first orphan release and fixed-clock expiry; conflicting duplicates; missing baseline/schedule inputs; simultaneous ingest/reference/reset; failed durable commit; restart with the same reference revision; stale WebSocket message rejection; and slow-client isolation. Copy fixtures into CI because the current `data/` folder is gitignored.

**Stretch tests:** T13 evaluates all R1–R8 using a separate fixture with complete schedules and offer history; Alvarez is ineligible for a Suncrest-only gap because he lacks that credential. T14 verifies gap closure, no worsened shared-capacity gap and disclosed load seeding without hardcoded physician/site counts. T15 no send without approval; T16 rejection returns item; T17 message has no patient data; T18 expiry after 10 min; T19 second acceptance gets Already filled; T20 gap closes and offers withdraw; T21 offer limits; T22 full audit trail.

**Performance targets (proposed, not measured):** on the intended deployment, p95 single-event ingest-to-publication <=250 ms, p95 cached snapshot <=100 ms, relevant deadline visibility <=5 s and base import <=2 s. Measure durable commit, replay, detection and serialization separately at sample volume and 10x/100x, with concurrent readers, late inserts and a slow WebSocket. Record event rate, batch size and hardware. Keep full replay as a differential oracle if later introducing incremental updates. Five-second freshness describes the proposed service objective, not observed performance.

## Team and plan

Six people, 36 hours, five parallel workstreams. Pydantic schemas freeze at H2 so everyone builds against mocks from then on.

| Person | Owns | Tests |
| --- | --- | --- |
| P1 Backend lead | API, WebSockets, clock modes, ingest endpoints, deploy, reset | Integration |
| P2 Backend | G1 to G8 replay engine, quarantine, column map | T1 to T6, T12, T24, T25 |
| P3 Operations/data | G8b to G15, alert reasons | T7 to T11, T23, T26 to T28 |
| P4 Frontend | Consult board, physician board, attention queue | Visual |
| P5 Frontend | Workload, heatmap, data quality, live injector | Visual |
| P6 Flutter | H0 to H20: test harness, live-test runner, demo script. After H20: Flutter offer app (stretch) | Harness for all |

**Critical path:** P3 depends on P2's state. P3 builds against `snapshot_*_1820.csv` until P2's engine lands at H12.

&#91;embedded content: 36-hour plan · 7 phases, 4 gates\]

If T1–T12, T23–T28, consistency checks and the four winning cases are not green at H20, the stretch loop is dropped and H24 to H30 goes to core fixes. Read-only recommendations are the next optimization increment after core, before external offers.

**Cut list if behind at H20**

1. Drop the whole stretch loop.
2. Heatmap becomes a table.
3. Live injector becomes CSV upload only.

## Assumptions and open questions

Each assumption lives in one config value or one function, so it can change in one place.

**Assumptions**

- Late = prior accepted event-time watermark lag over 60 s (G3); delivery lag is a separate measure. The brief sets no threshold.
- An unanswered ring is not a call (G8) but blocks routing while it rings (G7).
- Projected coverage counts complete scheduled intervals and excludes Temporarily Unavailable; now counts only G7-routable ones. Current busy sessions are assumed released in projected cells. Unknown upcoming intervals are exposed.
- Spike uses the reference's declared time zone (ET for supplied files), recomputed as the count changes. Current spike uplift is carried through the forecast as an explicit scenario.
- Overload thresholds and the proposed peer-cohort rule are initial operations assumptions, validated at H12. They do not determine dispatch eligibility.
- Agent comes back online on any later camera event; the brief has no heartbeat-restored event.
- Shift end comes from roster times; the brief has no shift-ended event.
- `offers_declined_last_30d` maps to the G18 decline metric. Offers sent in seven days and current offer slots need an audit/history source; absent data is Unknown rather than zero.
- Reference headers are known for the supplied files; new formats require versioned mappings and explicit time-zone metadata.
- Naive timestamps are rejected, never assigned a zone.

**Open questions**

- [ ] How will the held-out March 17 data arrive: CSV upload, API batch or event stream? How is simulation time advanced during judging?
- [ ] Will new physician/hospital IDs come with updated rosters and credentials, or will the extension use existing reference IDs?
- [ ] Will held-out columns, event types, description values and timestamp offsets follow the supplied CSV conventions?
- [ ] What are the judging criteria and their weights? Decides whether live test work moves before H24.
- [ ] How long is a Temporarily Unavailable status trusted before it is flagged stale?
- [ ] What clears an unanswered ring when no answer/cancel event arrives? Until a policy is configured, retain the routing exclusion and expose its age.
- [ ] What are the authoritative complete upcoming shifts and offer-history sources? Required before confirmed future staffing or offer eligibility.
- [ ] Which workload/cohort rules and concurrent-assignment capacities should govern recommendations? Current overload warnings remain advisory.
- [ ] Should General Neuro in Imaging Review get its own time standard?
- [ ] Who can see the audit log: coordinators, clinical leads, or both?
