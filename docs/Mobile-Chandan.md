> **Document status:** Owner design checklist. The live backend adapter scope at the top of Mobile-App-Contract.md overrides design-only v1.1 routes. The server remains the authority for permissions and rules. See [current document authority](README.md) and [gap fixes](Decision-Engine-Gap-Fixes.md).

# Mobile — Chandan (data, platform, deploy)

You build everything the screens stand on: the API client, repositories, live feeds, server clock, browser alerts, fakes, sample JSON, deploy and the demo script. Hitanshu builds every screen on top of your interfaces and never writes HTTP code.

**Read first:** `Mobile-App-Contract.md` (v1.1). It is the source of truth for every endpoint, field name, enum and outcome. If something here disagrees with it, the contract wins; change the contract first, then the code.

## What you own

| Path | Contents |
| --- | --- |
| `mobile/lib/data/*` | DTOs, API client, repositories, fakes, feeds, server clock, `AppServices` |
| `mobile/lib/web_alerts.dart` | Chime, vibration, tab-title badge (replaces the old `audio.dart`; audio read-aloud is dropped) |
| `mobile/test/data/*` | All data-layer tests |
| `docs/contracts/mobile_*.json` | Shared sample JSON, also used by your fakes and Hitanshu's tests |
| `mobile/web/` deploy config, `vercel.json` | Build and deploy |
| `docs/demo-mobile.md` | Demo script |

Hitanshu owns `mobile/lib/main.dart`, `mobile/lib/screens/*` and `mobile/test/screens/*`. He creates the Flutter project; you add `lib/data/` to it.

