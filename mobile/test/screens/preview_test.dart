import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/preview/preview_menu.dart';
import 'package:sevaro_mobile/screens/preview/preview_offer.dart';
import 'package:sevaro_mobile/screens/preview/preview_widgets.dart';
import 'package:sevaro_mobile/screens/sign_in_screen.dart';

void main() {
  testWidgets('developer gallery renders populated screens', (tester) async {
    await tester.pumpWidget(const SevaroApp(home: PreviewMenu()));
    expect(find.text('Explore Sevaro'), findsOneWidget);
    await tester.tap(find.text('Physician · on shift'));
    await tester.pumpAndSettle();
    expect(find.text('SCREEN PREVIEW · synthetic data'), findsOneWidget);
    expect(find.text('Your shift, at a glance'), findsOneWidget);
    await tester.tap(find.text('Offers'));
    await tester.pumpAndSettle();
    expect(find.text('2 of 3 requests this week'), findsOneWidget);
  });

  testWidgets('plain sign-in has no preview access', (tester) async {
    await tester.pumpWidget(const SevaroApp(home: SignInScreen()));
    expect(find.text('Preview screens'), findsNothing);
  });

  testWidgets('preview acceptance updates the actual offer widget', (
    tester,
  ) async {
    await tester.pumpWidget(
      const SevaroApp(home: PreviewSurface(child: PreviewOffer())),
    );
    await tester.ensureVisible(find.text("Accept, I'll cover it"));
    await tester.tap(find.text("Accept, I'll cover it"));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirm acceptance'));
    await tester.pump();
    expect(find.text("You're on"), findsNothing);
    await tester.pump(const Duration(milliseconds: 700));
    await tester.pumpAndSettle();
    expect(find.text("You're on"), findsOneWidget);
    expect(find.text("I can't make it after all"), findsOneWidget);
  });

  testWidgets('manual clock disables both offer responses', (tester) async {
    await tester.pumpWidget(
      const SevaroApp(home: PreviewSurface(child: PreviewOffer())),
    );
    await tester.tap(find.text('Set 0:00'));
    await tester.pump();
    expect(find.text('Expiring…'), findsOneWidget);
    for (final button in tester.widgetList<OutlinedButton>(
      find.byType(OutlinedButton),
    )) {
      expect(button.onPressed, isNull);
    }
  });

  testWidgets('lead preview opens selected coverage tab', (tester) async {
    await tester.pumpWidget(
      const SevaroApp(home: PreviewDashboard(lead: true, initialIndex: 2)),
    );
    expect(find.text('Coverage across your team'), findsOneWidget);
    expect(find.text('1/2*'), findsOneWidget);
  });

  testWidgets('preview menu fits narrow screens with large text', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(2)),
          child: child!,
        ),
        home: const PreviewMenu(),
      ),
    );
    await tester.ensureVisible(find.text('My schedule'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
