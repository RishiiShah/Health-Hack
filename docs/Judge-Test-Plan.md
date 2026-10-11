# Judge test plan: what the judges provide and how we pass

Current implementation, policy differences and historical document labels are
indexed in [document authority](README.md). Protected-pack results are local
verification; clean CI uses synthetic API worlds and generated replay fixtures.
The approved G15 policy is severity-first lexicographic ordering with an ordinal
score. A41 compares joiner load with peers under baseline demand only; every
scenario retains site, wait and peer-harm constraints.

## What the judges will do (handbook Chapter 4, brief "What Teams Must Demonstrate" #8)
- **One CSV** in exactly the `event_stream.csv` format: `event_id, event_time, ingested_at, consult_id, event_type, physician_id, hospital_id, description`.
- Same doctors, hospitals and kinds of events as the kit; **new records that move the day forward** (who is free, what is stuck, what to do next). Example given: another stroke consult at the surging hospital.
- We **drop it into the running tool**; it must be appended to the day already loaded, with **no restart**, and the engine must find the problems and fixes on its own.
- "The data you're tested on won't be the data you practiced on": expect different wording, times and winners. The held-out packs we were not allowed to open are named `03_integration_two_candidates` and `04_holdout_changed_winner`, so expect two eligible physicians and a different eligible winner.
- They also score the eight demonstrations: rebuild the 18:20 snapshot (late and duplicate events), physician activity and consult lifecycle shown separately, ranked attention list with reasons, 90-minute forecast, a recommended fix with every off-shift physician's rule results, the full offer loop, the split-shift trap, and the live update.

## Rehearsed and verified (automated tests)
| Judge action | What happens | Test |
|---|---|---|
| Base kit loaded at 18:20 (`data/`, sample layout) | 1,163 accepted, 1 duplicate, 23 reordered, 1 late, 0 rejected | `test_judge_file_on_the_original_kit_updates_without_restart` |
| Judge CSV dropped in (Data page or `POST /events/csv`) | Appended without restart; new wording ("Acute stroke consult requested") read by keyword; duplicate row ignored; repeat call is the same patient (first clock kept, surge count unchanged); new consult ranked Critical with a fix | same |
| Judge events dated after the clock | Reported as `pending_future`; `?advance_clock=true` advances to the latest newly accepted event within 24 hours; larger jumps remain pending with a date-review warning | same |
| Live append, clock moving | Served queue equals a full replay at 18:20, 18:40, 19:30 and 22:20 on both allowed packs | `test_live_append_matches_a_full_replay_at_every_checkpoint` |
| Same file uploaded twice | No decision changes | `test_ingesting_the_same_file_twice_changes_no_decision` |
| Nobody eligible | Escalation with every off-shift physician's failing rule; no offer | validation pack tests |
| Two eligible physicians / changed winner | Ranked by covered gap minutes → minutes to online → declines → 7-day hours → offers this week → ID; each input flips the winner; runner-up shown | `test_two_eligible_candidates_rank_by_the_stated_order_and_the_winner_changes_with_the_data` |
| Two doctors accept within a minute | First committed wins, the other is told "already filled" | `test_double_accept…`, `test_concurrent_commands_from_two_instances_serialize` |
| Full loop through the web UI | Coordinator proposes → lead approves/sends → physician accepts and awaits observed arrival → arrival enables routing; schedule and audit update | `web/scripts/workflows.e2e.cjs`, official-kit disposable localhost run on 2026-10-11 |
| Judge file through the web | `make backend` stack + Joy's Data page: base kit 1,163/1/23/1; pasted judge CSV accepted 3, duplicate 1, clock moved to 18:30, Suncrest surge 6 | manual run on 2026-10-10 |
| Development pack through computer use and Playwright | File chooser loads 1,709 base events; judge CSV adds 124 and drops 1 duplicate; all 1,709 original events and 147 original consults retained; 16 new consults; unchanged six references; queue matches full replay and contains the new consults in grouped Critical escalations. Repeat upload adds 0 and drops 125 duplicates. | Local isolated browser run on 2026-10-11; production untouched |

