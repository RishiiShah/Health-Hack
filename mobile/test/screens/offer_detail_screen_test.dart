import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/offer_detail_screen.dart';

void main() {
  late ValueNotifier<Duration> remaining;

  setUp(() => remaining = ValueNotifier(const Duration(minutes: 5)));
  tearDown(() => remaining.dispose());

  Widget offer({
    String status = 'sent',
    String? outcome,
    String? reason,
    Set<String> actions = const {'accept', 'decline'},
    OfferActionCallback? onAction,
  }) => SevaroApp(
    home: OfferDetailScreen(
      offerId: 'OFF-TEST',
      hospital: 'Suncrest Medical Pavilion',
      hoursEt: '19:00–23:00 ET',
      signInByEt: '18:55 ET',
      expiresAtEt: '18:35 ET',
      gapSummary: 'One physician short from 19:00.',
      whyYou: const ['Credentialed at Suncrest'],
      status: status,
      outcome: outcome,
      statusReason: reason,
      allowedActions: actions,
      remaining: remaining,
      routingHospitals: const ['Suncrest Medical Pavilion'],
      onAction: onAction ?? (_) async => null,
    ),
  );

  Future<void> tapAccept(WidgetTester tester) async {
    await tester.ensureVisible(find.text("Accept, I'll cover it"));
    await tester.tap(find.text("Accept, I'll cover it"));
    await tester.pumpAndSettle();
  }

  testWidgets('Cancel makes no request', (tester) async {
    var calls = 0;
    await tester.pumpWidget(
      offer(
        onAction: (_) async {
          calls++;
          return null;
        },
      ),
    );
    await tapAccept(tester);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(calls, 0);
  });

  testWidgets('expiry during confirmation prevents sending accept', (
    tester,
  ) async {
    var calls = 0;
    await tester.pumpWidget(
      offer(
        onAction: (_) async {
          calls++;
          return null;
        },
      ),
    );
    await tapAccept(tester);
    remaining.value = Duration.zero;
    await tester.pump();
    await tester.tap(find.text('Confirm acceptance'));
    await tester.pumpAndSettle();
    expect(calls, 0);
    expect(find.text('Expiring…'), findsOneWidget);
    for (final button in tester.widgetList<OutlinedButton>(
      find.byType(OutlinedButton),
    )) {
      expect(button.onPressed, isNull);
    }
  });

  testWidgets('both actions disabled in flight without optimistic acceptance', (
    tester,
  ) async {
    final pending = Completer<String?>();
    var calls = 0;
    await tester.pumpWidget(
      offer(
        onAction: (action) {
          expect(action, 'accept');
          calls++;
          return pending.future;
        },
      ),
    );
    await tapAccept(tester);
    await tester.tap(find.text('Confirm acceptance'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(calls, 1);
    expect(find.text("You're on"), findsNothing);
    for (final button in tester.widgetList<OutlinedButton>(
      find.byType(OutlinedButton),
    )) {
      expect(button.onPressed, isNull);
    }
    pending.complete("You don't have permission for this.");
    await tester.pumpAndSettle();
    expect(find.text("You don't have permission for this."), findsOneWidget);
    expect(find.text("You're on"), findsNothing);
  });

  testWidgets('server outcome wins over previous sent state', (tester) async {
    await tester.pumpWidget(offer(outcome: 'already_filled'));
    expect(find.text('Already filled'), findsOneWidget);
    expect(find.text("Accept, I'll cover it"), findsNothing);
  });

  testWidgets('feed withdrawal while confirming prevents sending', (
    tester,
  ) async {
    var calls = 0;
    Future<String?> action(String _) async {
      calls++;
      return null;
    }

    await tester.pumpWidget(offer(onAction: action));
    await tapAccept(tester);
    await tester.pumpWidget(
      offer(
        status: 'withdrawn',
        reason: 'filled_by_another_physician',
        onAction: action,
      ),
    );
    await tester.tap(find.text('Confirm acceptance'));
    await tester.pumpAndSettle();
    expect(calls, 0);
    expect(find.text('Already filled'), findsOneWidget);
  });

  for (final entry in {
    'accepted': "You're on",
    'declined': 'Declined',
    'expired': 'Missed',
    'released': 'Released',
    'not_open': 'No longer needed',
  }.entries) {
    testWidgets('renders ${entry.key} outcome', (tester) async {
      await tester.pumpWidget(offer(outcome: entry.key));
      expect(find.text(entry.value), findsOneWidget);
      expect(find.text("Accept, I'll cover it"), findsNothing);
    });
  }

  testWidgets('release appears only when allowed', (tester) async {
    await tester.pumpWidget(offer(status: 'accepted', actions: {}));
    expect(find.text("I can't make it after all"), findsNothing);
    await tester.pumpWidget(offer(status: 'accepted', actions: {'release'}));
    expect(find.text("I can't make it after all"), findsOneWidget);
  });
}
