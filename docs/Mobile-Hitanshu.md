**Purpose:** the off-shift physician sees one offer and can accept or decline it. Nothing else.
**Stack:** Flutter web, so judges open a link on any phone. Plain `setState` and `ValueNotifier`, plus `Navigator`.
**Owns:** `mobile/lib/screens/*`, `mobile/lib/main.dart`, `mobile/test/screens/*`.
**Uses** Chandan's `OfferRepository` interface; never calls HTTP directly.

### Tasks
1. Create the project with `flutter create --platforms web mobile` → check: `flutter build web` succeeds.
2. Startup: read `token` from the page URL (`Uri.base`). With no token, show "No active offer. Open the link from your message." → check: a widget test.
3. Offer screen:
   - Hospital names, date, start and end times (Eastern, labelled as such), hours, the "why you were asked" text, and an expiry countdown.
   - Two large buttons: Accept and Decline.
   - Check: the screen has no other buttons or navigation.
4. Confirmation dialog on Accept and on Decline → check: cancelling the dialog makes no request.
5. End-state screens: Accepted (start time, plus "You'll receive calls only from: <hospitals>"), Already filled, Declined, Expired, and "No longer active" (for Withdrawn, Cancelled or Rejected) → check: one widget test per state.
6. Error screens: network error with a Retry button, and invalid or expired link (401) → check: widget tests with a fake repository.
7. Accessibility: tap targets at least 48 dp, screen-reader labels on every action, works at 200% text size → check: a manual pass on one phone.
8. Show a loading state between taps, and disable the buttons while a request is in flight → check: a widget test.

**Out of scope:** login, offer history, settings, push notifications, patient information, and any API logic.
