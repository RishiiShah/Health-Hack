**Purpose:** let the clinical lead and the off-shift physician work on the go. One app, and the dashboard comes from the signed-in role (`GET /me`):
- **Physician:** my offers (accept or decline) and my accepted shifts.
- **Clinical lead:** approve or reject offers and escalations, see stroke-risk Critical items and offer status.
- **Coordinator:** a single "Use the web dashboard" screen. **Admin:** the same.

**Stack:** Flutter web, so judges open a link on any phone. Plain `setState` and `ValueNotifier`, plus `Navigator`.
**Owns:** `mobile/lib/screens/*`, `mobile/lib/main.dart`, `mobile/test/screens/*`.
**Uses** Chandan's `AuthRepository`, `OfferRepository` and `LeadRepository`; never calls HTTP directly, and never decides permissions (it only reads `me.permissions`; the server enforces them).

### Tasks
1. Create the project with `flutter create --platforms web mobile` → check: `flutter build web` succeeds.
2. Startup and sign-in:
   - Ask `AuthRepository` for the current user. It reads a `token` from the URL or session storage.
   - With no token, show a sign-in screen to paste one (no role picker; the role comes from the server).
   - A 401 at any point returns to sign-in.
   - Check: widget tests for no token, a valid token and a 401.
3. Role router: `me.role` picks the home screen: physician → `PhysicianHome`, lead → `LeadHome`, coordinator or admin → "Use the web dashboard" with the web link. An unknown role shows an error, never a default dashboard → check: one widget test per role.

**Physician screens**

4. `PhysicianHome`: active offers first, then "My accepted shifts" (soonest first). If the URL carried an `offer` ID, open that offer directly → check: a widget test with a fake repository.
5. Offer screen:
   - Hospital names, date, start and end times (Eastern, labelled as such), hours, the "why you were asked" text, and an expiry countdown.
   - Two large buttons: Accept and Decline, each behind a confirmation dialog. Cancelling makes no request.
   - Check: the screen has no other actions.
6. End-state screens: Accepted (start time, plus "You'll receive calls only from: <hospitals>"), Already filled, Declined, Expired, and "No longer active" (for Withdrawn, Cancelled or Rejected) → check: one widget test per state.

**Clinical-lead screens**

7. `LeadHome`: the approval queue (Proposed offers and escalations, newest first, with a count), then stroke-risk Critical items (the server's order, level and reason text), then a compact offer-status list → check: a widget test with fake data in each section.
8. Approval detail:
   - The gap (hospital, window, required vs counted), the proposed physician, the ranking reason, the number of candidates excluded with each one's failed rule, and the trap-check result (pass/fail with the server's explanation).
   - "See all candidates" opens the full read-only list.
   - Approve, or Reject with a required reason, each behind a confirmation dialog.
   - Check: Reject is disabled until a reason is typed; a 403 shows "You don't have permission for this" and changes nothing.
9. Escalation detail: the item, its reason and the proposed intervention, with Authorize behind a confirmation → check: a widget test.

**Shared**

10. Error screens: network error with a Retry button, invalid or expired sign-in (401), and permission denied (403) → check: widget tests with a fake repository.
11. Show a loading state between taps, and disable the buttons while a request is in flight → check: a widget test.
12. Accessibility: tap targets at least 48 dp, screen-reader labels on every action, works at 200% text size, readable at 390 px wide → check: a manual pass on one phone for each role.

**Out of scope:** the coordinator command center on mobile, client-side permission or rule logic, push notifications, patient information, and any HTTP code.
