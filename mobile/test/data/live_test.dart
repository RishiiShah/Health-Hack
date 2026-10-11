// Live repositories against a mock HTTP client: every endpoint in contract
// section 3 (method, path, query, body), plus the auth behaviors of task 5.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fake_samples.g.dart';
import 'package:sevaro_mobile/data/live/live.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';

const _api = 'https://api.example';

/// Answers each request with a canned response and records what was sent.
class _Server {
  final requests = <http.Request>[];
  final _routes = <String, List<http.Response>>{};

  void on(String route, String sample, {int status = 200}) =>
      onResponse(route, http.Response(sample, status, headers: {'content-type': 'application/json'}));

  /// Responses are used in order; the last one repeats.
  void onResponse(String route, http.Response r) => (_routes[route] ??= []).add(r);

  String last(String route) => requests.lastWhere((r) => '${r.method} ${r.url.path}' == route).body;

  Future<http.Response> handle(http.BaseRequest req) async {
    final r = req as http.Request;
    requests.add(r);
    final key = '${r.method} ${r.url.path}';
    final list = _routes[key];
    if (list == null) fail('unexpected request: $key');
    return list.length > 1 ? list.removeAt(0) : list.first;
  }

  AppServices services({MemoryBrowser? browser}) =>
      LiveServices.create(Uri.parse(_api), browser: browser ?? MemoryBrowser(), httpClient: MockClient(handle));
}

String _offer(String status) {
  final offers = jsonDecode(kSamples['mobile_offers.json']!)['offers'] as List;
  return jsonEncode(offers.firstWhere((o) => o['status'] == status));
}

MemoryBrowser _signedIn([String token = 'stored']) => MemoryBrowser()..session['sevaro_token'] = token;

