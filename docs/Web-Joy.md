**Owns:** `web/src/forecast/*`, `web/src/act/*`, `web/src/lead/*`.
**Uses** Anish's `api/client.ts`, `live.ts` and `can(permission)`; asks Anish for changes to them.
**Roles:** the coordinator uses the Decide/Act panels; the clinical lead gets a dashboard of their own (task 14), which mirrors the lead screens in the mobile app.

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
14. Clinical-lead dashboard (`lead/LeadDashboard.tsx`), loaded when `me.role` is lead:
    - Home is the approval queue from task 7, newest first, with a count badge.
    - Below it: stroke-risk Critical items from the snapshot's attention queue (read-only, the server's order and reasons), and the offer tracker from task 8 (read-only for the lead).
    - Audit by gap from task 10.
    - "Approval requested" voice alert: when a new Proposed offer appears, play `/alerts/{id}/audio` once, using the same enable/mute pattern as Anish's voice alerts.
    - Usable at 390 px wide (a lead on the go may open the web on a phone).
    - Check: with the lead token, approve and reject both work and the coordinator-only actions never render; with the coordinator token, approving returns 403.

**Out of scope:** charting libraries, editing eligibility rules, client-side permission logic, and sending real SMS or push notifications.
