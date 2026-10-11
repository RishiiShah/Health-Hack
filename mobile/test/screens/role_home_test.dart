import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/role_home.dart';

void main() {
  Widget home(String role) => SevaroApp(
    home: RoleHome(
      role: role,
      physicianPages: List.generate(
        4,
        (index) =>
            (_) => Text('Physician page $index'),
      ),
      leadPages: List.generate(
        4,
        (index) =>
            (_) => Text('Lead page $index'),
      ),
    ),
  );

  testWidgets('physician starts on shift and can open offers', (tester) async {
    await tester.pumpWidget(home('physician'));
    expect(find.text('Physician page 0'), findsOneWidget);
    await tester.tap(find.text('Offers'));
    await tester.pump();
    expect(find.text('Physician page 2'), findsOneWidget);
    expect(find.text('Physician page 0'), findsNothing);
  });

  testWidgets('lead starts on approvals', (tester) async {
    await tester.pumpWidget(home('clinical_lead'));
    expect(find.text('Lead page 0'), findsOneWidget);
    expect(find.text('Offers'), findsNothing);
  });

  for (final role in ['coordinator', 'admin']) {
    testWidgets('$role uses web dashboard', (tester) async {
      await tester.pumpWidget(home(role));
      expect(find.text('Use the web dashboard'), findsOneWidget);
      expect(find.text('Physician page 0'), findsNothing);
    });
  }

  testWidgets('unknown role does not fall back to a dashboard', (tester) async {
    await tester.pumpWidget(home('unexpected'));
    expect(find.text('This account has an unrecognized role.'), findsOneWidget);
    expect(find.text('Physician page 0'), findsNothing);
    expect(find.text('Lead page 0'), findsNothing);
  });
}
