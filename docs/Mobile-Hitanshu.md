> **Document status:** Owner design checklist. Live mode uses the existing backend adapter; schedule views, preference updates, release and broadcasts below remain design-only features. See [current document authority](README.md) and [gap fixes](Decision-Engine-Gap-Fixes.md).

# Mobile — Hitanshu (screens)

You build every screen of the Flutter web app for two roles, physician and clinical lead, following the UI design (`Sevaro Command Center Screens.pdf`) and the theme reference. Chandan builds the data layer; you only call his interfaces.

**Read first:** `Mobile-App-Contract.md` (v1.1), especially sections 4.3 (what each offer status shows), 5.1 (broadcast), 8 (countdown) and 13 (fields behind the design). Field names below are the contract's.

## What you own

| Path | Contents |
| --- | --- |
| `mobile/lib/main.dart` | Startup, `AppServices.fromEnvironment()`, role router |
| `mobile/lib/screens/*` | All screens and widgets |
| `mobile/test/screens/*` | Widget tests, all on Chandan's fakes |
| `mobile/web/index.html` | Loading screen shown before Flutter starts |

**Stack:** Flutter web, `setState` and `ValueNotifier`/`ValueListenableBuilder`, `Navigator`. No state-management packages.

## Rules

1. **Never write HTTP code.** Use the repositories, feeds, clock and alerts from `AppServices`.
2. **Never decide permissions.** Show a button only when the data allows it: `offer.allowedActions` for physicians, `me.permissions` for the lead. The server still enforces everything; a 403 shows "You don't have permission for this" and changes nothing.
3. **Role comes from `me.role`, not the sign-in switch.** Unknown role → error screen, never a default dashboard.
4. **Never show Accepted (or Approved) before the server says so.** Show a loading state and disable both buttons while a request is in flight.
5. **All times from the server clock, shown in ET with "ET".** Use Chandan's `ServerClock` and `formatEt()`, never `DateTime.now()`.
6. **No patient information** on the lock screen, offer screens or toasts. Render the server's text; don't add consult details.
7. **Render from data, never hardcode names.** The design shows Okafor, but every name, hospital, time and count comes from the API.
8. **Every confirm dialog's Cancel makes no request.**

## The interface you use

Chandan commits this first, with fakes. Build against the fakes from the start.

```dart
// mobile/lib/data/api.dart
abstract class AuthRepository {
  Future<Me?> currentUser();
  Future<Me> signIn(String email, String password);
  Future<void> signOut();
  Future<PreferencesResult> setOptIn(bool optIn, {bool declineOpenOffer = false});
  String? takeInitialOfferId();
  Stream<void> get signedOut;
}
abstract class OfferRepository {
  Future<OfferList> listOffers();
  Future<Offer> getOffer(String offerId);
  Future<OfferActionResult> accept(String offerId);
  Future<OfferActionResult> decline(String offerId);
  Future<OfferActionResult> release(String offerId);
  Future<NotificationList> notifications();
}
abstract class ShiftRepository {
  Future<MyShift> myShift();
  Future<MySchedule> mySchedule(DateTime weekStart);
}
abstract class LeadRepository {
  Future<LeadQueue> queue();
  Future<Proposal> proposal(String proposalId);
  Future<ProposalActionResult> approve(String proposalId);
  Future<ProposalActionResult> reject(String proposalId, String reason);
  Future<CandidateList> candidates(String gapId);
  Future<TrapCheck> trapCheck(String gapId);
  Future<AuditLog> audit(String gapId);
  Future<BroadcastList> activeOffers();
  Future<EscalationActionResult> authorize(String escalationId);
  Future<CoverageBoard> coverage();
  Future<LeadSchedule> schedule(DateTime date);
}
abstract class PhysicianFeed {
  ValueListenable<AsyncSnapshot<OfferList>> get offers;
  ValueListenable<AsyncSnapshot<NotificationList>> get notifications;
  Stream<Offer> get newOffer;
  Stream<Offer> get offerChanged;
  void start(); void stop(); Future<void> refreshNow();
}
abstract class LeadFeed {
  ValueListenable<AsyncSnapshot<LeadQueue>> get queue;
  ValueListenable<AsyncSnapshot<BroadcastList>> get activeOffers;
  Stream<AnswerEvent> get answers;
  void start(); void stop(); Future<void> refreshNow();
}
abstract class ServerClock {
  DateTime now();
  Duration remaining(DateTime until);
  ValueListenable<DateTime> get ticks;
}
abstract class WebAlerts {
  Future<void> enableSound(); bool get soundEnabled;
  void chime(); void vibrate(); void setBadge(int count);
}
sealed class ApiException implements Exception {}
// Unauthorized, Forbidden, NotFound, InvalidRequest(String message), Unavailable, NetworkError, ParseError
```

For screens that poll on their own (My shift, Coverage), use Chandan's `Poller(interval, callback)` and stop it in `dispose()`.

