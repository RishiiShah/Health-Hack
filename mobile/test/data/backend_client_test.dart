import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/clock.dart';
import 'package:sevaro_mobile/data/live/backend_client.dart';
import 'package:sevaro_mobile/data/live/live.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';
import 'package:sevaro_mobile/screens/data_widgets.dart';

// Exported by backend/tests/test_mobile_contract.py from real API calls on a
// synthetic world. No challenge files, answer keys or account credentials.
final bundle =
    jsonDecode(File('test/fixtures/backend_workflows.json').readAsStringSync())
        as Map<String, dynamic>;

class Server {
  final requests = <http.Request>[];
  final routes = <String, (Object, int)>{};
  late final OffsetServerClock clock;
  late final BackendApiClient client;
  Server({DateTime Function()? deviceNow}) {
    clock = OffsetServerClock(deviceNow: deviceNow, ticking: false);
    client = BackendApiClient(
      baseUrl: Uri.parse('https://api.example/api'),
      tokens: SessionTokenStore(
        MemoryBrowser()..session['sevaro_token'] = 'stored',
      ),
      clock: clock,
      onUnauthorized: () {},
      httpClient: MockClient((request) async {
        requests.add(request);
        expect(request.headers['authorization'], 'Bearer stored');
        final path = Uri.decodeComponent(
          request.url.path,
        ).replaceFirst('/api', '');
        final key = '${request.method} $path';
        final response = routes[key];
        if (response == null) fail('Unexpected native request: $key');
        return http.Response(
          jsonEncode(response.$1),
          response.$2,
          headers: {'content-type': 'application/json'},
        );
      }),
    );
    addTearDown(() {
      client.close();
      clock.dispose();
    });
  }
  void on(String path, String fixture, {int status = 200}) =>
      routes[path] = (bundle[fixture], status);
  void response(String path, Object payload, {int status = 200}) =>
      routes[path] = (payload, status);
  void proposalRoutes() {
    on('GET /offers/OFR-00001', 'proposed');
    on('GET /gaps/now_gap:G/candidates', 'candidates');
    on('GET /gaps/now_gap:G/trap-check', 'trap');
  }
}

