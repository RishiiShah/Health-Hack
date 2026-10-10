import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fakes.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/account_page.dart';
import 'package:sevaro_mobile/screens/lead_pages.dart';
import 'package:sevaro_mobile/screens/physician_pages.dart';
import 'package:sevaro_mobile/screens/service_session.dart';
import 'package:sevaro_mobile/screens/schedule_pages.dart';

void main() {
  Future<FakeServices> prepare(WidgetTester tester, String role) async {
    final fake = FakeServices(
      ticking: false,
      browser: MemoryBrowser(),
      autoAnswer: false,
    );
    await fake.signInAs(role);
    addTearDown(() async {
      await tester.pumpWidget(const SizedBox());
      fake.services.physicianFeed.stop();
      fake.services.leadFeed.stop();
      fake.dispose();
    });
    return fake;
  }

  Future<void> tap(WidgetTester tester, String label) async {
    final finder = find.text(label);
    await tester.ensureVisible(finder);
    await tester.tap(finder);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    await tester.pump();
  }

  testWidgets('accept and release render repository outcomes', (tester) async {
    final fake = await prepare(tester, 'okafor');
    await tester.pumpWidget(
      SevaroApp(
        home: ConnectedOffer(services: fake.services, offerId: 'OFF-0007'),
      ),
    );
    await tester.pumpAndSettle();
    await tap(tester, "Accept, I'll cover it");
    await tap(tester, 'Confirm acceptance');
    expect(find.text("You're on"), findsOneWidget);
    expect(
      (await fake.offers.getOffer('OFF-0007')).status,
      OfferStatus.accepted,
    );
    await tap(tester, "I can't make it after all");
    await tap(tester, 'Notify clinical lead');
    expect(find.text('Released'), findsOneWidget);
    expect(
      (await fake.offers.getOffer('OFF-0007')).status,
      OfferStatus.released,
    );
  });

  for (final state in ['filled', 'expired', 'closed']) {
    testWidgets('feed changes open offer to $state', (tester) async {
      final fake = await prepare(tester, 'okafor');
      fake.services.physicianFeed.start();
      await tester.pumpWidget(
        SevaroApp(
          home: ConnectedOffer(services: fake.services, offerId: 'OFF-0007'),
        ),
      );
      await tester.pumpAndSettle();
      switch (state) {
        case 'filled':
          fake.offers.fillByOther('OFF-0007');
        case 'expired':
          fake.offers.expire('OFF-0007');
        case 'closed':
          fake.offers.closeGap('OFF-0007');
      }
      await fake.services.physicianFeed.refreshNow();
      await tester.pumpAndSettle();
      expect(
        find.text(switch (state) {
          'filled' => 'Already filled',
          'expired' => 'Missed',
          _ => 'No longer needed',
        }),
        findsOneWidget,
      );
      expect(find.text("Accept, I'll cover it"), findsNothing);
      fake.services.physicianFeed.stop();
    });
  }

  testWidgets('opting out with an open offer requires confirmation', (
    tester,
  ) async {
    final fake = await prepare(tester, 'okafor');
    await tester.pumpWidget(
      SevaroApp(
        home: Scaffold(
          body: ValueListenableBuilder<Me?>(
            valueListenable: fake.auth.me,
            builder: (_, me, _) =>
                AccountPage(services: fake.services, me: me!),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tap(tester, 'Available for extra shifts');
    await tap(tester, 'Cancel');
    expect(fake.auth.me.value!.splitShiftOptIn, isTrue);
    expect((await fake.offers.getOffer('OFF-0007')).status, OfferStatus.sent);
    await tap(tester, 'Available for extra shifts');
    await tap(tester, 'Decline and opt out');
    expect(fake.auth.me.value!.splitShiftOptIn, isFalse);
    expect(
      (await fake.offers.getOffer('OFF-0007')).status,
      OfferStatus.declined,
    );
  });

  testWidgets('proposal cancel makes no mutation, approval uses repository', (
    tester,
  ) async {
    final fake = await prepare(tester, 'lead');
    final proposal = (await fake.lead.queue()).proposals.first;
    await tester.pumpWidget(
      SevaroApp(
        home: ProposalScreen(
          services: fake.services,
          proposalId: proposal.proposalId,
        ),
      ),
    );
    await tester.pumpAndSettle();
    final detail = await fake.lead.proposal(proposal.proposalId);
    final label = detail.recipients.length == 1
        ? 'Approve and send to ${detail.recipients.first.displayName}'
        : 'Approve and send to ${detail.recipients.length} physicians';
    await tap(tester, label);
    await tap(tester, 'Cancel');
    expect(
      (await fake.lead.proposal(proposal.proposalId)).status,
      ProposalStatus.proposed,
    );
    await tap(tester, label);
    await tap(tester, 'Approve and send');
    expect(find.text('Approved'), findsOneWidget);
    expect(
      (await fake.lead.proposal(proposal.proposalId)).status,
      ProposalStatus.approved,
    );
  });

  testWidgets('new offer takes over shift and sign-out removes nested routes', (
    tester,
  ) async {
    final fake = await prepare(tester, 'brennan');
    await fake.auth.setOptIn(true);
    var ended = false;
    await tester.pumpWidget(
      SevaroApp(
        home: ServiceSession(
          services: fake.services,
          me: fake.auth.me.value!,
          onEnded: () => ended = true,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text("You're off shift"), findsOneWidget);
    fake.offers.pushNewOffer();
    await fake.services.physicianFeed.refreshNow();
    await tester.pumpAndSettle();
    expect(find.text('Coverage notification'), findsOneWidget);
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Coverage notification'), findsNothing);
    expect(find.text("You're off shift"), findsOneWidget);
    fake.offers.pushNewOffer();
    await fake.services.physicianFeed.refreshNow();
    await tester.pumpAndSettle();
    expect(find.text('Coverage notification'), findsOneWidget);
    await fake.auth.signOut();
    await tester.pumpAndSettle();
    expect(ended, isTrue);
    expect(find.text('Coverage notification'), findsNothing);
  });

  testWidgets('all candidates expose all eight server rule results', (
    tester,
  ) async {
    final fake = await prepare(tester, 'lead');
    final proposal = (await fake.lead.queue()).proposals.first;
    final candidates = await fake.lead.candidates(proposal.gapId);
    await tester.pumpWidget(
      SevaroApp(
        home: CandidatesScreen(services: fake.services, gapId: proposal.gapId),
      ),
    );
    await tester.pumpAndSettle();
    for (final candidate in candidates.candidates) {
      expect(find.text(candidate.displayName), findsOneWidget);
      expect(candidate.rules, hasLength(8));
      for (final rule in candidate.rules) {
        expect(
          find.text(
            '${rule.rule} · ${rule.name} · ${rule.passed ? 'Pass' : 'Fail'}',
          ),
          findsWidgets,
        );
      }
    }
  });

  testWidgets('rejection requires a reason and renders repository result', (
    tester,
  ) async {
    final fake = await prepare(tester, 'lead');
    final proposal = (await fake.lead.queue()).proposals.first;
    await tester.pumpWidget(
      SevaroApp(
        home: ProposalScreen(
          services: fake.services,
          proposalId: proposal.proposalId,
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tap(tester, 'Reject');
    final button = tester.widget<OutlinedButton>(
      find.widgetWithText(OutlinedButton, 'Reject proposal'),
    );
    expect(button.onPressed, isNull);
    await tester.enterText(find.byType(TextField), 'Coverage plan changed');
    await tester.pump();
    await tap(tester, 'Reject proposal');
    await tap(tester, 'Confirm rejection');
    expect(find.text('Rejected'), findsOneWidget);
    expect(
      (await fake.lead.proposal(proposal.proposalId)).rejectReason,
      'Coverage plan changed',
    );
  });

  testWidgets('escalation cancel preserves pending; confirmation authorizes', (
    tester,
  ) async {
    final fake = await prepare(tester, 'lead');
    final escalation = (await fake.lead.queue()).escalations.first;
    await tester.pumpWidget(
      SevaroApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: EscalationCard(
              services: fake.services,
              me: fake.auth.me.value!,
              escalation: escalation,
            ),
          ),
        ),
      ),
    );
    await tap(tester, 'Authorize');
    await tap(tester, 'Cancel');
    expect(
      (await fake.lead.queue()).escalations.any(
        (e) => e.escalationId == escalation.escalationId,
      ),
      isTrue,
    );
    await tap(tester, 'Authorize');
    await tester.tap(find.widgetWithText(FilledButton, 'Authorize').last);
    await tester.pumpAndSettle();
    expect(find.text('Authorized'), findsOneWidget);
    expect(
      (await fake.lead.queue()).escalations.any(
        (e) => e.escalationId == escalation.escalationId,
      ),
      isFalse,
    );
  });

  for (final page in ['coverage', 'schedule', 'shift']) {
    testWidgets('$page fits a phone at 200 percent text size', (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final fake = await prepare(tester, page == 'shift' ? 'shah' : 'lead');
      final child = switch (page) {
        'coverage' => CoveragePage(services: fake.services),
        'schedule' => LeadSchedulePage(
          services: fake.services,
          openProposal: (_) {},
        ),
        _ => ShiftPage(
          services: fake.services,
          me: fake.auth.me.value!,
          onOffers: () {},
        ),
      };
      await tester.pumpWidget(
        MaterialApp(
          builder: (context, child) => MediaQuery(
            data: MediaQuery.of(
              context,
            ).copyWith(textScaler: const TextScaler.linear(2)),
            child: child!,
          ),
          home: Scaffold(body: child),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('forbidden approval keeps proposal unchanged', (tester) async {
    final fake = await prepare(tester, 'lead');
    final proposal = (await fake.lead.queue()).proposals.first;
    await tester.pumpWidget(
      SevaroApp(
        home: ProposalScreen(
          services: fake.services,
          proposalId: proposal.proposalId,
        ),
      ),
    );
    await tester.pumpAndSettle();
    final button = find.byType(FilledButton).first;
    await tester.ensureVisible(button);
    await tester.tap(button);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    fake.failNext(const Forbidden());
    await tap(tester, 'Approve and send');
    expect(find.text("You don't have permission for this."), findsOneWidget);
    expect(
      (await fake.lead.proposal(proposal.proposalId)).status,
      ProposalStatus.proposed,
    );
  });

  testWidgets('lead answer event displays an acceptance toast', (tester) async {
    final fake = FakeServices(ticking: false, browser: MemoryBrowser());
    await fake.signInAs('lead');
    final proposal = (await fake.lead.queue()).proposals.first;
    await fake.lead.approve(proposal.proposalId);
    await tester.pumpWidget(
      SevaroApp(
        home: ServiceSession(services: fake.services, me: fake.auth.me.value!),
      ),
    );
    await tester.pumpAndSettle();
    fake.clock.advance(const Duration(seconds: 16));
    await fake.services.leadFeed.refreshNow();
    await tester.pump();
    expect(find.byType(SnackBar), findsOneWidget);
    expect(find.textContaining('accepted ·'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    fake.dispose();
  });
}
