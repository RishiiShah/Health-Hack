# Decision engine: Detect inputs → Decide → Act

Owner: Rishi (backend). Scope: the server-side algorithm that turns published state into ranked problems, chooses the fix and approver, and runs the offer loop. Web and mobile only display these results ([00-Boundaries](00-Boundaries-and-Contracts.md)).

Sources: brief `problem/Sevaro_…_Challenge_2_…pdf` [B pN], handbook `Handbook/Challenge_2_Handbook.pdf` [H chN], `data/*.csv`, the P2 engine in `backend/app/engine/`. Tags in this doc: `[B]`/`[H]` = stated in a source, `[D]` = observed in the data, `[A#]` = our assumption (section 9).

## 1. What we found in the sources and data

These facts shape the design. Several contradict the earlier handoff note.

| # | Finding | Consequence |
|---|---|---|
| F1 | Baseline column is `hour_start_et`; coverage blocks are `time_block_et` (16:00-22:00, 22:00-07:00 crosses midnight) [D] | Surge hour and coverage block are looked up in **ET**, not hospital-local time |
| F2 | Suncrest (SYN-005) received 5 consults 17:40-18:15; p90 for 18:00 is 1 [D] | Surge, requirement 1 → 2. Lakeview 1 vs p90 2: no surge |
| F3 | Suncrest surge, counted from already-received consults only, lasts until 19:04:30, when CON-2107 (18:04:30) leaves the window [D] | A projected surge has an end time; it is not "on for the rest of the horizon" |
| F4 | Night starters are only in the off-shift roster (`next_shift_start` 19:00 Cho, 20:00 Haddad), with no end time. P2's loader creates no future shift for them [D] | We need a "scheduled start, end unknown" capacity source |
| F5 | Counting Cho at 19:00, Suncrest has 1 confirmed (PHY-005) + 1 scheduled = 2 = requirement. Not counting her, Suncrest is short 19:00-19:04 [D] | The sample's "projected gap" depends on this choice → two-tier gaps (section 4.3) |
| F6 | Extending past 90 min: Northfield (SYN-008) is short **20:00-22:00** even counting both night starters (1 < 2); Cedar Ridge (SYN-001) and Redwood (SYN-003) are short 21:00-22:00 [D] | Project to the last known shift boundary, but label anything beyond now+90 as outlook |
| F7 | Off-shift R1-R8 for a Suncrest gap: Okafor passes all; Alvarez fails R2; Cho fails R5 (her 19:00 night shift); Brennan fails R1; Haddad fails R1 and R2; Menon fails R4 (59 h + 2 h > 60). For the Northfield 20:00 gap Okafor is again the only one (Menon then fails R2) [D] | Matches the brief's "exactly one eligible, others fail one rule each" [B p7], but only when candidates are evaluated **per gap**, not against every gap of the day |
| F8 | For the 21:00 Cedar Ridge gap nobody qualifies (only Menon is credentialed, R4 fail); Alvarez qualifies for Redwood 21:00 but the gap is only 60 min of a 2 h offer [D] | Real "nobody eligible → escalate" case and a "low-value offer" case in the same day |
| F9 | Every Harbor-credentialed on-shift physician is busy at 18:20, so CON-2110 (stranded with PHY-008, Temporarily Unavailable) cannot be reassigned now [D] | Reassign is not always feasible; escalation must say why |
| F10 | No repeat call exists in the sample. P2 replay keeps the first `received_at` and flags `multiple_receipts` on a second `consult_received` [D] | Live test may add one. We need a repeat count, not just a flag |
| F11 | P2 replay does not count `routing_attempt_failed` per consult [D] | Add `routing_failures` and `last_routing_failure_at` to consult state |
| F12 | `physicians_on_shift.csv` has no Day/Night role; the roster has `role` (Day/Night/Float) [D] | Routing threshold (6 day / 4 night) needs a rule for on-shift physicians [A7] |
| F13 | The brief says all three layers are required [B p1, H ch3]; the PRD marks the offer loop as stretch | Treat Act as core for our area. PRD wording should change (Rishi owns the PRD) |

## 2. Shape of the engine

Everything below is a **pure function of (publication bundle, ops references, offer log, now)**. No I/O, no clock reads, no randomness. Only commands (section 6) write.

```
Published bundle (P2, immutable, revision R)
   │  + OpsRefs (baseline, coverage, roster details)   + OfferLog (DB)   + now
   ▼
1 detect()     → Findings          (stage timers, notes-at-shift-end, stranded, surge, signals)
2 project()    → CoverageTimeline  (per hospital, piecewise-constant over [now, outlook end])
3 gaps()       → Gaps              (hard / at-risk, interval, cause)
4 decide()     → Recommendations   (fix, approver, alternatives rejected and why)
5 eligibility()→ CandidateTable    (every off-shift physician × R1-R8, values, window)
6 trap_check() → RoutingSim        (with/without joiner, restricted+seeded vs not)
7 rank()       → Queue             (lexicographic key, every item has what/where/why/fix)
   ▼
Snapshot section `decisions` tagged {revision R, as_of now}
```