## Tasks

### 1. Project and startup
- `flutter create --platforms web mobile`. Push it so Chandan can add `lib/data/`.
- `main.dart`: build `AppServices.fromEnvironment()`, call `SemanticsBinding.instance.ensureSemantics()` (Flutter web doesn't build the screen-reader tree otherwise), then `auth.currentUser()`.
- `web/index.html`: a simple Sevaro loading screen so phones don't show a blank page while Flutter loads.
- Listen to `auth.signedOut` everywhere: go to sign-in.
- **Check:** `flutter build web` succeeds; widget tests for no token, valid token, and a 401 mid-session.

### 2. Sign-in
- Email, password, Sign in. "I work as: Operations | Physician" only changes the subtitle.
- Errors from `signIn`: show the server's message under the form; keep the email filled.
- "Use Sevaro single sign-on" and "Forgot password?" → "Not available in the demo".
- Footer: demo accounts, "Synthetic data only".
- **Check:** wrong password shows the message; success routes by role.

### 3. Role router
| `me.role` | Home |
| --- | --- |
| `physician` | Physician tabs: My shift, Schedule, Offers, Account |
| `clinical_lead` | Lead tabs: Approvals, Schedule, Coverage, Account |
| `coordinator`, `admin` | One screen: "Use the web dashboard" with the link |
| anything else | Error screen (the data layer already rejects unknown roles) |

- If `auth.takeInitialOfferId()` returns an ID for a physician, open that offer directly.
- **Check:** one widget test per role.

## Physician screens

Start `PhysicianFeed` when the physician home opens; stop it on sign-out.

### 4. Simulated lock screen (the Duo-style takeover)
- Opens full screen over any tab when `feed.newOffer` fires. Shows date and time from the server clock, the notification list from `feed.notifications`, and the label "<name>'s phone · off shift · simulated".
- On open: `alerts.chime()` (if sound is enabled), `alerts.vibrate()`, `alerts.setBadge(unread offers)`.
- Tapping the offer notification opens the offer detail. Clear the badge when the offer screen opens.
- **Check:** a widget test where the fake pushes a new offer while on My shift → lock screen appears.

### 5. Offers tab and offer detail
- **List:** `sent` offers first, then accepted (soonest first), then Recent (all others), each with its status label from contract 4.3. Header: "<name> · off shift". Show "2 of 3 requests this week" from `me.offersReceived7d` / `me.weeklyOfferLimit`.
- **Detail (status `sent`):** "Approved by your clinical lead", countdown, headline ("Cover <hospital> tonight?"), `gapSummary`, Hospital, Hours (ET), Start ("Sign in by" `signInBy`), Why you (`whyYou` bullets), the note "No patient details are shared until you accept. Declining doesn't change your schedule.", then the buttons from `allowedActions`: **Accept, I'll cover it** and **Not tonight**, each behind a confirmation.
- **Countdown:** `clock.remaining(offer.expiresAt)` on every tick. At 0:00 disable both buttons immediately and show "Expiring…" until the feed returns the server's status.
- **After a tap:** show the screen for `result.outcome` (contract 4.5), not for what was tapped. An `expired` outcome after Accept shows Missed with "Your response arrived after the request expired."
- If `feed.offerChanged` reports this offer changed while it's open (filled by someone else, expired), switch to that end state.
- **Check:** a widget test per outcome; the screen has no actions other than those in `allowedActions`.

### 6. End states
| State | Shows |
| --- | --- |
| Accepted | "Confirmed. You're on at <hospital> tonight.", Hospital, Hours, Sign in by, "You'll only be routed <`routingHospitals`> consults during these hours.", `coverageAfter` ("<hospital> now shows 2 of 2 from 19:00"), What happens next (`nextSteps`), and **I can't make it after all** only if `allowedActions` has `release` (confirm first) |
| Already filled | "Already filled, thank you." Nothing changed on your schedule |
| Declined | "You declined this request." |
| Missed (`expired`) | "This request expired at <time> ET without a response." No penalty wording |
| No longer needed (`withdrawn` / `gap_closed`) | "This shift no longer needs coverage." |
| Released | "You let your clinical lead know you can't make it." |

- **Check:** one widget test per state.

### 7. My shift
- `shifts.myShift()`, refreshed every 30 s while the tab is open.
- **On shift:** header "<name> · until <shift_end>", the `update` banner if present, the consult cards (ID, type, badge, hospital, `statusText`, color by `level`), and the footer "<time left> left · <consultsToday> consults today". Time left = `clock.remaining(shiftEnd)`.
- **Off shift:** "You're off shift", next shift if known, and a link to Offers.
- **Check:** widget tests for on shift, off shift, and an empty consult list.

### 8. My schedule
- `shifts.mySchedule(weekStart)`. Week strip from `days` (color by `kind`; `split` = accepted extra shift), Today card, "With you at <hospital>" timeline from `withYou.rows` (highlight `isYou`), the note, Next shift ("Not in this roster yet" when null).
- Swiping or tapping arrows changes `weekStart` by 7 days.
- **Check:** widget test with the sample schedule.

### 9. Account (physician)
- Name, role, **Available for extra shifts** switch (`me.splitShiftOptIn`), **Enable sound** (calls `alerts.enableSound()` from the tap), Sign out, "Synthetic data only".
- **Opt-in switch:** turning it off calls `setOptIn(false)`. If the result's outcome is `open_offer_exists`, ask "You have an open request. Decline it and opt out?"; Yes → `setOptIn(false, declineOpenOffer: true)`. When off, show on Offers: "You won't receive coverage requests."
- **Check:** widget tests for opt in, opt out, and the open-offer prompt.

## Clinical-lead screens

Start `LeadFeed` when the lead home opens; stop it on sign-out.

### 10. Approvals
- Header: date and time from the server clock ("Tue 17 Mar · 18:22 ET"), "Approvals · <pendingCount> waiting".
- **Proposal card** (per `queue.proposals`, newest first), opens `lead.proposal(id)`:
  - "Waiting for you · gap at <start>", recipient line ("Dr. Okafor for Suncrest", or "2 physicians for Suncrest"), hours, off shift.
  - Before/after table from `coveragePreview` (Without / With, per time).
  - "Checked <n> off-shift physicians": eligible names, then `excluded` grouped by identical reason ("Haddad, Brennan: not opted in to extra shifts"). **See all candidates** opens `lead.candidates(gapId)` read-only with all eight rules per physician.
  - Trap-check result and explanation (`lead.trapCheck(gapId)`), and a link to the audit log (`lead.audit(gapId)`).
  - **Approve and send to Dr. Okafor** (one recipient) or **Approve and send to <n> physicians**; **Reject**, which needs a typed reason (button disabled until then). Both behind confirmations.
  - After a tap, show `result.outcome`: approved (with any `skipped` recipients and why), rejected, or already decided.
- **Escalation cards** (`queue.escalations`): reason, proposed intervention, **Authorize** behind a confirmation.
- **Sent** section from `feed.activeOffers`: each broadcast with each recipient's status and countdown; Filled / Unfilled when done.
- **Done automatically** from `queue.automatedActions`.
- **Toast** on each `feed.answers` event ("Dr. Okafor accepted · Suncrest 19:00–23:00 ET"), with a chime if sound is enabled.
- **Check:** widget tests for proposal detail, reject disabled until a reason is typed, a 403 on approve, an escalation, and an answer toast.

### 11. Lead schedule
- `lead.schedule(date)`. Week strip (tap a day to change `date`), the banner (tap opens the proposal), the 12:00–24:00 timeline with On shift and Off shift rows colored by `kind` (Day, Night, Away, Offer legend), "Off shift · <working> of <total> working today".
- **Check:** widget test with the sample schedule, banner tap opens the proposal.

### 12. Coverage
- `lead.coverage()`, refreshed every 15 s while open. Columns from `columns`, one row per hospital with `statusText`, cells "staffed/required" with `marker`, color by `level`; footnotes below. Label the table "Staffed / required · training data".
- **Check:** widget test with the sample board, including a footnote marker.

### 13. Account (lead)
- Name, role, **Enable sound**, Sign out, "Synthetic data only".

## Shared

### 14. Errors and loading
| Error | Screen |
| --- | --- |
| `NetworkError`, `Unavailable` | "Can't reach Sevaro" with Retry |
| `Unauthorized` | Back to sign-in |
| `Forbidden` | "You don't have permission for this." Nothing changes |
| `NotFound` | "This item is no longer available." |
| `InvalidRequest` | The server's message |
| A feed with stale data and an error | Keep showing the data, plus a small "Reconnecting…" banner |

- Every action button shows a spinner and both buttons are disabled while the request runs.
- **Check:** widget tests with the fake set to fail with each error.

### 15. Accessibility
- Tap targets at least 48 dp, semantic labels on every action, works at 200% text size, readable at 390 px wide with no horizontal scroll.
- **Check:** one manual pass on a phone per role, with a screen reader on.

## Timeline

| When | Task |
| --- | --- |
| Sat 3–4 PM | 1, 3; theme and shared widgets |
| Sat 4–8 PM | 2, 4, 5, 6 (physician offer flow on fakes) |
| Sat 8–11 PM | 10 (Approvals), 9 (Account and opt-in), 14 |
| Sat 11 PM–2 AM | 7, 8, 11, 12, 13 |
| Sun 8–10 AM | 15, demo rehearsal with Chandan, code freeze |

The offer flow and Approvals are the demo; build them first. Schedule and Coverage come after.

## Done when
- Every widget test passes on fakes, with no network.
- The demo script (`docs/demo-mobile.md`) runs end to end on four phones: lead approves, two physicians race, one Missed run, Shah's My shift.