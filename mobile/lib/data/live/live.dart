import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../../web_alerts.dart';
import '../api.dart';
import 'client.dart';
import '../clock.dart';
import '../feeds.dart';
import '../platform/browser.dart';

const _tokenKey = 'sevaro_token';

class SessionTokenStore implements TokenStore {
  SessionTokenStore(this._browser);
  final Browser _browser;

  @override
  String? read() => _browser.readSession(_tokenKey);
  @override
  void write(String token) => _browser.writeSession(_tokenKey, token);
  @override
  void clear() => _browser.removeSession(_tokenKey);
}

class LiveAuthRepository implements AuthRepository {
  LiveAuthRepository(this._client, this._tokens, this._browser);

  final ApiClient _client;
  final TokenStore _tokens;
  final Browser _browser;
  final _signedOut = StreamController<void>.broadcast();
  final _me = ValueNotifier<Me?>(null);
  bool _urlRead = false;
  String? _initialOfferId;

  /// Wired to ApiClient.onUnauthorized.
  void handleUnauthorized() {
    _me.value = null;
    _signedOut.add(null);
  }

  void _readUrlOnce() {
    if (_urlRead) return;
    _urlRead = true;
    final uri = _browser.initialUri;
    final token = uri.queryParameters['token'];
    final offer = uri.queryParameters['offer'];
    if (token != null && token.isNotEmpty) _tokens.write(token);
    if (offer != null && offer.isNotEmpty) _initialOfferId = offer;
    if (token != null || offer != null) {
      final rest = Map<String, String>.of(uri.queryParameters)
        ..remove('token')
        ..remove('offer');
      _browser.replaceUrl(_withQuery(uri, rest));
    }
  }

  /// Uri.replace(queryParameters: null) keeps the old query, so an address
  /// with only `?token=` would keep the token. Build the address afresh.
  Uri _withQuery(Uri uri, Map<String, String> query) => Uri(
        scheme: uri.scheme,
        userInfo: uri.userInfo.isEmpty ? null : uri.userInfo,
        host: uri.host,
        port: uri.hasPort ? uri.port : null,
        path: uri.path,
        queryParameters: query.isEmpty ? null : query,
        fragment: uri.fragment.isEmpty ? null : uri.fragment,
      );

  @override
  Future<Me?> currentUser() async {
    _readUrlOnce();
    if (_tokens.read() == null) return null;
    try {
      return await refreshMe();
    } on Unauthorized {
      return null; // token cleared and signedOut fired by the client
    }
  }

  @override
  Future<Me> refreshMe() async {
    final me = await _client.get('/me', Me.parse);
    _me.value = me;
    return me;
  }

  @override
  Future<Me> signIn(String email, String password) async {
    final r = await _client.post('/auth/login', LoginResult.parse,
        body: {'email': email, 'password': password}, signOutOn401: false);
    _tokens.write(r.token);
    _me.value = r.me;
    return r.me;
  }

  @override
  Future<void> signOut() async {
    _tokens.clear();
    _me.value = null;
    _signedOut.add(null);
  }

  @override
  Future<PreferencesResult> setOptIn(bool optIn, {bool declineOpenOffer = false}) async {
    final r = await retryOnceOnNetwork(() => _client.put('/me/preferences', PreferencesResult.parse,
        body: {'split_shift_opt_in': optIn, 'decline_open_offer': declineOpenOffer}));
    _me.value = r.me;
    unawaited(refreshMe().then((_) {}, onError: (_) {}));
    return r;
  }

  @override
  String? takeInitialOfferId() {
    _readUrlOnce();
    final id = _initialOfferId;
    _initialOfferId = null;
    return id;
  }

  @override
  Stream<void> get signedOut => _signedOut.stream;

  @override
  ValueListenable<Me?> get me => _me;
}

class LiveOfferRepository implements OfferRepository {
  LiveOfferRepository(this._c);
  final ApiClient _c;

  String _id(String id) => Uri.encodeComponent(id);

