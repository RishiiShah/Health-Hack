**Owns:** `web/` setup, `web/src/api/*`, `web/src/auth/*`, `web/src/App.tsx`, `web/src/styles.css`, `web/src/detect/*`, `web/src/physician/*`.
**Doesn't own:** the Decide/Act and clinical-lead screens (Joy) or any rule logic (the server computes it).
**Roles on web:** coordinator, clinical lead and physician, each with their own dashboard chosen from `GET /me` (see RBAC in `00-Boundaries-and-Contracts.md`).

### Tasks (each with how to check it)
1. Create the `web/` project (Vite + React + TypeScript, Node 24) → check: `npm run build` succeeds.
2. Add an `npm run gen:api` script that runs `openapi-typescript` against `/openapi.json` and writes `src/api/types.gen.ts` → check: the generated types compile and are never edited by hand.
3. `src/api/client.ts`: a `fetch` wrapper that adds the bearer token, parses JSON and turns non-2xx responses into a typed `ApiError {status, message}` → check: a `node --test` test with a stubbed `fetch`.
4. `src/api/live.ts` (live updates over WebSocket):
   - Connect to `/ws`.
   - Ignore any message whose `seq` is no newer than the last one seen.
   - If `epoch` changes, reload `/snapshot`.
   - On disconnect, reconnect every 2 s, then reload `/snapshot`.
   - Check: stop and restart the backend, and the UI recovers without a page refresh.
5. Sign-in (`auth/`):
   - Read `token` (and `offer`) from the URL once, store the token in `sessionStorage`, then remove both from the address bar with `history.replaceState`.
   - With no token, show a sign-in screen to paste one. There is no role picker: the role comes from the server.
   - Call `GET /me`; any 401 clears the token and returns to sign-in.
   - Check: a wrong token shows the 401 message; a physician link signs in and the token is gone from the address bar.
6. Role routing (`App.tsx`):
   - Load the dashboard for `me.role`: coordinator → Detect (left) plus Joy's Decide/Act (right); lead → Joy's lead dashboard; physician → `physician/`; admin → coordinator layout plus Joy's live injector.
   - Expose `can(permission)` from `me.permissions`; components show an action only when it's allowed. This is convenience only; the server still enforces it.
   - Check: each of the four demo tokens lands on its own dashboard, and a lead never sees "Propose offer".
7. Header: clock mode and current time, plus six headline numbers taken directly from the snapshot → check: the values match the PRD's expected values at 18:20.
8. Attention queue (`detect/AttentionQueue.tsx`):
   - Shows rank, score (two decimals when fractional), level badge, reason text and uncertainty label.
   - The server decides the order.
   - Check: CON-2105 is first with a score of 160.
9. Item detail panel: the full reason, the linked consult, physician or hospital, and the action buttons from step 12 → check: it opens for every item type.
10. Consult board:
   - One row per open consult: hospital, type, stage, minutes in stage, minutes since received.
   - The colour comes from the server's level, not from thresholds in the client.
   - Check: CON-2102 shows 26 min in red (Critical).
11. Physician board:
    - Derived state next to the self-reported status, agent online/offline, an "unverified" badge, whether they can take calls, and the main reason if not.
    - Check: PHY-001 shows "camera active, no session"; PHY-007 shows offline, unverified and not taking calls while the phone rings.
12. Stuck consults:
    - Shows routing failure count, next retry time, and every credentialed physician with their exclusion reason.
    - Buttons: "Reassign to…" (only physicians the server lists as eligible) and "Escalate", both calling `POST /interventions`.
    - Check: CON-2105 shows 3 failures and CON-2110 shows as stranded.
13. Signal flags panel: conflicting or unverified signals with the reason → check: PHY-001 and PHY-007 appear.
14. Voice alerts:
    - An "Enable voice alerts" button (browsers only allow audio after a click).
    - Play `/alerts/{id}/audio` once for each Critical item ID not heard before.
    - Mute toggle; if the server returns 503, stay silent.
    - Check: inject test case T23, and the alert plays once, not on every update.
15. Page layout: plain CSS grid per role. Coordinator: Detect left, Decide/Act right, usable at 1366 px. Lead and physician dashboards also work at 390 px wide, for a lead or physician using the web on a phone → check: both widths by resizing the browser.
16. Physician dashboard (`physician/`), same content as the mobile physician app:
    - My offers from `GET /offers` (the server returns only this physician's): hospitals, Eastern start and end times, hours, the "why you were asked" text, expiry countdown from the server's `server_now` and `expires_at`.
    - Accept and Decline with a confirmation step; end states Accepted, Already filled, Declined, Expired and "No longer active".
    - "Listen to offer": fetch `/offers/{id}/audio` with the bearer token, play it from a blob URL, hide the button on 503.
    - My accepted shifts (offers in state Accepted), soonest first.
    - Poll every 5 s while any offer is Sent. No patient or consult details anywhere.
    - Check: two physician tokens accepting the same gap get Accepted and Already filled.
17. `node --test` tests for the pure functions (seq guard, score format, minute format, countdown, role → dashboard mapping) → check: `npm test` passes.

**Out of scope:** charts, a timeline view, client-side rule logic or permission logic, a router library, and recreating the baseline workload table.
