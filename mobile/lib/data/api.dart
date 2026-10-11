// The interface Hitanshu's screens use. Screens import only this file (it
// re-exports the DTOs, exceptions, time helpers and Poller) and never write
// HTTP code. Contract: Mobile-App-Contract.md v1.1.
//
// Changes from the interface block in Mobile-Chandan.md / Mobile-Hitanshu.md:
//  * Feeds expose FeedState<T> instead of AsyncSnapshot<T>, because AsyncSnapshot
//    cannot hold last-good data AND an error at the same time, and the
//    "Reconnecting…" banner needs both (Hitanshu task 14).
//  * AuthRepository adds `me` (ValueListenable) and `refreshMe()`, so the weekly
//    count and opt-in switch stay current (contract section 7: GET /me every 60 s).
import 'dart:async';

import 'package:flutter/foundation.dart';

import 'models.dart';
import 'wiring.dart';

export 'exceptions.dart';
export 'json.dart' show formatDate;
export 'models.dart';
export 'poller.dart';
export 'time.dart';

abstract class AuthRepository {
  /// URL token → sessionStorage → GET /me; null if there is no session.
  Future<Me?> currentUser();

  /// POST /auth/login. A 401 throws [Unauthorized] with the server's message
  /// for the form; it does NOT fire [signedOut].
  Future<Me> signIn(String email, String password);

  Future<void> signOut();

  /// PUT /me/preferences, returned as-is (including `open_offer_exists`).
  Future<PreferencesResult> setOptIn(bool optIn, {bool declineOpenOffer = false});

  /// The `?offer=` value the app was opened with, returned once, then null.
  String? takeInitialOfferId();

  /// Fires on sign-out and on any 401 from any call.
  Stream<void> get signedOut;

  /// The signed-in user; updated by currentUser, signIn, setOptIn, refreshMe.
  ValueListenable<Me?> get me;

  /// GET /me. Call on start and every 60 s on physician screens (weekly count).
  Future<Me> refreshMe();
}

abstract class OfferRepository {
  Future<OfferList> listOffers();
  Future<Offer> getOffer(String offerId);
  Future<OfferActionResult> accept(String offerId);
  Future<OfferActionResult> decline(String offerId);
  Future<OfferActionResult> release(String offerId);

  /// GET /offers/{id}/audio: the server's spoken offer (MP3). Throws
  /// [Unavailable] when text-to-speech is off; show the offer text instead.
  Future<Uint8List> getOfferAudio(String offerId);
  Future<NotificationList> notifications();
}

abstract class ShiftRepository {
  Future<MyShift> myShift();

  /// [weekStart] is the Sunday (use etWeekStart(clock.now())).
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

  /// [date] is an ET calendar date (use etDate(clock.now())).
  Future<LeadSchedule> schedule(DateTime date);
}

/// Live data with last-good value, last error and loading flag together.
@immutable
class FeedState<T> {
  const FeedState({this.data, this.error, this.loading = false});
  const FeedState.loading() : this(loading: true);

  final T? data;

  /// The last poll's error, or null if the last poll succeeded.
  final Object? error;

  /// True only before the first result arrives.
  final bool loading;

  bool get hasData => data != null;

  /// Data is on screen but the last poll failed → show "Reconnecting…".
  bool get stale => data != null && error != null;
}

abstract class PhysicianFeed {
  ValueListenable<FeedState<OfferList>> get offers;
  ValueListenable<FeedState<NotificationList>> get notifications;

  /// A `sent` offer not seen before. On first load every `sent` offer emits
  /// once, so a phone opened from a QR code shows the lock screen.
  Stream<Offer> get newOffer;

  /// Any status change on an offer seen in the previous poll.
  Stream<Offer> get offerChanged;

  void start();
  void stop();
  Future<void> refreshNow();
}

abstract class LeadFeed {
  ValueListenable<FeedState<LeadQueue>> get queue;
  ValueListenable<FeedState<BroadcastList>> get activeOffers;

  /// A recipient's offer changed status (accepted, declined, expired, released…).
  Stream<AnswerEvent> get answers;

  void start();
  void stop();
  Future<void> refreshNow();
}

abstract class ServerClock {
  /// Device time corrected by server_now. Never use DateTime.now() in screens.
  DateTime now();

  /// Never negative.
  Duration remaining(DateTime until);

  /// Updates every second.
  ValueListenable<DateTime> get ticks;
}

abstract class WebAlerts {
  /// Call from a tap (browsers block audio otherwise).
  Future<void> enableSound();
  bool get soundEnabled;
  void chime();
  void vibrate();

  /// Loops the chime until [stopSound]. Silent until sound has been enabled.
  void startRing();

  /// Plays [mp3] once (the spoken offer), replacing any ring. Throws if the
  /// browser refuses to play it.
  Future<void> play(Uint8List mp3);

  /// Stops the ring or the spoken offer.
  void stopSound();

  /// "(n) New coverage request" in the tab title; 0 restores the title.
  void setBadge(int count);
}

/// One of everything. Build once in main.dart.
class AppServices {
  AppServices({
    required this.auth,
    required this.offers,
    required this.shifts,
    required this.lead,
    required this.physicianFeed,
    required this.leadFeed,
    required this.clock,
    required this.alerts,
    required this.isFake,
  });

  final AuthRepository auth;
  final OfferRepository offers;
  final ShiftRepository shifts;
  final LeadRepository lead;
  final PhysicianFeed physicianFeed;
  final LeadFeed leadFeed;
  final ServerClock clock;
  final WebAlerts alerts;

  /// True when running on FakeServices (show a small "Demo data" tag if you like).
  final bool isFake;

  /// Picks real or fake from lib/data/config.dart (AppConfig):
  ///   API_MODE=fake               everything fake (default; `main` always runs)
  ///   API_MODE=live, LIVE_REPOS=all   everything against API_BASE_URL
  ///   API_MODE=live, LIVE_REPOS=auth  live sign-in, the rest fake (switch repos
  ///     over one by one as the backend lands: auth,offers,shifts,lead)
  /// Run with: flutter run -d chrome --dart-define-from-file=config/fake.json
  factory AppServices.fromEnvironment() => buildServicesFromConfig();
}
