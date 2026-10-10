**Owns:** `mobile/lib/data/*`, `mobile/lib/audio.dart`, the build and deploy config, `mobile/test/data/*`, and the shared JSON samples in `docs/contracts/mobile_*.json`.
**Serves** Hitanshu's screens for two roles, clinical lead and physician; the role and permissions come from `GET /me` (see RBAC in `00-Boundaries-and-Contracts.md`).

### Tasks
1. `AuthRepository`:
   - `currentUser()` reads `token` from the URL once (`Uri.base`), saves it in `sessionStorage` via `package:web`, then removes `token` and `offer` from the address bar with `history.replaceState`.
   - Calls `GET /me` and returns `Me {role, displayName, physicianId, permissions}`. `signIn(token)` and `signOut()` for the paste screen.
   - Every repository sends `Authorization: Bearer <token>`; a 401 from any call signs out.
   - Check: unit tests for URL token, stored token, no token and 401.
2. `OfferRepository` (physician): `listOffers`, `getOffer`, `accept` and `decline` against `/offers*`. The server returns only this physician's offers → check: it parses all the sample JSON files.
3. `LeadRepository` (clinical lead): `snapshot` (for stroke-risk items), `offers`, `candidates(gapId)`, `trapCheck(gapId)`, `audit(gapId)`, `approve`, `reject(reason)` and `authorize(interventionId)` → check: it parses the sample JSON files, and a 403 surfaces as a typed `Forbidden` error.
4. Fakes of all three repositories for Hitanshu's widget tests → check: his tests run with no network.
5. DTOs: parse each field explicitly. An unknown role, an unknown state or a missing field is an error, never a silent default → check: unit tests with bad JSON.
6. Polling:
   - Physician: every 5 s while any offer is Sent.
   - Lead: every 5 s for the approval queue and the snapshot. The server caches the snapshot, so this is cheap.
   - Stop while the tab is hidden and refresh as soon as it's visible again.
   - Check: a unit test with a fake timer.
7. Clock-difference correction: compute countdowns from the server's `server_now` and `expires_at`, not the phone's clock → check: the countdown is correct with the phone clock set wrong.
8. Repeated-tap safety: a retried accept, approve or reject after a network error must return the same result (the backend makes these safe to repeat; agree it with them) → check: a scripted retry.
9. Audio:
   - "Listen to offer" for the physician, and an "approval requested" sound for the lead when a new Proposed offer appears (played once, only after the lead taps "Enable sound").
   - Fetch `/offers/{id}/audio` or `/alerts/{id}/audio` with the bearer token, then play the bytes from a blob URL with `package:web`'s `HTMLAudioElement` (an audio `src` can't send the auth header). Never autoplays without that first tap; hide the button on 503.
   - Check: plays on a phone for both roles; hidden when the API key is removed.
10. Config: `--dart-define=API_BASE_URL=…` → check: the build points at the deployed backend.
11. Deploy the Flutter web build as a static site on Vercel. Send the origin to the backend owner to add to the server's allowed-origins (CORS) list → check: the link opens on a phone over HTTPS.
12. Demo script (`docs/demo-mobile.md`): the lead approves an offer on one phone; two physician phones accept the same gap, so one gets "Already filled"; plus one expiry run → check: rehearsed once end to end.

**Out of scope:** state-management, audio or Firebase plugins, storing anything beyond the session token, native app-store builds, and any permission logic (the server decides).
