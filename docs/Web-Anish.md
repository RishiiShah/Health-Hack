**Owns:** `web/` setup, `web/src/api/*`, `web/src/App.tsx`, `web/src/styles.css`, `web/src/detect/*`.
**Doesn't own:** the Decide/Act screens (Joy) or any rule logic (the server computes it).

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
5. Token screen: choose a role (coordinator or lead), paste the token and store it in `sessionStorage` → check: a wrong token shows the 401 message.
6. Header: clock mode and current time, plus six headline numbers taken directly from the snapshot → check: the values match the PRD's expected values at 18:20.
7. Attention queue (`detect/AttentionQueue.tsx`):
   - Shows rank, score (two decimals when fractional), level badge, reason text and uncertainty label.
   - The server decides the order.
   - Check: CON-2105 is first with a score of 160.
8. Item detail panel: the full reason, the linked consult, physician or hospital, and the action buttons from step 11 → check: it opens for every item type.
9. Consult board:
   - One row per open consult: hospital, type, stage, minutes in stage, minutes since received.
   - The colour comes from the server's level, not from thresholds in the client.
   - Check: CON-2102 shows 26 min in red (Critical).
10. Physician board:
    - Derived state next to the self-reported status, agent online/offline, an "unverified" badge, whether they can take calls, and the main reason if not.
    - Check: PHY-001 shows "camera active, no session"; PHY-007 shows offline, unverified and not taking calls while the phone rings.
11. Stuck consults:
    - Shows routing failure count, next retry time, and every credentialed physician with their exclusion reason.
    - Buttons: "Reassign to…" (only physicians the server lists as eligible) and "Escalate", both calling `POST /interventions`.
    - Check: CON-2105 shows 3 failures and CON-2110 shows as stranded.
12. Signal flags panel: conflicting or unverified signals with the reason → check: PHY-001 and PHY-007 appear.
13. Voice alerts:
    - An "Enable voice alerts" button (browsers only allow audio after a click).
    - Play `/alerts/{id}/audio` once for each Critical item ID not heard before.
    - Mute toggle; if the server returns 503, stay silent.
    - Check: inject test case T23, and the alert plays once, not on every update.
14. Page layout: Detect panels on the left, Joy's Decide/Act panels on the right, plain CSS grid → check: usable at 1366 px wide.
15. `node --test` tests for the pure functions (seq guard, score format, minute format) → check: `npm test` passes.

**Out of scope:** charts, a timeline view, client-side rule logic, routing, and recreating the baseline workload table.