void main() {
  testWidgets(
    'unsupported schedule displays its capability message without retry',
    (tester) async {
      final s = Server();
      UnsupportedFeature? error;
      try {
        await LiveLeadRepository(s.client).schedule(DateTime.utc(2026));
      } on UnsupportedFeature catch (failure) {
        error = failure;
      }
      expect(error, isNotNull);
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: DataFailure(
              error: error!,
              retry: () => fail('Unsupported features cannot retry'),
            ),
          ),
        ),
      );
      expect(
        find.text('Schedule views are not available from this backend.'),
        findsOneWidget,
      );
      expect(find.text('Retry'), findsNothing);
      expect(s.requests, isEmpty);
    },
  );
  test(
    'native physician metadata, effective shift, offers and activity parse',
    () async {
      final s = Server();
      s.on('GET /me', 'me_physician');
      s.on('GET /me/shift', 'shift_on');
      s.on('GET /me/offers', 'my_offers');
      s.on('GET /offers/OFR-00001', 'sent');
      final me = await s.client.get('/me', Me.parse);
      expect(me.role, Role.physician);
      expect(me.splitShiftOptIn, true);
      expect(me.weeklyOfferLimit, 3);
      expect(me.can('preferences.update'), false);
      final shift = await LiveShiftRepository(s.client).myShift();
      expect(shift.onShift, true);
      expect(
        shift.consultsToday,
        1,
      ); // real assignment after arrival, no simulated seed
      expect(
        shift.consults.firstWhere((c) => c.consultId == 'OWNED').level,
        ConsultLevel.critical,
      );
      final repo = LiveOfferRepository(s.client);
      final offer = (await repo.listOffers()).offers.single;
      expect(offer.hospitals.single.hospitalId, 'G');
      expect(offer.status, OfferStatus.sent);
      expect(offer.allowedActions, [OfferAction.accept, OfferAction.decline]);
      expect((await repo.getOffer(offer.offerId)).gapId, 'now_gap:G');
      expect((await repo.notifications()).items.single.offerId, offer.offerId);
      expect(
        s.requests.any((r) => r.url.path.endsWith('/notifications')),
        false,
      );
    },
  );

  test(
    'native replies and conflicts reload the authoritative offer; retry has a stable key',
    () async {
      final s = Server();
      s.on('POST /offers/OFR-00001/accept', 'accepted');
      final repo = LiveOfferRepository(s.client);
      final accepted = await repo.accept('OFR-00001');
      expect(accepted.outcome, OfferOutcome.accepted);
      expect(accepted.applied, true);
      expect(accepted.offer.allows(OfferAction.release), false);
      expect(
        s.requests.last.headers['idempotency-key'],
        'mobile:/offers/OFR-00001/accept',
      );
      await repo.accept('OFR-00001');
      expect(
        s.requests.last.headers['idempotency-key'],
        s.requests.first.headers['idempotency-key'],
      );
      s.response('POST /offers/OFR-00001/decline', {
        'error': {'code': 'conflicting_reply', 'message': 'Offer accepted'},
      }, status: 409);
      s.on('GET /offers/OFR-00001', 'accepted');
      final conflict = await repo.decline('OFR-00001');
      expect(conflict.outcome, OfferOutcome.notOpen);
      expect(conflict.applied, false);
      s.response('POST /offers/OFR-00001/accept', {
        'error': {'code': 'expired', 'message': 'Reply window closed'},
      }, status: 409);
      s.response('GET /offers/OFR-00001', {
        ...bundle['sent'],
        'state': 'Expired',
      });
      expect((await repo.accept('OFR-00001')).outcome, OfferOutcome.expired);
      s.response('POST /offers/OFR-00001/accept', {
        'detail': 'Clock is behind the last transition',
      }, status: 409);
      s.on('GET /offers/OFR-00001', 'sent');
      await expectLater(repo.accept('OFR-00001'), throwsA(isA<Conflict>()));
    },
  );

  test(
    'lead proposals, server candidates, trap, audit, coverage and approval parse',
    () async {
      final s = Server();
      s.proposalRoutes();
      s.on('GET /me', 'me_lead');
      s.on('GET /offers', 'offers_proposed');
      s.on('GET /interventions', 'interventions');
      s.on('GET /audit', 'audit');
      s.on('GET /snapshot', 'snapshot_coverage');
      s.on('POST /offers/OFR-00001/approve', 'sent');
      final me = await s.client.get('/me', Me.parse);
      expect(me.role, Role.clinicalLead);
      expect(me.can('proposal.approve'), true);
      final repo = LiveLeadRepository(s.client);
      final queue = await repo.queue();
      expect(queue.pendingCount, 1);
      final proposal = await repo.proposal(queue.proposals.single.proposalId);
      expect(proposal.recipients.single.physicianId, 'J');
      expect(proposal.recipients.single.rank, 1);
      final candidates = await repo.candidates('now_gap:G');
      expect(
        candidates.candidates.single.eligible,
        bundle['candidates']['candidates'][0]['eligible'],
      );
      expect(
        candidates.candidates.single.rules.length,
        bundle['candidates']['rules'].length,
      );
      expect(
        (await repo.trapCheck('now_gap:G')).seedConsults,
        bundle['trap']['seed_consults'],
      );
      expect(
        (await repo.audit('now_gap:G')).entries.length,
        bundle['audit']['items'].length,
      );
      expect(s.requests.last.url.queryParameters['gap_id'], 'now_gap:G');
      final coverage = await repo.coverage();
      expect(coverage.hospitals.length, 2);
      expect(coverage.columns.length, 7);
      final approved = await repo.approve(proposal.proposalId);
      expect(approved.applied, true);
      expect(approved.outcome, ProposalOutcome.approved);
      expect(approved.offers.single.status, OfferStatus.sent);
      expect(
        s.requests.last.headers['idempotency-key'],
        'mobile:/proposals/OFR-00001/approve',
      );
      s.on('GET /offers', 'offers_sent');
      expect(
        (await repo.activeOffers()).broadcasts.single.status,
        BroadcastStatus.open,
      );
    },
  );

  test(
    'rejected and cancelled proposals preserve server outcome; missing trap evidence is unavailable',
    () async {
      final s = Server();
      s.proposalRoutes();
      final repo = LiveLeadRepository(s.client);
      await repo.proposal('OFR-00001');
      s.response('POST /offers/OFR-00001/reject', {
        ...bundle['proposed'],
        'state': 'Rejected',
        'reject_reason': 'Not now',
      });
      final rejected = await repo.reject('OFR-00001', 'Not now');
      expect(rejected.outcome, ProposalOutcome.rejected);
      expect(rejected.proposal.rejectReason, 'Not now');
      s.response('POST /offers/OFR-00001/approve', {
        ...bundle['proposed'],
        'state': 'Cancelled',
        'reason': 'R3 no longer passes',
      });
      final cancelled = await repo.approve('OFR-00001');
      expect(cancelled.outcome, ProposalOutcome.cancelled);
      expect(cancelled.applied, true);
      expect(cancelled.proposal.decisionReason, 'R3 no longer passes');
      expect(cancelled.proposal.status, ProposalStatus.cancelled);
      expect(cancelled.offers, isEmpty);
      s.response('GET /gaps/now_gap:G/trap-check', {
        ...bundle['trap'],
        'seed_consults': null,
        'passed': false,
        'reasons': ['not modeled: no service time'],
      });
      await expectLater(
        repo.trapCheck('now_gap:G'),
        throwsA(isA<Unavailable>()),
      );
      s.response('GET /gaps/now_gap:G/trap-check', {
        ...bundle['trap'],
        'passed': false,
        'unknown_demand': ['H'],
        'reasons': ['trap check unknown: missing hourly demand for H'],
      });
      await expectLater(
        repo.trapCheck('now_gap:G'),
        throwsA(
          isA<Unavailable>().having(
            (e) => e.toString(),
            'reason',
            contains('unknown'),
          ),
        ),
      );
    },
  );

  test(
    'escalation authorization uses native intervention and handles repeat',
    () async {
      final s = Server();
      final row = {
        'id': 'INT-00001',
        'item_id': 'now_gap:G',
        'reason': 'Coverage needed',
        'created_at': bundle['sent']['server_now'],
        'state': 'AUTHORIZED',
        'authorized_at': bundle['sent']['server_now'],
        'authorized_by': 'Dr. Lead',
      };
      s.response('POST /interventions/INT-00001/authorize', row);
      s.on('GET /me', 'me_lead');
      final repo = LiveLeadRepository(s.client);
      expect(
        (await repo.authorize('INT-00001')).outcome,
        EscalationOutcome.authorized,
      );
      s.response('POST /interventions/INT-00001/authorize', {
        'detail': 'already authorized',
      }, status: 409);
      s.response('GET /interventions', {
        'items': [
          {...row, 'intervention_id': row['id']},
        ],
        'server_now': row['created_at'],
      });
      expect(
        (await repo.authorize('INT-00001')).outcome,
        EscalationOutcome.alreadyAuthorized,
      );
    },
  );

  test(
    'fixed backend time does not expire mobile offers as device time advances',
    () async {
      var device = DateTime.utc(2030);
      final s = Server(deviceNow: () => device);
      s.on('GET /me', 'me_physician');
      await s.client.get('/me', Me.parse);
      final before = s.clock.now();
      device = device.add(const Duration(hours: 5));
      expect(s.clock.now(), before);
      // Responses without a clock mode preserve the known mode.
      s.on('GET /gaps/now_gap:G/candidates', 'candidates');
      await LiveLeadRepository(s.client).candidates('now_gap:G');
      device = device.add(const Duration(hours: 1));
      expect(s.clock.now(), before);
      s.response('GET /me', {
        ...bundle['me_physician'],
        'clock_mode': 'anchored',
      });
      await s.client.get('/me', Me.parse);
      device = device.add(const Duration(minutes: 1));
      expect(s.clock.now(), before.add(const Duration(minutes: 1)));
    },
  );

  test(
    'unsupported workflows make no HTTP write and unknown staffing is not fabricated',
    () async {
      final s = Server();
      final lead = LiveLeadRepository(s.client),
          shift = LiveShiftRepository(s.client);
      await expectLater(
        lead.schedule(DateTime.utc(2026)),
        throwsA(isA<UnsupportedFeature>()),
      );
      await expectLater(
        shift.mySchedule(DateTime.utc(2026)),
        throwsA(isA<UnsupportedFeature>()),
      );
      await expectLater(
        LiveOfferRepository(s.client).release('OFR-00001'),
        throwsA(isA<UnsupportedFeature>()),
      );
      expect(
        () => s.client.put(
          '/me/preferences',
          (v) => v,
          body: {'split_shift_opt_in': false},
        ),
        throwsA(isA<UnsupportedFeature>()),
      );
      expect(s.requests, isEmpty);
      final snapshot =
          jsonDecode(jsonEncode(bundle['snapshot_coverage']))
              as Map<String, dynamic>;
      snapshot['coverage']['hospitals'][0]['cells'][0]['required'] = null;
      s.response('GET /snapshot', snapshot);
      await expectLater(lead.coverage(), throwsA(isA<Unavailable>()));
    },
  );
}
