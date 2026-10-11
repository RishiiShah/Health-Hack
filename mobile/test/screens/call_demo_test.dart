import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/call_demo.dart';

void main() {
  testWidgets('dummy mode rings the sample offer on the fake backend', (
    tester,
  ) async {
    await tester.pumpWidget(
      SevaroApp(
        home: Builder(
          builder: (context) => TextButton(
            onPressed: () => openCallDemo(context),
            child: const Text('go'),
          ),
        ),
      ),
    );
    await tester.tap(find.text('go'));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text('Sevaro Coverage Call'), findsOneWidget);
    expect(find.text('Suncrest Medical Pavilion'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
