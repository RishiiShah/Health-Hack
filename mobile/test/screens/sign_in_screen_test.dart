import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/sign_in_screen.dart';

void main() {
  testWidgets('shows server error and keeps email after failed login', (
    tester,
  ) async {
    await tester.pumpWidget(
      SevaroApp(
        home: SignInScreen(
          onSignIn: (email, password) async {
            expect(email, 'lead@demo.sevaro');
            expect(password, 'wrong');
            return 'Incorrect email or password';
          },
        ),
      ),
    );
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'lead@demo.sevaro',
    );
    await tester.enterText(find.byType(TextFormField).at(1), 'wrong');
    await tester.ensureVisible(find.text('Sign in'));
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();
    expect(find.text('Incorrect email or password'), findsOneWidget);
    expect(find.text('lead@demo.sevaro'), findsOneWidget);
    final password = tester.widget<TextFormField>(
      find.byType(TextFormField).at(1),
    );
    expect(password.controller!.text, isEmpty);
  });

  testWidgets('role preference only changes copy and login is submitted once', (
    tester,
  ) async {
    final pending = Completer<String?>();
    var calls = 0;
    await tester.pumpWidget(
      SevaroApp(
        home: SignInScreen(
          onSignIn: (email, password) {
            calls++;
            return pending.future;
          },
        ),
      ),
    );
    await tester.tap(find.text('Operations'));
    await tester.pump();
    expect(
      find.text('Keep your team connected and coverage on track.'),
      findsOneWidget,
    );
    await tester.enterText(
      find.byType(TextFormField).at(0),
      'okafor@demo.sevaro',
    );
    await tester.enterText(find.byType(TextFormField).at(1), 'demo');
    await tester.ensureVisible(find.text('Sign in'));
    await tester.tap(find.text('Sign in'));
    await tester.tap(find.text('Sign in'));
    await tester.pump();
    expect(calls, 1);
    expect(
      tester.widget<FilledButton>(find.byType(FilledButton)).onPressed,
      isNull,
    );
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    pending.complete(null);
    await tester.pumpAndSettle();
  });

  testWidgets('390px layout scrolls at 200 percent text size', (tester) async {
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
        home: const SignInScreen(),
      ),
    );
    await tester.ensureVisible(find.text('Synthetic data only'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Synthetic data only').hitTestable(), findsOneWidget);
  });

  testWidgets('SSO shows the demo unavailable notice', (tester) async {
    await tester.pumpWidget(const SevaroApp(home: SignInScreen()));
    await tester.ensureVisible(find.text('Use Sevaro single sign-on'));
    await tester.tap(find.text('Use Sevaro single sign-on'));
    await tester.pump();
    expect(find.text('Not available in the demo'), findsOneWidget);
  });
}
