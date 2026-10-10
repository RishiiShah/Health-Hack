import 'dart:convert';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/live/client.dart';
import 'package:sevaro_mobile/data/clock.dart';
import 'package:sevaro_mobile/data/fake/fake_samples.g.dart';
import 'package:sevaro_mobile/data/fake/fakes.dart';
import 'package:sevaro_mobile/data/live/live.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';

class MemTokens implements TokenStore {
  String? t = 'tok';
  @override
  String? read() => t;
  @override
  void write(String token) => t = token;
  @override
  void clear() => t = null;
}

void main() {
  group('time', () {
    test('ET offset follows DST', () {
      expect(etOffset(DateTime.utc(2026, 3, 17, 22)), const Duration(hours: -4));
      expect(etOffset(DateTime.utc(2026, 1, 10, 12)), const Duration(hours: -5));
      expect(etOffset(DateTime.utc(2026, 3, 8, 6, 59)), const Duration(hours: -5));
      expect(etOffset(DateTime.utc(2026, 3, 8, 7)), const Duration(hours: -4));
      expect(etOffset(DateTime.utc(2026, 11, 1, 5, 59)), const Duration(hours: -4));
      expect(etOffset(DateTime.utc(2026, 11, 1, 6)), const Duration(hours: -5));
    });
    test('formatting', () {
      final t = DateTime.parse('2026-03-17T18:22:00-04:00');
      expect(formatEtHeader(t), 'Tue 17 Mar · 18:22 ET');
      expect(formatDate(etWeekStart(t)), '2026-03-15');
      expect(formatCountdown(const Duration(minutes: 9, seconds: 5)), '9:05');
      expect(formatHoursMinutes(const Duration(hours: 1, minutes: 36)), '1 h 36 min');
      expect(isoEt(t.toUtc()), '2026-03-17T18:22:00-04:00');
    });
  });

  group('server clock', () {
    test('countdown is right with the device clock hours off', () {
      var device = DateTime.utc(2030, 1, 1, 3); // wildly wrong
      final clock = OffsetServerClock(deviceNow: () => device, ticking: false);
      clock.observe(DateTime.parse('2026-03-17T18:25:00-04:00'));
      final expires = DateTime.parse('2026-03-17T18:35:00-04:00');
      expect(clock.remaining(expires), const Duration(minutes: 10));
      device = device.add(const Duration(minutes: 4));
      expect(clock.remaining(expires), const Duration(minutes: 6));
      device = device.add(const Duration(hours: 1));
      expect(clock.remaining(expires), Duration.zero);
    });
  });

  group('ApiClient', () {
    Future<Object> call(int status, String body, {List<bool>? unauthorized}) async {
      final clock = OffsetServerClock(ticking: false);
      final c = ApiClient(
        baseUrl: Uri.parse('https://api.example/'),
        tokens: MemTokens(),
        clock: clock,
        onUnauthorized: () => unauthorized?.add(true),
        httpClient: MockClient((req) async {
          expect(req.headers['Authorization'], 'Bearer tok');
          return http.Response(body, status, headers: {'content-type': 'application/json'});
        }),
      );
      try {
        return await c.get('/me', Me.parse);
      } on ApiException catch (e) {
        return e;
      }
    }

    test('200 parses and updates the clock', () async {
      expect(await call(200, kSamples['mobile_me_physician.json']!), isA<Me>());
    });
    test('401 → Unauthorized and signs out', () async {
      final fired = <bool>[];
      expect(await call(401, kSamples['mobile_error_401.json']!, unauthorized: fired), isA<Unauthorized>());
      expect(fired, [true]);
    });
    test('403 → Forbidden', () async => expect(await call(403, kSamples['mobile_error_403.json']!), isA<Forbidden>()));
    test('404 → NotFound', () async => expect(await call(404, '{}'), isA<NotFound>()));
    test('422 → InvalidRequest with message', () async {
      final e = await call(422, jsonEncode({'error': {'code': 'invalid_request', 'message': 'Reason required'}}));
      expect(e, isA<InvalidRequest>().having((e) => e.message, 'message', 'Reason required'));
    });
    test('503 → Unavailable', () async => expect(await call(503, ''), isA<Unavailable>()));
    test('bad JSON → ParseError', () async => expect(await call(200, '<html>'), isA<ParseError>()));
    test('missing field → ParseError', () async => expect(await call(200, '{"role":"physician"}'), isA<ParseError>()));
    test('no response → NetworkError', () async {
      final c = ApiClient(
        baseUrl: Uri.parse('https://api.example'),
        tokens: MemTokens(),
        clock: OffsetServerClock(ticking: false),
        onUnauthorized: () {},
        httpClient: MockClient((_) async => throw http.ClientException('down')),
      );
      expect(() => c.get('/me', Me.parse), throwsA(isA<NetworkError>()));
    });
    test('retry after a timeout that the server applied gives the same outcome', () async {
      var calls = 0;
      final accepted = jsonDecode(kSamples['mobile_offer_accept_accepted.json']!) as Map<String, dynamic>;
      final c = ApiClient(
        baseUrl: Uri.parse('https://api.example'),
        tokens: MemTokens(),
        clock: OffsetServerClock(ticking: false),
        onUnauthorized: () {},
        httpClient: MockClient((_) async {
          calls++;
          if (calls == 1) throw http.ClientException('timeout'); // server applied it
          return http.Response(jsonEncode({...accepted, 'applied': false}), 200);
        }),
      );
      final r = await LiveOfferRepository(c).accept('OFF-0007');
      expect(calls, 2);
      expect(r.outcome, OfferOutcome.accepted);
      expect(r.applied, isFalse);
    });
  });

  group('live auth', () {
    test('URL token is stored, removed from the address bar, offer kept once', () async {
      final browser = MemoryBrowser(initialUri: Uri.parse('https://app.example/?token=abc&offer=OFF-0007&x=1'));
      final services = LiveServices.create(Uri.parse('https://api.example'),
          browser: browser,
          httpClient: MockClient((req) async {
            expect(req.headers['Authorization'], 'Bearer abc');
            return http.Response(kSamples['mobile_me_physician.json']!, 200);
          }));
      final me = await services.auth.currentUser();
      expect(me?.physicianId, 'PHY-009');
      expect(browser.currentUri.queryParameters, {'x': '1'});
      expect(services.auth.takeInitialOfferId(), 'OFF-0007');
      expect(services.auth.takeInitialOfferId(), isNull);
    });
    test('no token → null without a request', () async {
      final services = LiveServices.create(Uri.parse('https://api.example'),
          browser: MemoryBrowser(), httpClient: MockClient((_) async => fail('no request expected')));
      expect(await services.auth.currentUser(), isNull);
    });
    test('login 401 shows the message and does not fire signedOut', () async {
      final services = LiveServices.create(Uri.parse('https://api.example'),
          browser: MemoryBrowser(),
          httpClient: MockClient((_) async => http.Response(kSamples['mobile_error_401.json']!, 401)));
      var signedOut = false;
      services.auth.signedOut.listen((_) => signedOut = true);
      await expectLater(services.auth.signIn('x@y', 'z'),
          throwsA(isA<Unauthorized>().having((e) => e.message, 'message', 'Wrong email or password.')));
      await Future<void>.delayed(Duration.zero);
      expect(signedOut, isFalse);
    });
  });

  group('fakes', () {
    late FakeServices fake;
    setUp(() => fake = FakeServices(ticking: false, browser: MemoryBrowser(), autoAnswer: false));
    tearDown(() => fake.dispose());

    test('accept, then a retry of the same accept', () async {
      await fake.signInAs('okafor');
      final s = fake.services;
      final first = await s.offers.accept('OFF-0007');
      expect((first.outcome, first.applied), (OfferOutcome.accepted, true));
      final again = await s.offers.accept('OFF-0007');
      expect((again.outcome, again.applied), (OfferOutcome.accepted, false));
      expect(again.offer.allows(OfferAction.release), isTrue);
    });

    test('expired offer → expired outcome', () async {
      await fake.signInAs('okafor');
      fake.clock.set(DateTime.parse('2026-03-17T18:35:00-04:00'));
      final r = await fake.services.offers.accept('OFF-0007');
      expect(r.outcome, OfferOutcome.expired);
    });

    test('filled by another → already_filled', () async {
      await fake.signInAs('okafor');
      fake.offers.fillByOther('OFF-0007');
      expect((await fake.services.offers.accept('OFF-0007')).outcome, OfferOutcome.alreadyFilled);
    });

    test('opt out with an open offer asks first', () async {
      await fake.signInAs('okafor');
      final r = await fake.services.auth.setOptIn(false);
      expect(r.outcome, PreferencesOutcome.openOfferExists);
      expect(r.openOfferId, 'OFF-0007');
      final r2 = await fake.services.auth.setOptIn(false, declineOpenOffer: true);
      expect(r2.outcome, PreferencesOutcome.updated);
      expect(r2.me.splitShiftOptIn, isFalse);
    });

    test('Brennan opting in makes her a second recipient', () async {
      await fake.signInAs('brennan');
      await fake.services.auth.setOptIn(true);
      await fake.signInAs('lead');
      final p = await fake.services.lead.proposal('PRP-0003');
      expect(p.recipients.map((r) => r.physicianId), ['PHY-009', 'PHY-013']);
      expect(p.excluded.map((e) => e.physicianId), isNot(contains('PHY-013')));
    });

    test('lead endpoints are forbidden for physicians', () async {
      await fake.signInAs('okafor');
      expect(() => fake.services.lead.queue(), throwsA(isA<Forbidden>()));
    });

    test('failNext throws once', () async {
      await fake.signInAs('okafor');
      fake.failNext(const NetworkError());
      await expectLater(fake.services.offers.listOffers(), throwsA(isA<NetworkError>()));
      expect(await fake.services.offers.listOffers(), isA<OfferList>());
    });
  });

  group('feeds', () {
    test('new offer on first load, interval switching, hidden pauses, answers', () {
      fakeAsync((async) {
        final browser = MemoryBrowser();
        final fake = FakeServices(ticking: false, browser: browser, autoAnswer: false);
        fake.signInAs('okafor');
        async.flushMicrotasks();

        final feed = fake.services.physicianFeed;
        final newOffers = <String>[];
        final changed = <OfferStatus>[];
        feed.newOffer.listen((o) => newOffers.add(o.offerId));
        feed.offerChanged.listen((o) => changed.add(o.status));
        var polls = 0;
        feed.offers.addListener(() => polls++);

        feed.start();
        async.flushMicrotasks();
        expect(newOffers, ['OFF-0007']); // existing sent offer emits once
        expect(feed.offers.value.data!.anySent, isTrue);

        polls = 0;
        async.elapse(const Duration(seconds: 5)); // fast interval while sent
        expect(polls, 1);

        fake.offers.expire('OFF-0007');
        async.elapse(const Duration(seconds: 5));
        expect(changed, [OfferStatus.expired]);

        polls = 0;
        async.elapse(const Duration(seconds: 5)); // now slow: nothing yet
        expect(polls, 0);
        async.elapse(const Duration(seconds: 10));
        expect(polls, 1);

        browser.hidden = true;
        polls = 0;
        async.elapse(const Duration(minutes: 1));
        expect(polls, 0);
        browser.hidden = false;
        async.flushMicrotasks();
        expect(polls, 1);

        fake.offers.pushNewOffer();
        feed.refreshNow();
        async.flushMicrotasks();
        expect(newOffers.length, 2);

        fake.failNext(const NetworkError());
        feed.refreshNow();
        async.flushMicrotasks();
        expect(feed.offers.value.stale, isTrue);
        feed.refreshNow();
        async.flushMicrotasks();
        expect(feed.offers.value.error, isNull);

        feed.stop();
        fake.dispose();
      });
    });

    test('lead sees an answer event when a recipient accepts', () {
      fakeAsync((async) {
        final fake = FakeServices(ticking: false, browser: MemoryBrowser(), autoAnswer: true);
        fake.signInAs('lead');
        async.flushMicrotasks();
        final feed = fake.services.leadFeed;
        final answers = <AnswerEvent>[];
        feed.answers.listen(answers.add);
        feed.start();
        async.flushMicrotasks();
        fake.services.lead.approve('PRP-0003');
        async.flushMicrotasks();
        feed.refreshNow();
        async.flushMicrotasks();
        fake.clock.advance(const Duration(seconds: 20)); // auto-answer fires on next request
        async.elapse(const Duration(seconds: 5));
        expect(answers.single.status, OfferStatus.accepted);
        expect(answers.single.offer.displayName, 'Dr. Grace Okafor');
        feed.stop();
        fake.dispose();
      });
    });
  });
}