void main() {
  group('endpoints match contract section 3', () {
    // Each case: the call, then "METHOD /path?query" the server must see.
    final cases = <(String, String, String, Future<Object?> Function(AppServices))>[
      ('GET /me', 'mobile_me_physician.json', 'GET /me', (s) => s.auth.refreshMe()),
      ('GET /offers', 'mobile_offers.json', 'GET /offers', (s) => s.offers.listOffers()),
      ('GET /offers/{id}', 'OFFER', 'GET /offers/OFF-0007', (s) => s.offers.getOffer('OFF-0007')),
      ('POST accept', 'mobile_offer_accept_accepted.json', 'POST /offers/OFF-0007/accept',
          (s) => s.offers.accept('OFF-0007')),
      ('POST decline', 'mobile_offer_decline_declined.json', 'POST /offers/OFF-0007/decline',
          (s) => s.offers.decline('OFF-0007')),
      ('POST release', 'mobile_offer_release_released.json', 'POST /offers/OFF-0005/release',
          (s) => s.offers.release('OFF-0005')),
      ('GET /notifications', 'mobile_notifications.json', 'GET /notifications',
          (s) => s.offers.notifications()),
      ('GET /me/shift', 'mobile_shift_on.json', 'GET /me/shift', (s) => s.shifts.myShift()),
      ('GET /me/schedule', 'mobile_schedule.json', 'GET /me/schedule?week_start=2026-03-15',
          (s) => s.shifts.mySchedule(DateTime.utc(2026, 3, 15))),
      ('GET /lead/queue', 'mobile_lead_queue.json', 'GET /lead/queue', (s) => s.lead.queue()),
      ('GET /proposals/{id}', 'mobile_proposal.json', 'GET /proposals/PRP-0003',
          (s) => s.lead.proposal('PRP-0003')),
      ('POST approve', 'mobile_proposal_approved.json', 'POST /proposals/PRP-0003/approve',
          (s) => s.lead.approve('PRP-0003')),
      ('POST reject', 'mobile_proposal_approved.json', 'POST /proposals/PRP-0003/reject',
          (s) => s.lead.reject('PRP-0003', 'Not now')),
      ('GET candidates', 'mobile_candidates.json', 'GET /gaps/GAP-SYN-005-1900/candidates',
          (s) => s.lead.candidates('GAP-SYN-005-1900')),
      ('GET trap-check', 'mobile_trap_check.json', 'GET /gaps/GAP-SYN-005-1900/trap-check',
          (s) => s.lead.trapCheck('GAP-SYN-005-1900')),
      ('GET audit', 'mobile_audit.json', 'GET /gaps/GAP-SYN-005-1900/audit',
          (s) => s.lead.audit('GAP-SYN-005-1900')),
      ('GET /lead/offers', 'mobile_lead_offers.json', 'GET /lead/offers?active=true',
          (s) => s.lead.activeOffers()),
      ('POST authorize', 'ESCALATION_RESULT', 'POST /escalations/ESC-0002/authorize',
          (s) => s.lead.authorize('ESC-0002')),
      ('GET /lead/coverage', 'mobile_lead_coverage.json', 'GET /lead/coverage', (s) => s.lead.coverage()),
      ('GET /lead/schedule', 'mobile_lead_schedule.json', 'GET /lead/schedule?date=2026-03-17',
          (s) => s.lead.schedule(DateTime.utc(2026, 3, 17))),
    ];

    for (final (name, sample, expected, call) in cases) {
      test(name, () async {
        final server = _Server();
        final body = switch (sample) {
          'OFFER' => _offer('sent'),
          'ESCALATION_RESULT' => jsonEncode({
              'outcome': 'authorized',
              'applied': true,
              'escalation': jsonDecode(kSamples['mobile_escalation.json']!),
              'server_now': '2026-03-17T18:22:00-04:00',
            }),
          _ => kSamples[sample]!,
        };
        final route = expected.split('?').first;
        server.on(route, body);
        await call(server.services(browser: _signedIn()));
        final sent = server.requests.single;
        expect('${sent.method} ${sent.url.path}${sent.url.hasQuery ? '?${sent.url.query}' : ''}', expected);
        expect(sent.headers['Authorization'], 'Bearer stored');
      });
    }

    test('reject sends {"reason"}, an empty reason is not blocked, and a 422 surfaces', () async {
      final server = _Server()
        ..on('POST /proposals/PRP-0003/reject',
            jsonEncode({'error': {'code': 'invalid_request', 'message': 'A reason is required.'}}),
            status: 422);
      final s = server.services(browser: _signedIn());
      await expectLater(s.lead.reject('PRP-0003', ''),
          throwsA(isA<InvalidRequest>().having((e) => e.message, 'message', 'A reason is required.')));
      expect(jsonDecode(server.last('POST /proposals/PRP-0003/reject')), {'reason': ''});
    });

    test('preferences body carries both flags', () async {
      final server = _Server()..on('PUT /me/preferences', kSamples['mobile_preferences_updated.json']!);
      server.on('GET /me', kSamples['mobile_me_physician.json']!);
      await server.services(browser: _signedIn()).auth.setOptIn(true);
      expect(jsonDecode(server.last('PUT /me/preferences')),
          {'split_shift_opt_in': true, 'decline_open_offer': false});
    });
  });

  group('auth', () {
    test('URL token with no other query parameter leaves nothing in the address bar', () async {
      final browser = MemoryBrowser(initialUri: Uri.parse('https://app.example/?token=abc#/home'));
      final server = _Server()..on('GET /me', kSamples['mobile_me_physician.json']!);
      await server.services(browser: browser).auth.currentUser();
      expect(browser.currentUri.toString(), 'https://app.example/#/home');
      expect(browser.session['sevaro_token'], 'abc');
      expect(server.requests.single.headers['Authorization'], 'Bearer abc');
    });

    test('URL offer without a token is kept and removed from the address bar', () async {
      final browser = MemoryBrowser(initialUri: Uri.parse('https://app.example:8080/?offer=OFF-0007'))
        ..session['sevaro_token'] = 'stored';
      final services = _Server().services(browser: browser);
      expect(services.auth.takeInitialOfferId(), 'OFF-0007');
      expect(browser.currentUri.toString(), 'https://app.example:8080/');
    });

    test('stored token is used when the URL has none', () async {
      final server = _Server()..on('GET /me', kSamples['mobile_me_physician.json']!);
      final me = await server.services(browser: _signedIn('from-session')).auth.currentUser();
      expect(me?.physicianId, 'PHY-009');
      expect(server.requests.single.headers['Authorization'], 'Bearer from-session');
    });

    test('no token → null, and no Authorization header is ever sent', () async {
      final server = _Server()..on('POST /auth/login', kSamples['mobile_login.json']!);
      final s = server.services();
      expect(await s.auth.currentUser(), isNull);
      await s.auth.signIn('okafor@demo.sevaro', 'demo');
      expect(server.requests.single.headers.containsKey('Authorization'), isFalse);
    });

    test('login success stores only the token and returns me', () async {
      final browser = MemoryBrowser();
      final server = _Server()..on('POST /auth/login', kSamples['mobile_login.json']!);
      final me = await server.services(browser: browser).auth.signIn('okafor@demo.sevaro', 'demo');
      expect(me.userId, 'okafor@demo.sevaro');
      expect(jsonDecode(server.last('POST /auth/login')), {'email': 'okafor@demo.sevaro', 'password': 'demo'});
      expect(browser.session.keys, ['sevaro_token']);
      expect(browser.session['sevaro_token'], jsonDecode(kSamples['mobile_login.json']!)['token']);
    });

    test('a 401 from any call fires signedOut and clears the token', () async {
      final browser = _signedIn();
      final server = _Server()..on('GET /offers', kSamples['mobile_error_401.json']!, status: 401);
      final s = server.services(browser: browser);
      var fired = 0;
      s.auth.signedOut.listen((_) => fired++);
      await expectLater(s.offers.listOffers(), throwsA(isA<Unauthorized>()));
      await Future<void>.delayed(Duration.zero);
      expect(fired, 1);
      expect(browser.session, isEmpty);
      expect(s.auth.me.value, isNull);
    });

    test('a stale stored token → currentUser is null and signedOut fires', () async {
      final server = _Server()..on('GET /me', kSamples['mobile_error_401.json']!, status: 401);
      final s = server.services(browser: _signedIn());
      var fired = 0;
      s.auth.signedOut.listen((_) => fired++);
      expect(await s.auth.currentUser(), isNull);
      await Future<void>.delayed(Duration.zero);
      expect(fired, 1);
    });

    test('signOut clears the session and fires signedOut', () async {
      final browser = _signedIn();
      final s = _Server().services(browser: browser);
      var fired = 0;
      s.auth.signedOut.listen((_) => fired++);
      await s.auth.signOut();
      await Future<void>.delayed(Duration.zero);
      expect(browser.session, isEmpty);
      expect(fired, 1);
    });

    test('open_offer_exists round trip: ask, then resend with decline_open_offer', () async {
      final server = _Server()
        ..on('PUT /me/preferences', kSamples['mobile_preferences_open_offer.json']!)
        ..on('PUT /me/preferences', kSamples['mobile_preferences_updated.json']!)
        ..on('GET /me', kSamples['mobile_me_physician.json']!);
      final auth = server.services(browser: _signedIn()).auth;

      final first = await auth.setOptIn(false);
      expect((first.outcome, first.applied, first.openOfferId),
          (PreferencesOutcome.openOfferExists, false, 'OFF-0007'));
      final second = await auth.setOptIn(false, declineOpenOffer: true);
      expect((second.outcome, second.applied), (PreferencesOutcome.updated, true));

      final puts = server.requests.where((r) => r.method == 'PUT').map((r) => jsonDecode(r.body)).toList();
      expect(puts, [
        {'split_shift_opt_in': false, 'decline_open_offer': false},
        {'split_shift_opt_in': false, 'decline_open_offer': true},
      ]);
      expect(auth.me.value, isNotNull);
    });
  });

  group('permissions', () {
    test('a 403 on any lead endpoint surfaces as Forbidden and does not sign out', () async {
      final server = _Server()
        ..on('GET /lead/queue', kSamples['mobile_error_403.json']!, status: 403)
        ..on('POST /proposals/PRP-0003/approve', kSamples['mobile_error_403.json']!, status: 403);
      final browser = _signedIn();
      final s = server.services(browser: browser);
      var fired = 0;
      s.auth.signedOut.listen((_) => fired++);
      await expectLater(s.lead.queue(), throwsA(isA<Forbidden>()));
      await expectLater(
          s.lead.approve('PRP-0003'),
          throwsA(isA<Forbidden>().having(
              (e) => e.message, 'message', 'Only the clinical lead on duty can approve offers.')));
      await Future<void>.delayed(Duration.zero);
      expect(fired, 0);
      expect(browser.session['sevaro_token'], 'stored');
    });

    test('a 404 and a 503 map to NotFound and Unavailable', () async {
      final server = _Server()
        ..on('GET /offers/OFF-9', '{"error":{"code":"not_found","message":"x"}}', status: 404)
        ..on('GET /offers', '', status: 503);
      final s = server.services(browser: _signedIn());
      await expectLater(s.offers.getOffer('OFF-9'), throwsA(isA<NotFound>()));
      await expectLater(s.offers.listOffers(), throwsA(isA<Unavailable>()));
    });
  });
}
