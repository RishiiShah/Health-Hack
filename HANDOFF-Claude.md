# Claude handoff — Sevaro Command Center

Updated October 11, 2026 (~03:30 ET). Repository: `/Users/rishi/Desktop/CLG/Health Hack`, branch `rishi`.
Last commit `0de252a` ("Fix six problem-statement adherence gaps") is pushed to `origin/rishi`. **Everything below under
"Uncommitted work" is not committed.** Commit or push only when the user asks. `HANDOFF-codex.md` is older and superseded.

## Start here

Read `AGENTS.md`, `CLAUDE.md`, `docs/README.md`, then as needed:

- Challenge: `problem/Sevaro_Rutgers_Health_Hack_Challenge_2_Operations_Command_Center.pdf` and `Handbook/`.
- Requirements and gates: `docs/Sevaro Command Center PRD v2.md`. Rules, assumptions, tie-breakers: `docs/Decision-Engine.md`.
- API and roles: `docs/00-Boundaries-and-Contracts.md`. Reference kits and uploads: `docs/Reference-Data.md`.
  Hosting: `docs/Deployment.md`.

Built scope: deterministic Detect–Decide–Act loop. Backend Python 3.14.7 / FastAPI / PostgreSQL with injected clocks
and deterministic replay; web React/Vite/TypeScript; Flutter mobile. Clients only display server decisions.

## Policies to preserve

- G15 lexicographic priority: severity, horizon, ownerless, stroke, repeat contact, age, affected count, stable ID.
- A41 joiner-vs-busiest-peer load bound applies to baseline demand only; hospital restriction, non-worsening gap wait
  and peer tolerance apply to every scenario. (The old "trap check failed: surge_continues" issue is already fixed.)
- Fallback physicians are unreserved alternatives; primary recommendations keep reservations.
- The six fixes in `0de252a` (rest after accepted shifts, unsent-offer disclosure, stale offline camera, late-acceptance
  recheck, incomplete trap demand, offer window). Details in `docs/Decision-Engine-Gap-Fixes.md`.
- No AI/ML in decisions; stdlib first; never edit `web/src/api/types.gen.ts` or `data/*.csv`; never commit `data/`,
  `test_data/`, `.env`, databases or secrets.

## Key facts learned this session

- **Judges upload only an events CSV** (handbook ch. 4, PRD lines ~30 and ~386): same 8 columns, same doctors and
  hospitals as the official kit, appended without restart.
- **`test_data/` packs 01–04 use their own IDs** (e.g. `SYN-229`, `PHY-594`) and their own six reference files. Uploading
  a pack's `event_stream.csv` against the official kit used to hold every row as "Unknown physician/hospital" (1,709 held
  for pack 01). That was the user's bug report. Packs are gitignored and local only; 03/04 are blind tests.

## Uncommitted work (done and verified this session)

### 1. Stored reference kits + events-only upload matching (backend)

- `POST /admin/references`: the first kit must be the official Sevaro kit (409 otherwise, when the fingerprint pin is
  on). Afterwards an identical upload is a no-op and a **different kit is stored beside the active one, never replacing
  it** (`{"activated": false, "stored": true}`). Stored kits live in metadata key `reference_kits`, keyed by SHA-256.
