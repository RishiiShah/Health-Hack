# Decision-engine review: completed cohorts and delivery gaps

Completed in order after the repository, problem statement, handbook and branch
review. The backend remains a deterministic rules engine. No AI/ML model,
provider dependency, source-data edit or change to the trap acceptance policy was
introduced.

| Item | Cause | Implemented correction | Evidence |
| --- | --- | --- | --- |
| 1. Accepted joiners remained off shift in routing | Forecast supply used accepted windows while operational physician views used only the original schedule | Activate an effective shift after observed arrival, within the offered window and hospital restrictions. Use actual assignments/calls, respect cooldown and shift end, and count the physician once | `backend/tests/test_accepted_routing.py`, `backend/tests/test_offers.py` |
| 2. Simulator ignored existing rings/cooldown | Its initial free time used signal-busy state, losing other routing exclusions | Carry a known call's remaining cooldown. Reserve one median session plus cooldown for an unresolved ring, explicitly documented as A53 | `backend/tests/test_routing_sim.py`, four-pack sweep |
| 3. Clock overrides disappeared on restart | Admin/CSV changes replaced only the in-memory clock | Commit the override before publishing. Restore fixed time exactly; running clocks include elapsed receipt time and downtime. Saved metadata overrides environment defaults | `backend/tests/test_clock_recovery.py` |
| 4. Web build depended on missing demo JSON | Seven imports referred to files absent from the checkout | Add hand-authored synthetic presentation fixtures and label them as UI examples. Add web tests/build to CI | Source-only copy, locked `npm ci`, 33 tests and production build |
| 5. Mobile assumed another API contract | Routes, role names, payloads, action outcomes and clock behavior differed | Adapt existing backend workflows on the mobile side; add authoritative workflow/time metadata to existing backend responses. Preserve server permissions and decisions | Synthetic responses captured by `backend/tests/test_mobile_contract.py`, mobile adapter/auth/widget tests |
| 6. G8b overload was absent | Workload hardcoded a null classification | Apply configured open-work/rate thresholds, observed peer windows and explicit unavailable comparisons. Share evidence across queue, workload and headline | `test_overload.py`; official kit matches T28 |
| 7. Display horizon missed the final cliff | Grid, flags and headline used a fixed 90 minutes | Share a horizon through the last shift boundary within 120 minutes; include exact boundaries and endpoint. Keep supply-changing intervals separate | `test_forecast_schedule.py`; official kit reaches 20:00 |
| 8. Audit lacked historical decision evidence | Only narrow transition details were stored | Save all candidate rules, prior coverage and post-transition coverage atomically. Record and deduplicate recommendation passes; expose stored structured evidence | `test_offers.py`, `test_forecast_schedule.py`, full HTTP offer loop |
| 9. Live Schedule requested a missing route | Backend had no `/schedule` contract | Serve the existing web shape from references, accepted shifts, operational views and pending offers. Expose incomplete ends and actual service date; poll for updates | Synthetic schedule/API tests; web tests/build |
| 10. My Shift stayed stale while mounted | Its request ran only on mount | Poll the physician-only endpoint after each request settles, cancel on cleanup and retry failures while keeping the last response | `web/src/act/poll.test.ts`; real browser stayed on `#shift` while acceptance/arrival/assignment updated it |

The requested local reference load is also complete. The six official CSVs are
persisted in PostgreSQL on port 8010 and verified by a SHA-256 manifest, with
12 hospitals, 14 physicians and the existing 1,166 events retained. The repeatable
upload/check commands for localhost and future Render hosting are in
[Persistent reference data](Reference-Data.md). A matching script upload performs
no write. The subsequent production load stored the same six CSVs in the
configured AWS RDS **commandcenter** database, retaining all **1,163** existing
events and other operational state. An independent reconnect rebuilt and
verified the normalized and operational references. No Render service was
deployed or populated.

## Third cohort: items 11–15

Checkpoint **ba9d597** (`Fix decision workflows and persist reference data`)
committed the first two cohorts and production reference documentation, and was
pushed to `origin/rishi` before this cohort started. The personal local handoff,
source CSVs, environments, databases and secrets were excluded.