  @override
  Future<OfferList> listOffers() => _c.get('/offers', OfferList.parse);
  @override
  Future<Offer> getOffer(String offerId) => _c.get('/offers/${_id(offerId)}', Offer.parse);
  @override
  Future<OfferActionResult> accept(String offerId) =>
      retryOnceOnNetwork(() => _c.post('/offers/${_id(offerId)}/accept', OfferActionResult.parse));
  @override
  Future<OfferActionResult> decline(String offerId) =>
      retryOnceOnNetwork(() => _c.post('/offers/${_id(offerId)}/decline', OfferActionResult.parse));
  @override
  Future<OfferActionResult> release(String offerId) =>
      retryOnceOnNetwork(() => _c.post('/offers/${_id(offerId)}/release', OfferActionResult.parse));
  @override
  Future<Uint8List> getOfferAudio(String offerId) => _c.getBytes('/offers/${_id(offerId)}/audio');
  @override
  Future<NotificationList> notifications() => _c.get('/notifications', NotificationList.parse);
}

class LiveShiftRepository implements ShiftRepository {
  LiveShiftRepository(this._c);
  final ApiClient _c;

  @override
  Future<MyShift> myShift() => _c.get('/me/shift', MyShift.parse);
  @override
  Future<MySchedule> mySchedule(DateTime weekStart) =>
      _c.get('/me/schedule', MySchedule.parse, query: {'week_start': formatDate(weekStart)});
}

class LiveLeadRepository implements LeadRepository {
  LiveLeadRepository(this._c);
  final ApiClient _c;

  String _id(String id) => Uri.encodeComponent(id);

  @override
  Future<LeadQueue> queue() => _c.get('/lead/queue', LeadQueue.parse);
  @override
  Future<Proposal> proposal(String proposalId) => _c.get('/proposals/${_id(proposalId)}', Proposal.parse);
  @override
  Future<ProposalActionResult> approve(String proposalId) => retryOnceOnNetwork(
      () => _c.post('/proposals/${_id(proposalId)}/approve', ProposalActionResult.parse));
  @override
  Future<ProposalActionResult> reject(String proposalId, String reason) => retryOnceOnNetwork(() =>
      _c.post('/proposals/${_id(proposalId)}/reject', ProposalActionResult.parse, body: {'reason': reason}));
  @override
  Future<CandidateList> candidates(String gapId) => _c.get('/gaps/${_id(gapId)}/candidates', CandidateList.parse);
  @override
  Future<TrapCheck> trapCheck(String gapId) => _c.get('/gaps/${_id(gapId)}/trap-check', TrapCheck.parse);
  @override
  Future<AuditLog> audit(String gapId) => _c.get('/gaps/${_id(gapId)}/audit', AuditLog.parse);
  @override
  Future<BroadcastList> activeOffers() =>
      _c.get('/lead/offers', BroadcastList.parse, query: {'active': 'true'});
  @override
  Future<EscalationActionResult> authorize(String escalationId) => retryOnceOnNetwork(
      () => _c.post('/escalations/${_id(escalationId)}/authorize', EscalationActionResult.parse));
  @override
  Future<CoverageBoard> coverage() => _c.get('/lead/coverage', CoverageBoard.parse);
  @override
  Future<LeadSchedule> schedule(DateTime date) =>
      _c.get('/lead/schedule', LeadSchedule.parse, query: {'date': formatDate(date)});
}

class LiveServices {
  static AppServices create(Uri baseUrl, {http.Client? httpClient, Browser? browser}) {
    final b = browser ?? sharedBrowser;
    final tokens = SessionTokenStore(b);
    final clock = OffsetServerClock();
    late final LiveAuthRepository auth;
    final client = ApiClient(
      baseUrl: baseUrl,
      tokens: tokens,
      clock: clock,
      httpClient: httpClient,
      onUnauthorized: () => auth.handleUnauthorized(),
    );
    auth = LiveAuthRepository(client, tokens, b);
    final offers = LiveOfferRepository(client);
    final lead = LiveLeadRepository(client);
    final physicianFeed = PollingPhysicianFeed(offers, browser: b);
    final leadFeed = PollingLeadFeed(lead, browser: b);
    auth.signedOut.listen((_) {
      physicianFeed.stop();
      leadFeed.stop();
    });
    return AppServices(
      auth: auth,
      offers: offers,
      shifts: LiveShiftRepository(client),
      lead: lead,
      physicianFeed: physicianFeed,
      leadFeed: leadFeed,
      clock: clock,
      alerts: createWebAlerts(),
      isFake: false,
    );
  }
}