- `GET /admin/references` adds `kits: [{fingerprint, name, service_date, hospitals, physicians, active}]`.
- `POST /events/csv` goes through `Engine.ingest_upload` (`backend/app/service.py`):
  - any hospital/physician ID in the active kit → append as before (judges' path; unknown IDs keep the G4 hold);
  - no ID in the active kit and all IDs in exactly one stored kit → switch: kit + new dataset generation + events commit
    in one transaction (`ingest_raw(..., refs=, source=)` → `_mutate_once(fresh=True)` → `commit_batch(new_generation=True)`),
    clock moves to the file's latest event (either direction), offers and interventions reset; report has
    `dataset_switched_to`;
  - no stored kit matches → 422 naming the unknown IDs; nothing added or held.
- Startup accepts a persisted active kit only if it is the official kit or a stored kit (tamper check kept).
- `scripts/upload_references.py` stores additional kits instead of refusing; `--check` also matches stored kits.
- This deliberately reverses the "forbid replacement" rule from commit `857a445`, with the user's approval.
- Files: `backend/app/{coordinator,db,main,service}.py`, `scripts/upload_references.py`, new
  `backend/tests/test_reference_kits.py`, updated `test_reference_policy.py`, `test_upload_references.py`,
  `test_csv_audit.py`. Docs: `Reference-Data.md` (new "Stored kits and the events-only upload" section),
  `00-Boundaries-and-Contracts.md`, PRD G4 row, `Deployment.md`.

### 2. Event upload moved to the Command page (web)

- New `web/src/act/EventStream.tsx`: CSV upload (plus "paste events"), Pause / +5 min, event-stream checks,
  "Start empty stream", upload history. Shown as section "04 · Event stream" on the Command page (`web/src/App.tsx`).
- `web/src/act/DataPage.tsx` now shows only reference data: active kit, hourly baseline, stored kits (Active/Stored).
- Side effect: the lead role has a Data page but no Command page, so leads can no longer upload events from the web.
  The user has not decided whether that is OK.

### 3. Prod moved to a new database (`commandcenter_v2`)

- RDS instance is in **us-west-2**. The old database **`commandcenter`** was rewritten by a *different, unpushed backend
  version* (tables `runtime_sessions`, `configuration_boot_audit`, `reference_bundle`, `source_generation_3`, …; no
  branch or local checkout contains that code). **It has since been dropped** (Joy kept a pg_dump backup).
- Created **`commandcenter_v2`** on the same instance (`cc_admin` has CREATEDB) and bootstrapped it with this code:
  official kit (fingerprint `81602969911f…`), official stream (1,163 accepted, 1 duplicate, 23 reordered, 1 late,
  0 held), clock paused at 2026-03-17 18:20 ET. The stored packs (`reference_kits`) were later deleted; re-store them
  with `scripts/upload_references.py` once this code runs against prod. Only one backend may write at a time (Joy's,
  as of 03:45 ET). Verified 18:20 decisions match the baseline:
  18 open consults; top items `stranded:CON-2110` reassign → PHY-002, `unassigned:CON-2105` escalate,
  `now_gap:SYN-005` split shift → PHY-009 (trap check passes), `notes_at_shift_end:PHY-003`, `handoff_needed:CON-2102`.
- `.env` (gitignored, local) now points `CC_DATABASE_URL` at `commandcenter_v2` with
  `sslrootcert=/Users/rishi/rds-global-bundle.pem` (it previously pointed at a bundle path on Joy's machine). The
  original `.env` was backed up only in the previous session's scratchpad.
- `render.yaml` region changed virginia → oregon. `docs/Deployment.md` / `docs/Reference-Data.md` describe `commandcenter_v2`.

## Verified

- Backend: **415 passed** (`cd backend && .venv/bin/python -m pytest -q`; needs local Postgres on 5432, e.g. Docker `cc-pg`).
- Web: type-check clean, **62 passed**, production build passes (`cd web && npm test && npm run build`).
- `git diff --check` clean.
- Browser check on a disposable local server: unknown-ID upload shows the 422 message; a pack 01 upload switches the
  header to `01_development`; Data page lists both kits.
- Not verified: mobile tests (mobile code unchanged); Render deployment; the full 1,710-row pack upload through the
  browser file picker (sent via the same endpoint from the shell instead).

## What was running when this was written (may be gone in a new chat)

- Backend on `127.0.0.1:8000` → prod `commandcenter_v2`, started by a launcher that loads `.env` and
  `CC_DATA_DIR=data`. Equivalent: export the `.env` values, then
  `cd backend && CC_DATA_DIR=../data .venv/bin/python -m uvicorn app.main:app --port 8000`.
- Web on `http://localhost:5181` → backend 8000 (`cd web && API_URL=http://127.0.0.1:8000 npx vite --port 5181`).
- The user's own web on 5180 → local Docker demo on 8010 (old code, local database). Not touched.
- Note: the desktop preview launcher's Node cannot read the Desktop folder (macOS permission); run Vite from the shell.

## Open items / next steps

1. Commit the uncommitted work when the user asks (one imperative ~50-char subject per `CLAUDE.md`).
2. Deploy to Render (needs dashboard access): `CC_DATABASE_URL` = RDS URL with database `commandcenter_v2` and
   `sslrootcert=/etc/ssl/certs/rds-global-bundle.pem` (the Docker image already includes that bundle); set `CC_USERS`,
   `CC_AUTH_SECRET`; region Oregon.
3. Ask the team who runs the other backend on `commandcenter`, and whether that code should be pushed or retired;
   two versions on two databases will drift.
4. Decide whether the lead role needs event upload (currently Command page only).
5. Still outside delivered scope: hosted/device rehearsal, real ElevenLabs playback, latency measurement, official
   weekend baselines (weekday proxy only), mobile broadcasts/schedule/preferences/release.