**Rules:** no state-management, Firebase or audio plugins. Dependencies are limited to `package:http` and `package:web` (plus Flutter's own `foundation` and `widgets` for `ValueListenable` and `AsyncSnapshot`). Store nothing but the session token. No permission logic in the app; the server decides.

## The interface you hand to Hitanshu

Commit this file **first**, with fakes behind it, so he can start immediately. The same block is in his file.

```dart
// mobile/lib/data/api.dart
abstract class AuthRepository {
  Future<Me?> currentUser();                    // URL token → sessionStorage → GET /me; null if none
  Future<Me> signIn(String email, String password);
  Future<void> signOut();
  Future<PreferencesResult> setOptIn(bool optIn, {bool declineOpenOffer = false});
  String? takeInitialOfferId();                 // the ?offer= value, returned once, then null
  Stream<void> get signedOut;                   // fires on any 401 from any call
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

// Live data. AsyncSnapshot carries data, error and loading state.
abstract class PhysicianFeed {
  ValueListenable<AsyncSnapshot<OfferList>> get offers;
  ValueListenable<AsyncSnapshot<NotificationList>> get notifications;
  Stream<Offer> get newOffer;          // a `sent` offer not seen before
  Stream<Offer> get offerChanged;      // any status change on a known offer
  void start(); void stop(); Future<void> refreshNow();
}

abstract class LeadFeed {
  ValueListenable<AsyncSnapshot<LeadQueue>> get queue;
  ValueListenable<AsyncSnapshot<BroadcastList>> get activeOffers;
  Stream<AnswerEvent> get answers;     // a recipient's offer changed status (accepted, declined, expired, released)
  void start(); void stop(); Future<void> refreshNow();
}

abstract class ServerClock {
  DateTime now();                      // device time corrected by server_now
  Duration remaining(DateTime until);  // never negative
  ValueListenable<DateTime> get ticks; // updates every second
}

abstract class WebAlerts {
  Future<void> enableSound();          // call from a tap; unlocks audio
  bool get soundEnabled;
  void chime(); void vibrate(); void setBadge(int count); // badge 0 restores the title
}

sealed class ApiException implements Exception {}
// Unauthorized, Forbidden, NotFound, InvalidRequest(String message), Unavailable, NetworkError, ParseError

class AppServices {
  // One of each of the above. AppServices.fromEnvironment() picks real or fake from API_MODE.
}
```

DTO class names match the contract's schema names (`Me`, `Offer`, `OfferActionResult`, `MyShift`, `CoverageBoard`, …), with `camelCase` fields. Enums are Dart enums; parsing an unknown value throws `ParseError`.

## Tasks, in order

### 1. Interface and fakes first (first hour)
- Commit `api.dart` as above plus a `FakeServices` that returns the sample JSON.
- Fakes must be scriptable for Hitanshu's tests and the offline demo: `fakeOffers.pushNewOffer()`, `fakeOffers.expire(id)`, `fakeOffers.fillByOther(id)`, `fakeClock.set(…)`, `fakeLead.addProposal()`, and a switch to make the next call fail with any `ApiException`.
- **Check:** Hitanshu's first widget test runs with no network.

### 2. Sample JSON (`docs/contracts/`)
- Every file listed in contract section 10, using the **track's** data: Okafor (PHY-009, eligible), Brennan (PHY-013, opt-in off), Shah (PHY-005, on shift), Suncrest = SYN-005, clock 18:20–18:30 on 17 March.
- `mobile_offers.json` has one offer in each physician-visible state, including `released`.
- `bad/` has one file each for: unknown role, unknown offer status, unknown outcome, missing required field, wrong type.
- **Check:** every file parses (or fails, for `bad/`) in a unit test.

### 3. DTOs and strict parsing
- Parse each field explicitly. Required field missing or `null` → `ParseError`. Unknown enum → `ParseError`. Nullable fields per the contract.
- Timestamps parse with their offset and stay as UTC `DateTime`; formatting to ET is the screens' job (give Hitanshu a `formatEt(DateTime)` helper in `data/time.dart`).
- **No-patient-data test:** offer, notification and action-result samples contain no `consult_id`, `consult_type` or patient-like keys.
- **Check:** unit tests for every schema and every `bad/` file.

### 4. API client
- Base URL from `--dart-define=API_BASE_URL`. `API_MODE=live|fake` (default `fake` so `main` always runs).
- Every request sends `Authorization: Bearer <token>`. Map errors by the contract's error shape: 401 → `Unauthorized` and fire `signedOut`; 403 → `Forbidden`; 404 → `NotFound`; 422 → `InvalidRequest(message)`; 503 → `Unavailable`; no response or timeout (10 s) → `NetworkError`; bad JSON → `ParseError`.
- Every response with `server_now` updates the `ServerClock` offset.
- **Check:** unit tests with a mock HTTP client for each status code.

### 5. `AuthRepository`
- `currentUser()`: read `token` and `offer` from `Uri.base` once; store the token in `sessionStorage`; remove both from the address bar with `history.replaceState`; keep `offer` in memory for `takeInitialOfferId()`. Then `GET /me`.
- `signIn(email, password)`: `POST /auth/login`, store the token, return `me`. A 401 here shows the server's message on the form instead of signing out.
- `signOut()`: clear `sessionStorage`, fire `signedOut`.
- `setOptIn`: `PUT /me/preferences`; return the `PreferencesResult` as-is (including `open_offer_exists`); refresh `/me` afterwards.
- **Check:** tests for URL token, stored token, no token, login success, login 401, any-call 401, and the `open_offer_exists` round trip.

### 6. Physician repositories
- `OfferRepository`: `/offers`, `/offers/{id}`, accept, decline, release, `/notifications`.
- `ShiftRepository`: `/me/shift`, `/me/schedule?week_start=` (Sunday of the week, `YYYY-MM-DD`).
- **Check:** parse all physician sample files; accept returns each outcome from the fakes.

### 7. `LeadRepository`
- All lead endpoints in contract section 3, including `/lead/coverage` and `/lead/schedule?date=`.
- Reject sends `{"reason"}`; an empty reason is a 422 from the server, so don't block it in the data layer.
- **Check:** parse all lead sample files; a 403 surfaces as `Forbidden`.

### 8. Server clock
- `offset = server_now − device time at receipt`, updated on every response. `now()` = device time + offset. `ticks` emits every second.
- **Check:** countdown is correct with the device clock set hours off.

### 9. Feeds and polling
| Feed | Calls | Interval |
| --- | --- | --- |
| `PhysicianFeed` | `/offers` + `/notifications` | 5 s while any offer is `sent`, else 15 s |
| `LeadFeed` | `/lead/queue` + `/lead/offers?active=true` | 5 s |

- Screens call `myShift()` (every 30 s while open), `coverage()` (every 15 s while open) and schedule calls themselves; give Hitanshu a small `Poller(interval, callback)` helper for those.
- Stop polling while `document.hidden`; refresh immediately on `visibilitychange` back to visible.
- `newOffer`: a `sent` offer whose ID wasn't in the previous poll. On first load, existing `sent` offers also emit once, so a phone opened by QR shows the lock screen.
- `offerChanged` / `answers`: compare each offer's `status` with the previous poll.
- A failed poll keeps the last good data and sets the error on the snapshot; the next success clears it.
- **Check:** unit tests with a fake timer for interval switching, hidden/visible, new-offer detection, and lead answer events.

### 10. Repeated-tap safety
- Accept, decline, release, approve, reject, authorize and opt-in: on `NetworkError`, retry once automatically, then let the user retry. The server returns the same result for a repeat (contract section 3), so retries are safe.
- **Check:** scripted test — first call times out after the server applied it, retry returns `applied: false` with the same `outcome`, the screen ends in the same state.

### 11. `WebAlerts` (`lib/web_alerts.dart`)
- `enableSound()` must be called from a tap (browsers block audio otherwise). Play a short bundled chime asset (`assets/chime.mp3`) with `HTMLAudioElement`.
- `vibrate()` uses `navigator.vibrate` (works on Android Chrome; silently does nothing on iPhone).
- `setBadge(n)` sets the title to "(n) New coverage request" and restores it at 0.
- **Check:** chime and vibration on an Android phone, title change on any phone.

### 12. Build and deploy
- `flutter build web --release --dart-define=API_MODE=live --dart-define=API_BASE_URL=https://<backend>`.
- Deploy `build/web` to Vercel as a static site with an SPA rewrite to `index.html`.
- Also deploy a **fake-mode** build to a second Vercel URL. It's the backup if the backend is down during judging.
- Send the live origin to the backend owner for the CORS allowed-origins list.
- **Check:** both links open on a phone over HTTPS; the live one signs in with a demo account.

### 13. Demo script (`docs/demo-mobile.md`)
- Follow contract section 11: four phones or browser windows (lead, Okafor, Brennan, Shah), sign-in emails, exact taps, what each screen should show, and the expiry run.
- Include a reset step (backend `/admin/reset`) and the fallback to the fake-mode URL.
- **Check:** rehearsed once end to end with Hitanshu.

## What you need from the backend owner

Send this list early; until each endpoint exists, the fakes cover it.

1. `POST /auth/login` and the four demo accounts (contract section 9), password `demo`.
2. `GET /me` with the v1.1 fields; `PUT /me/preferences`.
3. Physician: `/offers*` including release, `/notifications`, `/me/shift`, `/me/schedule`.
4. Lead: `/lead/queue`, `/proposals/*`, `/gaps/{id}/candidates|trap-check|audit`, `/lead/offers`, `/escalations/{id}/authorize`, `/lead/coverage`, `/lead/schedule`.
5. Broadcast behavior and repeat-safe actions (contract sections 4.5, 5.1).
6. CORS for the Vercel origin.
7. Running on the **track's** data for the demo (Okafor eligible, Brennan fails only R1).

## Timeline

| When | Task |
| --- | --- |
| Sat 3–4 PM | 1 (interface + fakes pushed), start 2 |
| Sat 4–8 PM | 2, 3, 4, 5 |
| Sat 8–11 PM | 6, 7, 8, 9; switch to live endpoints as they land |
| Sat 11 PM–2 AM | 10, 11, 12 |
| Sun 8–10 AM | 13, rehearsal with Hitanshu, code freeze |

## Done when
- All data tests pass; `bad/` files all fail to parse.
- Hitanshu's widget tests run on fakes with no network.
- Both Vercel URLs open on a phone; live mode completes the demo script.