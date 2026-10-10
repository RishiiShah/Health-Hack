**Owns:** `web/src/forecast/*`, `web/src/act/*`.
**Uses** Anish's `api/client.ts` and `live.ts`; asks Anish for changes to them.

### Tasks
1. Coverage forecast (`forecast/CoverageGrid.tsx`):
   - An HTML table: one row per hospital, one column per 15-minute step from now to +90 min.
   - Each cell shows count/required. Colours: gap, OK or unknown.
   - Markers for "unverified" and "schedule incomplete".
   - Clicking a cell lists the physician IDs counted.
   - Check: at 19:00, Suncrest needs 2, counts 1 (PHY-005) and is marked incomplete.
2. Demand panel: consults in the trailing 60 minutes vs the hourly 90th-percentile baseline, plus a surge badge → check: Suncrest shows 5 vs 1 with a surge badge; Lakeview shows 1 vs 2 with none.
3. Workload and shift-end risk:
   - Sorted by risk. Shows consults, calls, open consults, minutes to shift end, an overload badge, the shift-end-notes alert and the reason.
   - Check: PHY-003 is Critical with 40 min left.
4. Candidate table (`act/Candidates.tsx`):
   - For the selected gap, list every off-shift physician.
   - Columns R1 to R8 (the PRD's eight eligibility rules), each pass/fail with the server's explanation.
   - Show rank and the ranking factors. Highlight the eligible physician(s).
   - Check: exactly one is eligible, and each excluded physician shows the rule they failed.
5. Split-shift trap check display:
   - Results with and without the protection, the seeded starting consult count, and the hospitals the joining physician is limited to.
   - Pass/fail from the server.
   - Check: matches `GET /trap-check`.
6. Offer proposal form (coordinator):
   - Physician and hospitals are filled in and read-only (gap hospitals only). Start and end times are editable.
   - Server errors are shown as returned; the client doesn't validate rules.
   - Check: an offer under 2 h shows the server's error.
7. Approval queue (lead role):
   - Proposed offers and escalations, each with the gap, candidates considered and trap-check rationale.
   - Approve, or Reject with a required reason.
   - Check: approving with the coordinator token shows 403; approving with the lead token moves the offer to Sent.
8. Offer tracker:
   - Shows state and a countdown based on the server's `expires_at`.
   - Shows the simulated message exactly as sent, with a "Play" button for its audio and the physician link for the demo phone.
   - Check: the 10-minute expiry flips the state; a decline makes the next candidate appear as Proposed.
9. Closing the loop: after an Accept, the grid updates from the next pushed snapshot, with no client logic → check: the Suncrest gap closes and other offers show Withdrawn.
10. Audit log view: read-only, filtered by gap. Shows who was considered and excluded with reasons, who approved, when it was sent, and the outcome → check: every step of one full loop appears.
11. Live injector (admin):
    - Paste JSON or upload a CSV. Shows the server's accepted, duplicate and quarantined counts.
    - "Reset to base" with a confirmation step.
    - Check: T23 to T27 from Krish's file update the UI without a restart.
12. Data quality panel → check: 1 duplicate, 23 reordered, 1 late, 0 rejected.
13. `node --test` tests for the pure helpers (countdown, mapping cells to their status) → check: `npm test` passes.

**Out of scope:** charting libraries, editing eligibility rules, and sending real SMS or push notifications.

## Demo data

`VITE_DEMO_DATA=1 npm run dev` (or `VITE_DEMO_DATA=1` in `web/.env.local`) answers every API call from `web/src/demo/`, an in-memory stand-in with the design's values. Approve, reject, propose, add events, pause and +5 min all work against it, and the header shows a "Demo data" badge. Without the variable the app calls the real backend and the demo code is left out of the build.

## Response shapes these screens need (proposal for the backend owner)

The screens render these fields as-is and compute no rules. Every timestamp is ISO 8601 with an offset. Names and display text come from the server; the client never builds them from IDs. A section the server can't compute yet returns `supported: false` and the screen says so. Errors use FastAPI's `{"detail": "..."}`, shown to the user verbatim.

### Added to `GET /snapshot`

```jsonc
"coverage": {                       // G13
  "supported": true,
  "steps": ["2026-03-17T22:20:00+00:00", "...7 steps: now, then +15 to +90 min"],
  "assumption": "Current surge uplift (+1) carried across the horizon",   // or null
  "hospitals": [{
    "hospital_id": "…", "hospital_name": "…",
    "nobody_reachable_now": false,
    "cells": [{
      "at": "…", "count": 1, "required": 2,              // null when unknown
      "status": "gap | at_minimum | above_minimum | unknown",
      "unverified": false, "schedule_incomplete": true,
      "physician_ids": ["…"], "incomplete_physician_ids": ["…"],
      "gap_id": "…"                                       // set when status is gap
    }]
  }]
},
"demand": {                         // G12
  "supported": true,
  "items": [{ "hospital_id": "…", "hospital_name": "…", "trailing_60m": 5, "p90": 1, "status": "surge | normal | unknown" }]
},
"workload": {                       // G8, G8b, G10, sorted by the server
  "supported": true,
  "items": [{ "physician_id": "…", "name": "…", "consults": 14, "calls": 17, "open_consults": 3,
              "shift_end": "…", "minutes_to_shift_end": 40,
              "overload": "Critical | Warning | null", "shift_end_risk": "Critical | Warning | null",
              "open_notes": 2, "reason": "…" }]
},
"data_quality": {                   // G1 to G4
  "supported": true,
  "events_read": 1164, "accepted": 1163, "duplicates": 1, "duplicate_ids": ["…"], "conflicts": 0,
  "reordered": 23, "late": 1, "max_reorder_lag_s": 355, "max_delivery_lag_s": 405,
  "rejected": 0, "pending_orphans": 0, "expired_orphans": 0
},
"dataset": { "name": "…", "description": "…", "reference_files": 7 },
"pending_approvals": 1
```

### Gaps, offers and audit

| Route | Returns |
|---|---|
| `GET /gaps/{gap_id}/candidates` | `{gap, revision, rules: [{id: "R1", label}], candidates: [{physician_id, name, eligible, rank, primary_reason, results: [{rule, status: "pass \| fail \| unknown", explanation}], ranking: {gap_hospitals, minutes_to_online, declines_30d, hours_7d}}]}`, sorted by the server |
| `GET /gaps/{gap_id}/trap-check` | `{gap_id, physician_id, passed, reasons: [string], seed_consults, limited_to: [{hospital_id, hospital_name}], steps: [iso], without: [{count, required}], with: [{count, required}], joiner_load, busiest_peer_load, other_gaps_worsened, assumption}` |
| `POST /offers` `{gap_id, physician_id, start, end}` | `Offer` (state Proposed), or 4xx with the rule that failed |
| `GET /offers` | `{items: Offer[]}` |
| `POST /offers/{id}/approve`, `POST /offers/{id}/reject {reason}` | `Offer`; 403 for a non-lead token |
| `GET /interventions?state=pending` | `{items: [{intervention_id, kind, item_id, reason, created_at}]}` (escalations for the approval queue) |
| `GET /audit?gap_id=` | `{items: [{at, actor, action, detail}]}`, oldest first |
| `POST /events/csv` (body `text/csv`) | the same report as `POST /events` |
| `POST /admin/reset`, `POST /admin/clock {mode, at?, advance_s?, paused?}` | `{revision}` / the snapshot `clock` |

### Sign-in and roles

`POST /auth/login {email, password}` returns `{token, expires_at, user}` and `GET /auth/me` returns `{user}`; both are implemented in the backend (see backend/README.md). Sign-in automatically opens the account's workspace. Older clients may still send the optional `portal: "operations" | "physician"` field. The web app revalidates a saved session before opening a workspace and offers retry on connectivity errors. The server decides the role and must check every route:

| Route | Roles |
|---|---|
| `GET /snapshot`, `/consults/*`, `/gaps/*`, `/offers`, `/audit`, `/interventions` | coordinator, lead |
| `POST /offers` | coordinator |
| `POST /offers/{id}/approve`, `/reject`, `POST /interventions/{id}/authorize` | lead |
| `POST /events`, `/events/csv`, `/admin/*` | coordinator, lead |
| `GET /me/offers` → `{now, items: Offer[]}`, `POST /me/offers/{id}/accept`, `/decline` | physician (their own offers, only once Sent) |

`gap` is `{gap_id, hospital_ids, hospital_names, start, end, required, count, summary}`, where `summary` is the server's plain-language reason (for example the trailing count against the usual peak, and who leaves at the shift change).

`Offer` is `{offer_id, gap_id, physician_id, physician_name, hospital_names, start, end, state, checked_count, proposed_by, proposed_at, approved_by, approved_at, sent_at, expires_at, responded_at, message, audio_url, phone_url, reject_reason}`. `message` is the exact text sent (hospital, hours and start only); `audio_url` is null when ElevenLabs is unavailable.
