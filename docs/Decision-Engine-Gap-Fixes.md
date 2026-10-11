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

The new CI jobs have been verified locally in the stated environments. Their
GitHub execution requires committing/pushing this cohort; the public clean
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
single-site scenario; it does not settle the separate A41 policy question. The
peer-load criterion still applies to every scenario. Pack agreement and local
tests do not establish clinical outcomes or deployed performance.

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

Backend/web changes are in the existing `rishi` working tree. Mobile changes are
in the attached managed checkout based on `origin/mobile`:
`/Users/rishi/.codex/worktrees/mobile-api-compatibility/Health Hack`. Its older
backend files were not merged into the decision-engine checkout. Review the
`mobile/` changes there alongside the backend changes here. The mobile README
documents the adapter and repeatable contract-fixture update procedure.

Changes remain uncommitted and unpushed. The broader review's items 11–18 remain
pending. No service was deployed or physical phone build tested.
