// Task 9 (lead feed timing) and task 10 (retry once on NetworkError).
import 'dart:convert';

import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fake_samples.g.dart';
import 'package:sevaro_mobile/data/fake/fakes.dart';
import 'package:sevaro_mobile/data/live/live.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';

void main() {
  group('lead feed timing', () {
    /// Runs [body] with a signed-in lead feed and a counter of completed polls.
    void withLeadFeed(
      void Function(
        FakeAsync async,
        LeadFeed feed,
        MemoryBrowser browser,
        FakeServices fake,
        int Function() polls,
      )
      body,
    ) {
      fakeAsync((async) {
        final browser = MemoryBrowser();
        final fake = FakeServices(
          ticking: false,
          browser: browser,
          autoAnswer: false,
        );
        fake.signInAs('lead');
        async.flushMicrotasks();
        final feed = fake.services.leadFeed;
        var polls = 0;
        feed.queue.addListener(() => polls++);
        body(async, feed, browser, fake, () => polls);
        feed.stop();
        fake.dispose();
      });
    }

    test('polls on start, then every 5 s', () {
      withLeadFeed((async, feed, _, _, polls) {
        feed.start();
        async.flushMicrotasks();
        expect(polls(), 1);
        async.elapse(const Duration(seconds: 4));
        expect(polls(), 1);
        async.elapse(const Duration(seconds: 1));
        expect(polls(), 2);
        async.elapse(const Duration(seconds: 10));
        expect(polls(), 4); // the interval does not change with the data
      });
    });

    test(
      'pauses while hidden and refreshes immediately when visible again',
      () {
        withLeadFeed((async, feed, browser, _, polls) {
          feed.start();
          async.flushMicrotasks();
          expect(polls(), 1);

          browser.hidden = true;
          async.elapse(const Duration(minutes: 2));
          expect(polls(), 1); // nothing while hidden

          browser.hidden = false; // no waiting for the next 5 s tick
          async.flushMicrotasks();
          expect(polls(), 2);

          async.elapse(
            const Duration(seconds: 5),
          ); // and the 5 s cadence resumes
          expect(polls(), 3);
        });
      },
    );

    test('hidden during a poll does not schedule the next one', () {
      withLeadFeed((async, feed, browser, _, polls) {
        feed.start();
        browser.hidden = true; // poll is in flight
        async.flushMicrotasks();
        async.elapse(const Duration(seconds: 30));
        expect(polls(), 1);
      });
    });

    test('stop() ends polling', () {
      withLeadFeed((async, feed, _, _, polls) {
        feed.start();
        async.flushMicrotasks();
        feed.stop();
        async.elapse(const Duration(minutes: 1));
        expect(polls(), 1 + 1); // +1: stop() resets the state to loading
      });
    });

    test(
      'a failed poll keeps the last data and the next success clears the error',
      () {
        withLeadFeed((async, feed, _, fake, _) {
          feed.start();
          async.flushMicrotasks();
          final good = feed.queue.value.data;
          expect(good, isNotNull);

          fake.failNext(const NetworkError());
          async.elapse(const Duration(seconds: 5));
          expect(feed.queue.value.stale, isTrue);
          expect(feed.queue.value.data, same(good));

          async.elapse(const Duration(seconds: 5));
          expect(feed.queue.value.error, isNull);
          expect(feed.queue.value.stale, isFalse);
        });
      },
    );
  });

  group('retry once on NetworkError', () {
    /// A server that applied the first request but whose reply never arrived.
    /// The first call throws; later calls return [repeat] (the server's
    /// "same result, applied: false" for a repeat).
    (AppServices, List<http.Request>) lostReply(
      String repeat, {
      bool alwaysFail = false,
    }) {
      final seen = <http.Request>[];
      final services = LiveServices.create(
        Uri.parse('https://api.example'),
        browser: MemoryBrowser()..session['sevaro_token'] = 't',
        httpClient: MockClient((req) async {
          seen.add(req);
          if (alwaysFail || seen.length == 1) {
            throw http.ClientException('timeout');
          }
          if (req.method == 'GET') {
            return http.Response(kSamples['mobile_me_physician.json']!, 200);
          }
          return http.Response(repeat, 200);
        }),
      );
      return (services, seen);
    }

    String applied(String sample, {String? outcome}) {
      final j = jsonDecode(kSamples[sample]!);
      return jsonEncode({...j, 'applied': false, 'outcome': ?outcome});
    }

    test('approve: the repeat returns the same outcome and the screen ends in the same state', () async {
      final (s, seen) = lostReply(applied('mobile_proposal_approved.json'));
      final r = await s.lead.approve('PRP-0003');
      expect(seen.map((r) => '${r.method} ${r.url.path}'), [
        'POST /proposals/PRP-0003/approve',
        'POST /proposals/PRP-0003/approve',
      ]);
      expect(
        (r.outcome, r.applied, r.proposal.status),
        (ProposalOutcome.approved, false, ProposalStatus.approved),
      );
      expect(r.offers, isNotEmpty); // the same offers the first call created
    });

    test(
      'opt-in: the repeat gives unchanged and the same opt-in value',
      () async {
        final (s, seen) = lostReply(
          applied('mobile_preferences_updated.json', outcome: 'unchanged'),
        );
        final r = await s.auth.setOptIn(false);
        final puts = seen
            .where((r) => r.method == 'PUT')
            .map((r) => r.body)
            .toList();
        expect(puts, hasLength(2));
        expect(puts.toSet(), hasLength(1)); // same body both times
        expect((r.outcome, r.applied), (PreferencesOutcome.unchanged, false));
        expect(
          r.me.splitShiftOptIn,
          jsonDecode(
            kSamples['mobile_preferences_updated.json']!,
          )['me']['split_shift_opt_in'],
        );
        expect(s.auth.me.value?.splitShiftOptIn, r.me.splitShiftOptIn);
      },
    );

    final actions = <String, (String, Future<Object?> Function(AppServices))>{
      'accept': (
        'mobile_offer_accept_accepted.json',
        (s) => s.offers.accept('OFF-0007'),
      ),
      'decline': (
        'mobile_offer_decline_declined.json',
        (s) => s.offers.decline('OFF-0007'),
      ),
      'release': (
        'mobile_offer_release_released.json',
        (s) => s.offers.release('OFF-0007'),
      ),
      'approve': (
        'mobile_proposal_approved.json',
        (s) => s.lead.approve('PRP-0003'),
      ),
      'reject': (
        'mobile_proposal_approved.json',
        (s) => s.lead.reject('PRP-0003', 'Not now'),
      ),
      'authorize': ('ESC', (s) => s.lead.authorize('ESC-0002')),
      'opt-in': (
        'mobile_preferences_updated.json',
        (s) => s.auth.setOptIn(true),
      ),
    };
    for (final MapEntry(key: name, value: (sample, call)) in actions.entries) {
      final body = sample == 'ESC'
          ? jsonEncode({
              'outcome': 'already_authorized',
              'applied': false,
              'escalation': jsonDecode(kSamples['mobile_escalation.json']!),
              'server_now': '2026-03-17T18:22:00-04:00',
            })
          : applied(sample);

      test('$name retries exactly once', () async {
        final (s, seen) = lostReply(body);
        await call(s);
        expect(seen.where((r) => r.method != 'GET'), hasLength(2));
      });
      test(
        '$name gives up after the retry fails too (NetworkError, no third attempt)',
        () async {
          final (s, seen) = lostReply(body, alwaysFail: true);
          await expectLater(call(s), throwsA(isA<NetworkError>()));
          expect(seen.where((r) => r.method != 'GET'), hasLength(2));
        },
      );
    }

    test('reads are not retried', () async {
      final (s, seen) = lostReply('{}', alwaysFail: true);
      await expectLater(s.offers.listOffers(), throwsA(isA<NetworkError>()));
      expect(seen, hasLength(1));
    });
  });
}
