import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';

void main() {
  for (final size in [const Size(390, 844), const Size(844, 390)]) {
    testWidgets('Cerevia dashboard fits $size and tables scroll inside cards', (
      tester,
    ) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(const SevaroApp());
      expect(find.text('Cerevia'), findsWidgets);
      await tester.tap(find.text('Sign in →'));
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Launch Coordinator →'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Launch Coordinator →'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Command center'), findsOneWidget);
      await tester.ensureVisible(find.text('Coverage by hospital'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      final table = find.byType(DataTable).first;
      final scroll = find
          .ancestor(
            of: table,
            matching: find.byWidgetPredicate(
              (widget) =>
                  widget is SingleChildScrollView &&
                  widget.scrollDirection == Axis.horizontal,
            ),
          )
          .first;
      expect(tester.getSize(scroll).width, lessThanOrEqualTo(size.width));
      await tester.ensureVisible(scroll);
      await tester.pumpAndSettle();
      await tester.dragFrom(
        tester.getTopLeft(scroll) + const Offset(100, 24),
        const Offset(-80, 0),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.ensureVisible(find.text('Coverage offers'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    });
  }
}