| Item | Cause | Correction/status | Evidence |
| --- | --- | --- | --- |
| 11. Snapshot responses could arrive out of order | Overlapping interval requests applied every result, including after cleanup | Serialize requests, queue/coalesce manual refreshes, discard the pre-refresh result, abort cleanup and ignore old generations. Accept new epochs/lower revisions and clock-only updates. Own-offer polling also serializes and honors paused clocks | `web/src/act/poll.test.ts`; web tests/build |
| 12. Native audio requests omitted bearer auth | `new Audio(protectedUrl)` bypassed the authenticated fetch wrapper | Fetch an authenticated binary response, play a temporary blob URL, stop/abort on cleanup and revoke on end/failure. Show server and browser errors. Own-physician playback is wired; unauthorized coordinator offer controls are hidden | `client.test.ts`, `audio.test.ts`; native browser played a silent synthetic WAV, verified auth and released the URL; visible 503 checked at desktop and 390px |
| 13. CI omitted public HTTP/client coverage | Module-wide private-pack skip and no mobile job | Scope skips to actual pack-dependent cases; add synthetic login/permissions/WS/live CSV/audio/reset/recovery checks. Add pinned Flutter analysis/tests/live and fake web builds; web checks already run | Full local backend **337 passed**; source-only backend **169 passed, 36 skipped**; source-only web **44 passed** and build; integrated mobile **149 passed**, clean analysis and both builds |
| 14. Planning docs looked like current contracts | Historical SQLite/scaffold statements, stale auth precedence and contradictory scoring/scope claims | Add a document authority index; label historical and owner planning docs; reconcile password auth, account precedence, PostgreSQL, RDS status, dependencies, scope and judge plan. Explicitly retain the G15 weighted-versus-lexicographic policy difference | `docs/README.md`, PRD status, boundaries, backend/mobile READMEs and judge plan; no algorithm policy changed |
| 15. Mobile deliverables were absent from the release checkout | Component source and adapter lived on a separate branch/worktree | Integrate **141** mobile/contract/test files from `origin/mobile@35cc674` plus the verified adapter, without copying old backend/web code. Add the missing `/schedule` Vite proxy and portable build instructions. **Partial delivery gap remains:** `scripts/synth` is absent from every fetched remote branch and is labeled undelivered | Integrated source builds/tests and shared synthetic fixture equality; private data remains excluded. Hosted application/device rehearsal is not claimed |

This cohort changes client correctness, public verification and documentation,
not routing rules, objective weights, capacities or stable tie-breakers. The
undelivered generator is not replaced by a claim that manual synthetic fixtures
provide every planned generator dataset. The G15 policy discrepancy, A41 surge
criterion and fallback-reservation policy remain explicit decisions.

The third cohort was committed and pushed as **e343a30**. The new CI jobs were
verified locally in the stated environments; the public clean
checkout intentionally cannot run the protected source/pack checks. Real
ElevenLabs playback, native devices, cross-origin hosting and Render deployment
remain separate checks.

## Verification of cohorts 1–10

- Python 3.14.7: **335 backend tests passed**, including all four local packs.
- Four-pack five-minute sweep: field agreement **100%**, scenario recall **6/6**
  in each pack, **zero safety violations**, **zero critical items without an
  action**, and unchanged passing traps, changed-fix/flip counts and ordering
  checks. Critical and persisting-item denominators changed with the new findings
  and horizon. Measurements and
  simulator assumptions are in [Decision Engine](Decision-Engine.md).
- Web: **36 tests passed** and the production build succeeded. The first cohort
  also verified a source-only copy with dependencies installed from the lockfile.
- Mobile: **149 tests passed**, static analysis clean, and a Flutter web release
  build in `API_MODE=live` succeeded using the previously documented Flutter
  3.35.3 / Dart 3.9.2 toolchain. No dependency or lockfile change was retained.
- The backend test asserts its current synthetic API responses equal
  `backend/tests/fixtures/mobile_backend.json`. The mobile tests use the identical
  `mobile/test/fixtures/backend_workflows.json` bundle. These are test-created
  fictional records, with no challenge CSVs, answer keys or credentials.

The current official-kit API check at 18:20 passes for the engine's selected
bundle (SYN-005/SYN-008/SYN-010, seed 12). This differs from the original handoff's
single-site scenario. A41 was subsequently resolved by explicit user choice in
the fourth cohort below. Pack agreement and local tests do not establish
clinical outcomes or deployed performance.

## Mobile scope and checkout

The user selected compatibility with **existing backend workflows**. Supported
flows include own shift and consults, offers and replies, lead approvals and
rejections, candidates, trap checks, audit, escalation authorization, coverage
and response activity. A proposal is one server-selected recipient with sequential
fallback. The adapter does not synthesize a broadcast or make eligibility/ranking
decisions. A cancelled approval displays the server's cancellation and reason.
Retryable offer/approval writes use stable idempotency keys; business conflicts
reload authoritative state. Paused server clocks stay paused on the device.

