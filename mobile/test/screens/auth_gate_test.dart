import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/data/fake/fakes.dart';
import 'package:sevaro_mobile/data/models.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/auth_gate.dart';

void main() {
  testWidgets(
    'arbitrary credentials open the selected dashboard; logout requires login again',
    (tester) async {
      final fake = FakeServices(
        browser: MemoryBrowser(),
        ticking: false,
        deviceNow: () => kFakeStart,
        autoAnswer: false,
        allowAnyCredentials: true,
      );
      addTearDown(fake.dispose);
      await tester.pumpWidget(
        SevaroApp(
          home: RepositoryAuthGate(
            services: fake.services,
            onPreviewRoleChanged: (physician) => fake.auth.previewRole =
                physician ? Role.physician : Role.clinicalLead,
          ),
        ),
      );
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.text('Open working demo'), findsNothing);
      expect(find.text('Preview screens'), findsNothing);
      expect(find.text('I work as'), findsOneWidget);
      expect(find.text('Demo accounts'), findsNothing);

      Future<void> login(String email, String password) async {
        await tester.enterText(find.byType(TextFormField).first, email);
        await tester.enterText(find.byType(TextFormField).last, password);
        await tester.ensureVisible(find.text('Sign in'));
        await tester.tap(find.text('Sign in'));
        await tester.pumpAndSettle();
      }

      await login('', '');
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.text('2 waiting'), findsNothing);
      await tester.ensureVisible(find.text('Clinical lead'));
      await tester.tap(find.text('Clinical lead'));
      await tester.pump();
      await login('any.lead@example.com', 'anything');
      expect(find.text('2 waiting'), findsOneWidget);
      expect(find.text('Review proposal'), findsOneWidget);
      expect(find.text('Oak Valley Medical'), findsOneWidget);
      expect(find.text('My shift'), findsNothing);

      await tester.tap(find.widgetWithText(TextButton, 'Account'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Sign out'));
      await tester.tap(find.text('Sign out'));
      await tester.pumpAndSettle();
      expect(find.text('Welcome back'), findsOneWidget);
      expect(find.text('2 waiting'), findsNothing);

      await login('someone.else@example.com', 'another-password');
      expect(find.text('CON-2104'), findsOneWidget);
      expect(find.text('CON-2113'), findsOneWidget);
      expect(find.text('Approvals'), findsNothing);
      expect(find.text('someone.else@example.com'), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
      await tester.pump();
    },
  );
}