Recompute the whole pipeline on every publication and every clock minute; cache by `(revision, offer_log_version, as_of minute)`. Sizes are small (12 hospitals × 14 physicians × ~30 change points; open consults are O(tens) even at 100× events), so incremental logic is not worth its bug risk here. Full recompute is also the oracle for tests.

Proposed layout (all in `backend/app/`):

| Module | Contents |
|---|---|
| `ops/refs.py` | Load and validate `baseline_hourly_volume.csv`, `coverage_requirements.csv`, roster details (opt-in, last end, next start, hours 7 d, minutes to online, channel, declines, role) |
| `ops/detect.py` | G9 stage timers, G10 notes near shift end, G11 stranded/unassigned, G14 signal conflicts |
| `ops/coverage.py` | G12 surge, G13 projection and gaps |
| `decide/interventions.py` | Fix choice per finding, alternatives, approver |
| `decide/eligibility.py` | R1-R8, offer window, candidate ranking |
| `decide/routing_sim.py` | Deterministic routing model and trap check |
| `decide/rank.py` | Queue ordering and explanation text |
| `act/offers.py` | Offer state machine, commands, audit, expiry sweep |

## 3. Detect (inputs to decisions)

### 3.1 Stage timers [B p3, H ch5]

| Stage (P2 canonical) | Applies | Warning | Critical | Clock starts at |
|---|---|---|---|---|
| Triaged | All | 5 | 10 | `entered_at` of Triaged |
| Assigned | Stroke | 3 | 8 | `entered_at` of Assigned (re-assignment does not restart it [A33]) |
| Imaging Pending | Stroke | 12 | 20 | stage entry |
| Imaging Review | Stroke | 6 | 12 | stage entry |
| Note Pending + Documentation | Stroke 30/45, General 45/90 | | | `note_pending_since` (continuous across both stages) |

- Level is reached **at** the limit (`age >= limit`) [A34]. Ages use `event_time`, never `ingested_at`.
- Each item carries `limit`, `age`, `due_at` of the next level, so the UI can count down without recomputing rules.
- `Received` (not yet triaged) has no standard. Report it as info once it exceeds the Triaged warning, labelled "no standard; untriaged" [A35].

### 3.2 Open notes near shift end [B p3]
For each on-shift physician with `minutes_to_shift_end <= 60`: open notes = owned consults in Note Pending or Documentation. 1 → Warning, ≥2 → Critical. Also list owned consults **not** in a note stage (e.g. PHY-003 owns CON-2102 in Imaging Pending, ends 19:00); those need a handoff (section 5.1).

