import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/main.dart';

void main() {
  testWidgets('app opens the sign-in screen', (tester) async {
    await tester.pumpWidget(const SevaroApp());
    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Sign-in is temporarily unavailable.'), findsOneWidget);
  });
}
