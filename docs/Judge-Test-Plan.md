# Judge test plan: what the judges provide and how we pass

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
| Judge events dated after the clock | Reported as `pending_future`; `?advance_clock=true` moves the clock to the file's latest event so all of it is visible at once | same |
| Live append, clock moving | Served queue equals a full replay at 18:20, 18:40, 19:30 and 22:20 on both allowed packs | `test_live_append_matches_a_full_replay_at_every_checkpoint` |
| Same file uploaded twice | No decision changes | `test_ingesting_the_same_file_twice_changes_no_decision` |
| Nobody eligible | Escalation with every off-shift physician's failing rule; no offer | validation pack tests |
| Two eligible physicians / changed winner | Ranked by covered gap minutes → minutes to online → declines → 7-day hours → offers this week → ID; each input flips the winner; runner-up shown | `test_two_eligible_candidates_rank_by_the_stated_order_and_the_winner_changes_with_the_data` |
| Two doctors accept within a minute | First committed wins, the other is told "already filled" | `test_double_accept…`, `test_concurrent_commands_from_two_instances_serialize` |
| Full loop through the web UI | Coordinator proposes → lead approves and sends → physician accepts; grid, tracker and audit update | manual run on 2026-10-10 (backend + Joy's web, development pack) |
| Judge file through the web | `make backend` stack + Joy's Data page: base kit 1,163/1/23/1; pasted judge CSV accepted 3, duplicate 1, clock moved to 18:30, Suncrest surge 6 | manual run on 2026-10-10 |

## Demo-day run sheet
1. `make backend`: it mounts `data/` as `CC_DATA_DIR` and reads the root `.env` (from `.env.example`: service date 2026-03-17, fixed clock at 18:20, ElevenLabs key). Then `cd web && npm ci && npm run dev`.
2. Load the base day: Data page upload of `data/event_stream.csv` (or `POST /events/csv`). Check the data-quality panel shows 1 duplicate, 23 reordered, 1 late, 0 rejected.
3. Walk the eight demonstrations at 18:20.
4. Judges' file: upload it on the Data page; a CSV upload moves the clock to its latest event (`/events/csv?advance_clock=true`, never backwards) and the report says where the clock moved. Never restart the server.
5. If something looks wrong, `POST /admin/reset` starts a clean generation (the old one stays in the database).
6. Hosted: the image has no reference CSVs. Before the demo run `python3 scripts/upload_references.py data --url https://<host> --service-date 2026-03-17` once; the database keeps them across restarts.

## Open items for teammates
- **Web Detect screens (Anish):** `web/src/detect/` does not exist, so the web has no attention queue, consult board, physician board, stuck-consult panel, signal flags or voice alerts (demonstrations 2–3). The backend serves all of it in `/snapshot` (`queue`, `consults`, `physicians`).
- **Web dev proxy** does not forward `/ws`; the app polls `/snapshot` every 2 s, which is fine.
- Fixed: the Data page uploads with `advance_clock=true`; TypeScript is pinned to 5.9.3 so `npm ci` installs cleanly (7.0.2 conflicted with `openapi-typescript`).
- **Mobile (Hitanshu/Chandan):** calls `/lead/queue`, `/lead/offers` and `/notifications`, which the backend does not serve; not checked against the backend yet.