### 3.3 Stranded and unassigned
- **Unassigned:** stage ≤ Triaged and no owner. Add `routing_failures`, `next_retry_at = last_failure + 5 min` [B p3], and the per-physician exclusion list for the hospital (credentialed on-shift physicians with their G7 reasons; uncredentialed are summarized as a count).
- **Stranded:** owner exists, consult not Signed Off, owner is Temporarily Unavailable, off shift, or Camera-Active-No-Session.
- **Repeat call:** `repeat_contacts` = extra `consult_received` rows for the consult [A32]. Waiting time stays anchored at the **first** contact. Different `consult_id`s are never merged [H ch2 #7].
- **Unanswered ring:** ring open ≥ 2 min [A36] → Warning with "most physicians busy" context (count of routable credentialed physicians).

### 3.4 Signals [B p3]
Camera active, no session (BUSY_EXTERNAL) and agent offline (unverified) come from P2 `flags`. Self-reported Available while busy is **not** flagged [B p5].

## 4. Coverage projection and gaps

### 4.1 Capacity sources per hospital h at time t

| Source | Counts from | Counts until | Confidence |
|---|---|---|---|
| On-shift physician, credentialed at h, not Temporarily Unavailable | now | shift end (exclusive) [A9] | confirmed |
| On-shift but Temporarily Unavailable | — | — | not counted; assumed to stay TU through the horizon [A37] |
| Roster physician with `next_shift_start` in the horizon | `next_shift_start` | horizon end (end unknown) | scheduled (confirmed once `shift_started` arrives) |
| Accepted split shift | offer start | offer end | confirmed, **only at the offer's hospitals** (trap guard) |

Busy (call, video, ringing) does **not** remove coverage; it is transient and handled at consult level by 3.3. Agent offline and BUSY_EXTERNAL still count but mark the hospital "coverage relies on unverified physician" [A24b].

### 4.2 Requirement
`required(h, t) = min_available(h, ET block containing t) + surge(h, t)`.

`surge(h, t)`: distinct consults first received at h in `(t − 60 min, t]`, counting only consults **already received** (no forecast demand), compared **strictly greater** than `p90(h, ET hour of t)` [B p4, PRD T10]. If p90 = 0, any consult is a surge [A30]. A missing baseline row makes the surge **unknown**, reported as a data-quality finding, never as 0.

Why observed-only for the future: baseline mean is ≤ p90 by construction, so adding forecast demand only creates fractional boundary artefacts. The projected surge ends when the last qualifying consult ages out (F3). A new event during the live test extends it automatically.

### 4.3 Timeline and gap classes
Change points = now, every shift start/end, block boundary, each `received_at + 60 min` at a surging hospital, each scheduled start, each accepted offer start/end, now + 90 min. Between change points every count is constant, so gaps are **exact intervals**, not samples.

- **Hard gap:** confirmed + scheduled < required.
- **At-risk:** confirmed < required ≤ confirmed + scheduled (closes only if the scheduled starter comes online). If no `shift_started` by start + 5 min [A38], it becomes hard.
- **Horizon:** now to now + 90 min is the required window [B p8 #4]. Outlook continues to the last known shift boundary; outlook items rank below in-horizon items with the same severity.
- Every gap carries its **cause**: which shift ends, which surge, which physician is TU.

With the sample: Suncrest 19:00-19:04:30 at-risk (relies on Cho), Northfield 20:00-22:00 hard, Cedar Ridge and Redwood 21:00-22:00 hard (outlook).

**Open decision (needs organizer confirmation):** if the scheduled night starter should *not* count until `shift_started`, Suncrest 19:00-19:04:30 becomes the hard in-horizon gap the brief seems to intend. This is one line in the capacity function; the two-tier output shows both readings meanwhile.

## 5. Decide

### 5.1 Intervention per finding (cheapest safe fix first)

Every recommendation lists the alternatives it rejected and why [H ch4: "why that fix over the others"].

| Finding | 1st choice (if feasible) | Else | Approver |
|---|---|---|---|
| Unassigned or stranded consult | **Reassign** to a routable credentialed physician, chosen by the modeled routing order (5.4) so it matches what the router would do | **Escalate** to clinical lead with the exclusion table and concrete options (ask the TU owner to return, interrupt physician X when their session ends, accept delay) | Reassign: coordinator. Escalate: coordinator raises, lead authorizes |
| Owned consult whose owner's shift ends before the work can finish (non-note stage, ≤60 min to shift end) | **Handoff** to a credentialed physician on shift past the owner's end, preferring routable now | Escalate | Coordinator |
| Notes near shift end | **Contact physician** (internal alert, may be automatic) | — | Automatic alert; coordinator follows up |
| Stage breach with available owner | **Contact physician** | Escalate if stroke and Critical | Coordinator |
| BUSY_EXTERNAL / agent offline | **Verify with physician** | — | Coordinator |
| Hard gap | Scheduled coverage already closes it? → **Watch** | **Split-shift offer** (5.2) → if no eligible candidate, **escalate** with the full table [H ch2 #8] | Coordinator proposes, lead approves |
| At-risk gap | **Watch** with a pre-computed candidate table, promoted automatically if it turns hard | — | — |
| Credential-driven imbalance (load ratio vs peers explained by credential count) | **Inform** only; no live action fixes credentials | — | — |

Feasibility for reassign/handoff uses G7 routability now plus credentials. If nobody is routable, the recommendation says so and names the earliest **known** end of a blocking session only when the data has it (no duration guessing).

### 5.2 Split-shift eligibility (R1-R8) [B p4, H ch5]

Evaluate **every** off-shift physician against **every** rule, never short-circuit, and keep the value behind each result.

Candidates are evaluated **per coverage case**: one hospital's hard-gap interval `[gs, ge)`. Offer window for candidate p:
- `start = max(now + minutes_to_online(p), gs)`
- `end = max(ge, start + 2 h)` (not capped at the outlook end, or R6 would fail for every late gap)
- Offered hospitals = the case hospital, plus any other hard-gap hospital p is credentialed for whose gap overlaps the window (extra coverage, shown separately). Never non-gap hospitals (trap guard and message content).
- Sample: Northfield `[20:00, 22:00)` → Okafor 20:00-22:00, net 2 h, R3 13 h, R4 38 h.

| Rule | Check (at the window above) | Value shown |
|---|---|---|
| R1 | opt-in = Yes | Yes/No |
| R2 | credentialed at the case hospital | credentialed gap hospitals |
| R3 | `start − last_shift_end >= 10 h` | hours rested at start |
| R4 | `hours_last_7d + accepted split hours this week + (end − start) <= 60` | total |
| R5 | `[start, end)` does not intersect `[next_shift_start, ∞)` or any accepted shift | conflicting shift |
| R6 | `end − start >= 2 h` (start already includes time to come online) | net hours |
| R7 | no open offer (PROPOSED, APPROVED, SENT) for p | open offer ID |
| R8 | offers SENT to p in the trailing 7 days + 1 <= 3 | count (0 with "no history supplied" if none) [A16] |

Rules are evaluated on the natural window and never relaxed. Scheduled night shifts are capacity, not offers [B p6]; Cho therefore shows R5 fail, which is the honest reason.

**Rank eligible candidates** (lexicographic, each component displayed): most hard-gap minutes covered → fewest minutes to online → fewest declines in 30 days → fewest hours in 7 days → fewest offers this week (fairness) → `physician_id`. No weights.

**Value floor:** if covered gap minutes < 60 [A39], mark "low value" (the Alvarez/Redwood case). Still eligible; the lead decides.

### 5.3 Trap guard [B p3, H ch2 #9]
On acceptance the joiner is added to routing and coverage with:
- **Restriction:** eligible only at the offered gap hospitals.
- **Seed:** `seed = max(low_volume_threshold + 1, min consults_this_shift of on-shift peers credentialed at the gap hospitals)` [A26]. Threshold is 6 for day, 4 for night [B p3]; for the joiner use 6 (covers both) [A7].
- Seeding is a recommended router setting for the joiner's session; we model its effect and do not change the production router [B p8].

### 5.4 Routing simulator (model, not replacement)
Deterministic discrete-event replay over the horizon:
- Demand: per hospital, baseline mean arrivals placed where the cumulative expected count crosses each integer (deterministic, no randomness) [A12]. A second scenario continues the observed trailing-60 rate at surging hospitals.
- Service time: per consult type, the median busy time observed today (call + video durations from the replayed day) [A40].
- Routing: rules 1-5 of [B p3] exactly, ties by least-recent answer then `physician_id`.
- Runs: (a) no joiner, (b) joiner unrestricted and unseeded (the trap), (c) joiner restricted and seeded.
- Output per run: calls per physician per hospital, joiner share, failed routes per hospital, peer load change.
- Pass for (c): joiner gets calls only at gap hospitals, failed routes at gap hospitals do not increase vs (a), joiner load ≤ busiest peer, and no peer's load rises by more than 1 consult vs (a) [A41].

### 5.5 Queue ranking [H ch2 #6]
Lexicographic, every component shown as a reason, no weights:
1. Severity (Critical > Warning > Info)
2. In horizon before outlook
3. Ownerless (unassigned, or owner cannot act) before owned
4. Stroke before General Neuro
5. Repeat call before not
6. Patient wait since **first** contact, longest first (gap items: soonest start first)
7. Consults/hospitals affected, most first
8. Stable ID

Items sharing a root cause (e.g. a Suncrest surge, its unassigned consult, its at-risk gap, two leaving physicians' notes) are grouped under one **incident** with the top-ranked item as its headline, to limit alert overload [H ch7].

Each item exposes: `what`, `where {hospital, consult, physician}`, `why {age, limit, level, worsens_at}`, `fix {kind, approver, reason, alternatives_rejected[]}` [H ch4].

### 5.6 Rules tightened after running the sample (steps 3-6 implemented)
- **One item per consult or physician.** Findings about the same subject merge; the most severe level wins and the others are listed under `also`. Note-overdue items fold into the owner's shift-end notes item.
- **Unassigned severity follows the Triaged clock,** raised one level by a failed route or a repeat call. CON-2114 (2 min in triage, 1 failure) is Warning, not Critical.
- **A ringing unassigned consult** → coordinator calls the physician being rung before anything is escalated.
- **Handoff** prefers a routable physician who stays past the owner's end, then one who stays and can act once free (PHY-005 for CON-2112). Escalate only if nobody stays.
- **At-risk gaps group by the scheduled starter** they depend on (one watch item per starter, not one per hospital).
- **Gaps closed by the same offer merge** into one item, so there is one approval and one message.
- **Split-shift alternative text names the closest candidate and the rule it fails** (e.g. Okafor fails R6 for an immediate offer: 1.75 h after 15 min online).

Sample at 18:20: CON-2110 and CON-2105 escalate first; CON-2102 hands off to PHY-004; Suncrest watch relies on Cho, with Okafor the only eligible fallback; Northfield 20:00-22:00 → offer Okafor; Cedar Ridge 21:00 → escalate. At 19:10 with no `shift_started` for Cho, the watch becomes hard gaps and one Okafor offer covers SYN-004/005/008.

### 5.7 Aligned with the scenario packs (`test_data/01_development`, `test_data/02_validation_no_candidate`)
`expected/` is the answer key, never an input: state is built from `inputs/` + `live/judge_events.csv` and compared at 18:20, 18:40, 19:30 and 22:20 (`tests/test_pack.py`, parametrized per pack). The integration and holdout packs (03, 04) are held out.
- **Two reference layouts, chosen by header:** sample (`*_et`, ET hours) and pack (full timestamps, `*_local` hours in hospital time, weekday 0 = Monday, roster next shift with an end).
- **Current coverage is by signals** (on shift, credentialed, not busy); **the forecast is a schedule ceiling** that counts scheduled physicians regardless of status, including Temporarily Unavailable (replaces A37) and night starters from their start.
- **Replay:** an end with no open session (late start) advances the consult (CON-FA73B353C6F); `last_answered` counts incoming calls only; camera + In Meeting outranks Documentation.
- **Eligibility evaluates a proposal** (start, end, hospitals) with the answer key's rule keys, adding `off_shift_now`, `start_not_in_past` and splitting R6 into nominal and useful duration (after time to come online).
- **Current gaps:** with consults waiting → offer or escalate; with nobody waiting → watch (busy is transient).
- **One new consult per physician per pass** (assignments are reserved in rank order) and manual assignment prefers physicians not leaving within the hour [A47].
- **No automatic message to an off-shift physician:** their open notes go to the coordinator.
- **Offers for the same physician merge** into one window and hospital set only if the merged proposal still passes every rule.

### 5.8 Step 7: routing simulator, trap guard and metrics (implemented)
`decide/routing_sim.py` models the router [B p3]; it never replaces it.
- **Service time is measured, not invented:** median busy minutes per consult (incoming calls + video) from today's events (`observed_service`). Dev pack: 6.5 min; sample: 18.3 min. With no observations the trap check is not run and the offer says so.
- **Demand:** waiting unassigned consults at `now`, then baseline means placed where the expected count crosses each half-integer (deterministic). Second scenario: surging hospitals keep their trailing-60 rate. Missing baseline → that hospital's demand is reported unknown.
- **Physicians:** the forecast's supply (on shift + scheduled starters); Temporarily Unavailable stay out [A37]; a session in progress ends after one median service time [A48]; 2-minute cooldown after each call; no ring time.
- **Runs per scenario:** (a) no joiner, (b) joiner unrestricted and unseeded (the trap), (c) joiner restricted to the offer hospitals and seeded [A26, peers that are Temporarily Unavailable excluded from the seed].
- **Pass for (c):** joiner only at offer hospitals; patient wait minutes at the offer hospitals not worse than (a); joiner load ≤ busiest peer + 1; no peer +2 or more vs (a) [A41].
- Every split-shift item carries `why.trap_guard` (restriction, seed, verdict, wait minutes removed, unguarded spill) and the reason names the router setting. A failed check is shown to the lead, never hidden; the offer still needs approval.
- Dev pack 18:20: PHY-809 restricted to SYN-146/SYN-864, seed 17: wait at those hospitals 320 → 90 patient-min (no joiner → guarded); unguarded the joiner takes 6 consults at SYN-229/SYN-555, which the offer never named. Sample 18:20: the PHY-009 offer fails `joiner_not_above_busiest_peer` only under a sustained Suncrest surge (10 vs 8), shown as a warning.

**Decision rules changed by the clock sweep** (the sweep runs `decide` every 5 min 18:20-22:20 with live events):
- **Free soon, not absent:** when nobody credentialed is routable but one is in a call/video or the 2-minute cooldown, the consult is queued for them ("when their video consult ends", lead notified if Critical) instead of escalated [A49]. This removed most assign↔escalate flip-flops.
- **Incidents:** escalations for consults at the same hospital merge into one `escalate:<hospital>` item that lists every consult and its wait [H ch7]; open notes merge into one item per owner. 22:20 queue: 31 → 12 items, escalations 17 → 4.

**Metrics** (`tests/pack_metrics.py`; asserted in `tests/test_pack.py` and `tests/test_pack_sweep.py`, which run on all four packs; 03 and 04 were held out until the engine was finished and were scored blind, with no engine change: the two failures they exposed were both test bugs, fixed in the tests). A rules engine has no ML accuracy; we measure agreement with the answer key, scenario recall and decision properties:

| Metric | 01 development | 02 validation (no candidate) | 03 two candidates (blind) | 04 changed winner (blind) |
|---|---|---|---|---|
| Field agreement with expected/ (4 checkpoints, forecast, candidate rules) | 11,661/11,661 (100%) | 11,661/11,661 (100%) | 11,607/11,607 (100%) | 11,637/11,637 (100%) |
| Example offer | PHY-809 offered (answer key: the only eligible) | Escalated with every off-shift physician's failing rule (answer key: 0 eligible) | PHY-916 offered, PHY-435 shown as runner-up (answer key: both eligible, unranked); after PHY-916 accepts, PHY-435 is offered because the hospital still needs 2 | PHY-620 offered (answer key: the only eligible) |
| Scenario recall (HB01-HB06; HB05 negative control not flagged) | 6/6 | 6/6 | 6/6 | 6/6 |
| Safety/feasibility violations, 49 passes 18:20-22:20 | 0 | 0 | 0 | 0 |
| Critical items without an action | 0/579 | 0/597 | 0/587 | 0/591 |
| Offers passing the trap guard | 18/18 | no offers (nobody eligible) | 19/19 | 19/19 |
| Fix churn / flip-flops (two free physicians swapping places in the router's order) | 15/692 / 6 | 22/711 / 8 | 25/694 / 10 | 24/699 / 9 |
| Order invariance at checkpoints | 4/4 | 4/4 | 4/4 | 4/4 |
| Latency per pass (replay + decide) | median 5 ms, p95 28 ms | median 5 ms, p95 6 ms | median 5 ms, p95 30 ms | median 5 ms, p95 28 ms |

Not measured: whether following the advice improves outcomes over a whole evening. That needs a closed loop where our accepted actions feed back as events (the replay is open loop: nobody acts on our advice, so the same consults are re-decided every pass).

## 6. Act: offer state machine

```
PROPOSED ──approve──► APPROVED ──send──► SENT ──accept──► ACCEPTED
   │                    │                 ├─accept, gap already filled─► ALREADY_FILLED
   └─reject─► REJECTED  └─recheck fails─► CANCELLED ├─decline─► DECLINED
                                                    ├─now ≥ expires_at─► EXPIRED
                                                    └─gap closed otherwise─► WITHDRAWN
```

Approve and send happen in one command (as the API contract says), but each still re-runs its own checks.

### 6.1 Command rules (each command = one DB transaction)
1. Serialize through the same `MutationCoordinator` lock as ingest, so a command sees exactly one revision.
2. `SELECT … FOR UPDATE` the coverage case row, then the offer row.
3. Re-run R1-R8 and the gap check **from current state** at propose, approve and send. If the window changed but the physician still passes, keep going and record the change; if not, CANCELLED with the failing rule.
4. Write the transition, an audit row and (for send) a simulated-message outbox row; commit; then publish. TTS runs after commit and can never roll back a send.
5. Every command carries an `Idempotency-Key`; a repeat returns the stored response.
6. DB backstops: partial unique index on `offers(physician_id) WHERE state IN ('PROPOSED','APPROVED','SENT')` (R7), CHECK on legal transitions.

### 6.2 Acceptance (the atomic part)
Inside the accept transaction: re-project coverage with already-accepted joiners **plus this one**. If this joiner reduces any remaining hard-gap minutes at the offered hospitals → ACCEPTED, add the shift, re-run gaps, and WITHDRAW other open offers that no longer reduce anything. If not → ALREADY_FILLED and the physician is told "no longer needed" [A19]. "Remaining need" is derived from the projection, not a counter, so it cannot drift.

### 6.3 Timing
- `expires_at = sent_at + 10 min` on the injected clock, half-open: a reply at exactly `expires_at` is late [A42].
- Expiry is checked lazily on every read/command and materialized by `sweep()`. EXPIRED or DECLINED creates a PROPOSED offer for the next-ranked eligible candidate, which still needs the lead's approval [B p2].
- Sending policy: open SENT offers per hospital ≤ remaining hard need at that hospital (sequential when need is 1) [A18].
- Clock moved backwards (admin) below the latest offer transition: offer commands return 409 until the clock passes it again; terminal states never revert [A43].

### 6.4 Message content [B p4]
Typed template fields only: hospital names, start, end, hours, expiry, and a reason code from a fixed enum ("coverage gap at a hospital you are credentialed for"). No consult IDs, types, counts or patient data are passed into the template function. Withdrawal and "already filled" notices use the same template and are covered by the offer's original approval [A44].

### 6.5 Audit (append-only)
One row per transition and per decision pass that produced a recommendation: gap snapshot, every candidate with every rule result and value, chosen window, proposer, approver (display name from the lead's token), send time, reply and timestamp, late/duplicate/conflicting replies, final coverage after the transition, revision and `as_of`.

### 6.6 As built (step 8, `app/act/offers.py`, `tests/test_offers.py`)
- **One command = one transaction:** global advisory lock (`OFFER_LOCK`, serializes instances) → offer row `FOR UPDATE` → re-check from current state → transition + audit row + outbox row + idempotency record → commit. A failure anywhere rolls all of it back (`test_a_failure_mid_command_leaves_nothing_behind`).
- **A refused command still leaves a record:** the refusal's audit row (under the offer's gap) and its idempotency record commit, then the error is raised. Expiry found at reply time is materialized (EXPIRED + next candidate) before the late reply is refused.
- **Schema backstops:** partial unique index = one open offer per physician (R7); a trigger rejects any state change outside the transition table.
- **Need is derived, never counted:** `ops.coverage.remaining_need` (forecast hard shortfall with accepted joiners as supply, or with consults waiting the current shortfall less joiners due within the horizon). Propose requires need at every offered hospital (trap guard); later re-checks require need at any.
- **Parallel sends are allowed** (replaces A18): the lead approves each; the first committed acceptance wins; other open offers that no longer reduce any need are WITHDRAWN (SENT, with a "no longer needed" notice) or CANCELLED (PROPOSED/APPROVED). A later reply to a withdrawn offer gets 409 `already_filled`; an acceptance that finds no need left becomes ALREADY_FILLED.
- **Late approval** moves the start to `now` and re-checks R6 on what is left; the move is in the audit row.
- **Next candidate** after decline/expiry: best eligible physician not yet asked for this gap, for the hospitals that still need help, PROPOSED by `system` (lead approval still required). None left → audit `next_candidate:none` (the queue shows the escalation).
- **Feedback:** `desk.accepted()` and `desk.history(now)` go into `decide()`; `decide()` also folds accepted shifts into R4/R5 itself, and accepted joiners close current gaps.
- **Physician isolation:** another physician's offer returns 404, same as a missing one.
- Pack check (`test_engine_offer_runs_end_to_end_through_the_desk`): dev pack, the engine's own PHY-809 offer goes propose → send → accept and SYN-146 stops being short (SYN-864 still escalates: the surge needs one more); validation pack, every off-shift physician is refused (422) for the example gap.

## 7. Edge cases and expected behavior

| Case | Expected behavior | Test |
|---|---|---|
| Two accepts within 1 minute, need 1 | First committed wins; second ALREADY_FILLED, logged | `test_double_accept` |
| Accept after expiry | Rejected as late, offer stays EXPIRED, logged; next candidate unaffected | `test_late_reply` |
| Accept then decline (or reverse) | First response wins; second 409, logged | `test_conflicting_replies` |
| Same reply twice | Idempotent, same response | `test_idempotent_reply` |
| No reply | EXPIRED at 10 min; next candidate PROPOSED | `test_timeout_then_next` |
| Decline | Next candidate PROPOSED (needs approval) | `test_decline_then_next` |
| Lead rejects | REJECTED with reason; item returns to coordinator with next candidate shown | `test_reject` |
| Gap closes by other means (TU physician returns, new shift_started) | Open offers WITHDRAWN, PROPOSED/APPROVED CANCELLED | `test_gap_filled_elsewhere` |
| Physician becomes ineligible between approve and send (new offer, references change) | CANCELLED with failing rule | `test_ineligible_at_send` |
| Weekly cap reached | R8 fail with count | `test_weekly_cap` |
| Nobody eligible | Escalation item with the full table; no offer | `test_nobody_eligible` |
| Exactly one eligible, others fail one rule each | That one ranked first; each other shows its single failing rule | `test_sample_candidates` |
| Rest boundary exactly 10 h | Pass (`>=`) | `test_r3_boundary` |
| Hours exactly 60 | Pass (`<=`) | `test_r4_boundary` |
| Offer ends exactly at next shift start | No overlap (half-open) | `test_r5_adjacent` |
| Online time pushes net below 2 h | R6 fail with net hours | `test_r6_online_cost` |
| Trailing count equal to p90 | No surge | `test_surge_equal` |
| Two hospitals surging at once | Both raise requirement independently | `test_multi_surge` |
| Repeat call on same consult | Not new demand (surge count unchanged), wait from first contact, ranks above an equal non-repeat | `test_repeat_call` |
| Two consults at one hospital | Never merged; both counted | `test_distinct_consults` |
| Late event moves a consult's stage back in time | Timer recomputed from event time | covered by P2 + `test_timer_late_event` |
| Surge expires inside the horizon | Requirement drops at `received_at + 60` | `test_surge_expiry` |
| Block boundary crossing midnight (22:00-07:00) | Correct block chosen | `test_block_midnight` |
| DST or other date | No date/ID assumptions; runs on 2026-04-07 / 2026-11-02 synthetic | `test_other_dates` |
| Missing baseline or coverage row | Data-quality finding; surge/gap "unknown", never 0 | `test_missing_refs` |
| References reloaded (credentials or shifts change) | Next pass uses new revision; open offers re-checked at next command and on sweep | `test_reference_change` |
| Joiner restricted + seeded | Routes only at gap hospitals; peers within tolerance | `test_trap_guard` |
| Joiner unrestricted + unseeded | Simulator shows flooding across hospitals (the trap) | `test_trap_unguarded` |
| Live append (prefix then suffix) | Same decisions as full replay | `test_live_append_decisions` |
| Shuffled arrival order | Identical decisions | `test_order_invariance` |
| Same file ingested twice | Identical decisions | `test_idempotent_ingest` |

## 8. Build plan (each step is one PR with its own tests)

| Step | Deliverable | Verify |
|---|---|---|
| 1 | `ops/refs.py`: baseline, coverage, roster details, scheduled starts | Loader tests incl. missing rows, midnight block, other dates |
| 2 | Replay additions: `routing_failures`, `last_routing_failure_at`, `repeat_contacts` | Existing 57 tests + new repeat-call and failure-count tests |
| 3 | `ops/detect.py`: G9, G10, G11, G14 with what/where/why | Sample at 18:20: CON-2105, CON-2110, CON-2102, CON-2112, PHY-003/006 notes; boundary tests |
| 4 | `ops/coverage.py`: surge, timeline, hard/at-risk gaps | Sample: Suncrest surge to 19:04:30; Northfield hard 20:00-22:00; equality and multi-surge synthetic |
| 5 | `decide/eligibility.py`: windows, R1-R8, ranking | Sample table (F7), boundary tests per rule, nobody-eligible case (Cedar Ridge 21:00) |
| 6 | `decide/interventions.py` + `rank.py`: fix choice, alternatives, incidents, queue | Top item at 18:20 with plain reason; order invariance |
| 7 ✅ | `decide/routing_sim.py`: three runs and pass criteria; clock sweep and metrics | Trap shown unguarded, contained guarded; `test_routing_sim.py`, `test_pack_sweep.py` |
| 8 ✅ | `act/offers.py` + schema: state machine, commands, sweep, audit | `test_offers.py` (all section 7 flow cases, atomicity, concurrency) |
| 9 ✅ | Wire into snapshot and API contract (every endpoint in 00-Boundaries, auth and RBAC, WebSocket, sweep, ElevenLabs) | `test_api.py`: live append equals full replay at every checkpoint on both packs; re-ingest changes no decision; roles; offer loop over HTTP |
| 10 | Generator-driven property tests (Krish's synthetic data): assert behavior, not IDs | Runs on two practice datasets |

Steps 1-7 are pure functions and can be tested without the database. Step 8 needs Postgres.

## 9. Assumptions

| ID | Assumption | Why |
|---|---|---|
| A7 | Day/night threshold for on-shift physicians: shift starting 17:00 ET or later is night; joiner uses the day threshold for seeding | On-shift file has no role (F12) |
| A9 | A physician leaves coverage exactly at shift end | Half-open intervals |
| A12 | Simulated demand uses baseline mean, placed deterministically | No randomness in decisions |
| A16 | Prior offers this week = 0 unless our offer log has some; shown explicitly | No offer history supplied |
| A18 | ~~Open sent offers per hospital ≤ remaining need~~ Replaced in 6.6: parallel sends, first committed acceptance wins, the rest withdrawn | Handbook expects two doctors accepting the same need; sequential sends would also slow every fill by a full reply window |
| A19 | First committed acceptance wins | Single serialized writer makes this exact |
| A24b | Busy does not remove staffing coverage; TU does | Busy is transient, handled per consult |
| A26 | Joiner seed = max(threshold + 1, min peer count at gap hospitals) | Rule 3 still floods a joiner below threshold |
| A30 | p90 = 0 → any consult is a surge | Strict `>` |
| A32 | Repeat call = each extra `consult_received` for the same `consult_id` (`repeat_contacts`). A first `incoming_call_ringing` is the original call reaching a physician (CON-2109), not a repeat | No example in the data (F10) |
| A33 | Reassignment does not restart the Assigned timer | Patient keeps waiting |
| A34 | Level reached at the limit (`>=`) | Brief lists limits, not "more than" |
| A35 | Untriaged consults have no standard; info after 5 min | Brief has no Received standard |
| A36 | Ring unanswered for 2 min → warning | No standard given |
| A37 | TU physicians stay TU through the horizon | No return time in the data |
| A38 | Scheduled starter is late if no `shift_started` by start + 5 min | Matches routing retry cadence |
| A39 | Offer covering < 60 gap minutes is "low value" (still eligible) | Informs the lead without bending R6 |
| A40 | Simulator service time = today's median busy minutes per consult (incoming calls + video); waiting consults use their type's median, simulated arrivals the overall median | Derived from the data, not invented |
| A41 | Trap tolerance: no peer gains more than 1 consult, and the joiner carries at most 1 more than the busiest peer | Counts are discrete; one consult is tie-order noise |
| A42 | Reply at exactly `expires_at` is late | Half-open window |
| A43 | Offer commands refuse a rewound clock | Keeps the audit monotone |
| A44 | Withdrawal/"already filled" notices are covered by the offer's approval | They respond to an approved offer |
| A48 | In the simulator a session in progress at `now` ends after one median service time | Start times of sessions are known, durations are not |
| A49 | A physician in a call, video or the 2-minute cooldown is free soon: queue the consult for them; escalate only when nobody credentialed is free or free soon | Escalating every short session flip-flopped the advice every pass |

## 10. Decisions taken

1. **Scheduled night starters count as "scheduled" capacity** from `next_shift_start`. A gap they close is at-risk, not hard, and turns hard if no `shift_started` arrives by start + 5 min (A38). [A45]
2. **The clock runs in real time during the demo.** Offer expiry, breach countdowns and late-starter checks all use the injected clock and `sweep()`; nothing assumes a fixed 18:20. [A46]
3. **Act (offer loop) is core for the decision engine,** because the brief requires all three layers [B p1].
