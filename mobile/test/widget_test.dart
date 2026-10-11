import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';

void main() {
  Future<void> launch(WidgetTester tester, String role) async {
    tester.view.physicalSize = const Size(1200, 2400);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(const SevaroApp());
    expect(find.text('Enter Command Center →'), findsOneWidget);
    await tester.tap(find.text('Sign in →'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Launch $role →'));
    await tester.pumpAndSettle();
  }

  testWidgets('coordinator lands on Command with dummy queue', (tester) async {
    await launch(tester, 'Coordinator');
    expect(find.text('Ranked queue'), findsOneWidget);
    await tester.tap(find.text('Schedule'));
    await tester.pumpAndSettle();
    expect(find.text('Shift schedule'), findsOneWidget);
    await tester.tap(find.text('Sign out ↗'));
    await tester.pumpAndSettle();
    expect(find.text('Enter Command Center →'), findsOneWidget);
  });

  testWidgets('lead approves the pending offer', (tester) async {
    await launch(tester, 'Lead');
    await tester.tap(find.text('Approve and send offer'));
    await tester.pump();
    expect(find.text('Approved · offer sent to Dr. Okafor'), findsOneWidget);
  });

  testWidgets('physician accepts the offer', (tester) async {
    await launch(tester, 'Physician');
    expect(find.text('1 h 36 min'), findsOneWidget);
    await tester.tap(find.text('Offers (1)'));
    await tester.pump();
    expect(find.text('10:00'), findsOneWidget);
    await tester.tap(find.text('Accept Extra Shift'));
    await tester.pump();
    expect(find.text('Accepted'), findsOneWidget);
  });
}