The fixed-reference audit also rehearsed the official kit through actual file uploads: 1,163 base events plus 3 accepted unseen events, an unchanged reference fingerprint, Critical CON-J01, retained original history and full replay parity. The development pack's incompatible IDs are held rather than replacing the official references. See [audit and regression instructions](CSV-Ingestion-Audit.md).

## Demo-day run sheet
1. `make backend`: it mounts `data/` as `CC_DATA_DIR` and reads the root `.env` (from `.env.example`: service date 2026-03-17, fixed clock at 18:20, ElevenLabs key). Then `cd web && npm ci && npm run dev`.
2. Load the base day: Data page upload of `data/event_stream.csv` (or `POST /events/csv`). Check the data-quality panel shows 1 duplicate, 23 reordered, 1 late, 0 rejected.
3. Walk the eight demonstrations at 18:20.
4. Judges' file: upload it on the Data page; a CSV upload advances to its latest newly accepted event within 24 hours (`/events/csv?advance_clock=true`, never backwards) and the report says where the clock moved. Never restart the server.
   Larger date jumps require review and explicit clock control. Data → Upload history retains receipts and per-row results across navigation/restarts; download a report for all rows. See [CSV audit](CSV-Ingestion-Audit.md).
   The upload appends to the existing event history and recalculates decisions on the combined state; reference names, counts and hashes remain unchanged. The Data page separates reference data from event-stream checks. Presentation demo mode disables event testing because its fixed examples do not run the decision engine; use the live backend for unseen CSVs.
5. For an independent rehearsal, Data → Start empty stream (`POST /admin/reset`) starts a clean generation with the same references and clears current consults, offers and interventions; it does not restore the original event file. The old event generation stays in the database.
6. Hosted: the image has no reference CSVs. Production RDS already stores the complete six-file reference kit; connect the backend to that database and verify with `python3 scripts/upload_references.py data --url https://<host> --service-date 2026-03-17 --check`. For a different database, upload first. The database keeps references across restarts; see [Reference Data](Reference-Data.md).

## Current delivery and remaining rehearsal

The latest [E2E audit and handoffs](E2E-Audit-2026-10-11.md) adds reproducible
official-kit browser fixtures, attendance/accessible-label regressions, fixed
hosting probes, truthful prototype copy and a real process-replacement check.
383 backend, 58 web and 149 mobile tests passed; web/Flutter builds and analysis
passed. Hosted and physical-device checks remain pending.

- Web Detect components exist and display server queue, consults, physician state and findings. Snapshot polling is serialized, aborts on cleanup and coalesces manual refreshes. No current web transport depends on the unproxied `/ws` route.
- Web schedule now has a backend route and a matching Vite proxy. Offer audio is fetched with bearer authentication, played through a temporary blob URL and released on completion, stop or navigation. Playback failures are visible; the physician's own offers screen includes playback. The server still restricts offer audio to lead/own physician. Automatic once-per-critical-item announcements remain a planned feature; `VoiceAlerts` supports manual playback and is not mounted on the current command page.
- Mobile live mode uses `BackendApiClient` for supported existing backend routes and DTOs. Broadcasts, mobile schedule/preferences/release remain outside the agreed live integration. Fake/design workflow tests do not establish those production capabilities.
- Backend, web and mobile source now share this checkout. CI builds/tests the public synthetic worlds; protected scenario packs remain uncommitted and require a separate local run. The standard-library `scripts/synth` generator now supplies five independent rehearsal datasets; CI verifies authored snapshots against backend replay. See `scripts/synth/README.md`.
- Render deployment, cross-origin gateway configuration, physical-device checks and real speech-provider playback remain separate rehearsal work. The synthetic audio tests validate auth and lifecycle without invoking ElevenLabs or claiming production audio quality.