Schedule views, preference editing and release are outside this scope. They show
an explicit capability message or a disabled/absent control. Unknown staffing and
rank fields remain unknown; missing trap evidence never becomes a passing verdict.
Offer activity is derived from sent records, without stored read receipts.

Mobile source and the adapter are now integrated in the main `rishi` checkout.
The original managed mobile worktree is preserved; its older backend/web files
were not merged. Checkpoint **e343a30** includes the verified mobile delivery.

## Fourth cohort: generator and approved policies

- **15 completed:** `scripts/synth` now supplies all five rehearsal datasets,
  eleven operational scenarios, all 20 event types, independently authored
  snapshots, DST, live append, one eligible roster candidate plus each R1–R8
  rejection, and 10×/100× replay volume. Generated CSVs remain ignored.
  The sample-format roster history extensions are explicitly backed by
  `support/offer_history.csv`. See [generator instructions](../scripts/synth/README.md).
- **16 completed:** queue titles show consult IDs first plus hospital names,
  combined gap names and physician names, including off-shift physicians.
  Advice and alternatives resolve whole known IDs to names; unknown IDs and
  action payloads remain intact. Watch rows say Watch; current gaps say No
  consult waiting. Watch dossiers show What to watch and do not promote a
  Find cover action. Duplicate explanatory phrases are displayed once.
  Server item IDs, severity, order and ranks are preserved.
- **17 resolved:** Rishi approved the joiner-versus-busiest-peer bound under
  baseline demand only. Site restrictions, non-worsening gap wait and the
  +1 peer tolerance still apply to every modeled demand scenario. A regression
  exercises concentrated legitimate surge load above the busiest peer.
- **18 resolved:** Rishi chose fallbacks as unreserved alternatives. Primary
  reservations remain; the server explains that a coordinator must choose one
  assignment and refresh before acting on another recommendation. A regression
  checks that a fallback may also be another item's primary.
- **G15 reconciled:** Rishi approved lexicographic priority with severity first.
  The PRD and implementation specification now share the complete stable key;
  former weighted numeric examples are superseded. Display scores are ordinal.
  No measured latency improvement or global optimality is claimed.

Fourth-cohort verification: **348 backend tests passed**, including all four
local packs; **45 web tests passed** and the production build passed;
**9 generator tests passed** locally. A source-only checkout passed **180 backend
tests**, explicitly skipping **36** protected-data cases; its generator run
passed **8** checks and skipped the private-source header comparison. Final
append/scaled snapshot regressions also pass in that checkout. Native browser
checks verified names and watch controls at desktop and 390×844, with no
horizontal page overflow. The mobile source/contract bundle is unchanged from
the **149-test** checkpoint. GitHub execution of the new generator stage is
separate from these local results.

Production reference data was not changed. No Render service was deployed or physical-device/real speech
rehearsal performed; those are the remaining hosting and demonstration tasks.

## Devil's advocate review fixes

The six confirmed adherence gaps are corrected:

1. R3 uses the latest known preceding end from roster, scheduled and accepted shifts. Active accepted shifts also prevent an off-shift offer; future obligations still receive overlap checks.
2. Physician offer lists, detail and media hide every unsent proposal, rejection and cancellation. Operations can review them; physicians retain access to their own sent offers and outcomes.
3. Camera evidence requires an online agent. Heartbeat loss restores available/unverified classification while real Synapse sessions, TU status, rings and cooldowns still exclude routing.
4. Acceptance rechecks eligibility at the reply clock, including two useful hours after expected readiness. An invalid reply is audited and returns 409 without adding coverage; normal expiry remains. An already-sent offer counts once toward the weekly cap.
5. Missing hourly demand in any scenario makes the full trap verdict unknown. API and queue evidence identify missing hospitals; web labels Unknown and mobile shows the missing-evidence reason. Partial simulations remain inspectable.
6. The web form uses the candidate's evaluated window and hospital set. Minute rounding preserves duration; separate endpoint dates preserve overnight windows. Selecting a different candidate resets the form, and the server validates edits.

Focused regressions cover the reported failures, ten-hour and two-hour boundaries, the third weekly offer, sent outcomes, camera recovery, partial-hour demand, and midnight rollover. The shared synthetic backend/mobile contract fixtures were updated together. No dependency, optimization policy, capacity or tie-breaker changes were needed.

Verification: Python 3.14.7 **410 backend tests passed**, including local pack checks; **62 web tests passed** and the production build succeeded; **149 mobile tests passed** and static analysis was clean. The updated mobile adapter's eight tests also passed against the final identical contract fixtures. These are local results; hosted and physical-device validation remain separate.
