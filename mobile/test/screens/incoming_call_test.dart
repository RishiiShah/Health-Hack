import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/fake/fakes.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';
import 'package:sevaro_mobile/main.dart';
import 'package:sevaro_mobile/screens/incoming_call_screen.dart';
import 'package:sevaro_mobile/screens/service_session.dart';
import 'package:sevaro_mobile/web_alerts.dart';

void main() {
  late RecordingWebAlerts alerts;

  Future<FakeServices> prepare(WidgetTester tester, String who) async {
    alerts = RecordingWebAlerts();
    final fake = FakeServices(
      ticking: false,
      browser: MemoryBrowser(),
      autoAnswer: false,
      alerts: alerts,
    );
    await fake.signInAs(who);
    addTearDown(() async {
      await tester.pumpWidget(const SizedBox());
      fake.services.physicianFeed.stop();
      fake.dispose();
    });
    return fake;
  }

  Future<void> tap(WidgetTester tester, String label) async {
    await tester.ensureVisible(find.text(label));
    await tester.tap(find.text(label));
    await tester.pumpAndSettle();
  }

  /// The call for Okafor's sent sample offer, already answered.
  Future<FakeServices> answered(WidgetTester tester, {Uint8List? audio}) async {
    final fake = await prepare(tester, 'okafor');
    fake.offers.audio = audio;
    final offer = await fake.offers.getOffer('OFF-0007');
    await tester.pumpWidget(
      SevaroApp(
        home: IncomingCallScreen(services: fake.services, offer: offer),
      ),
    );
    await tester.pumpAndSettle();
    await tap(tester, 'Answer');
    return fake;
  }

  testWidgets(
    'a new sent offer rings once; declining the call changes nothing',
    (tester) async {
      final fake = await prepare(tester, 'brennan');
      await fake.auth.setOptIn(true);
      await tester.pumpWidget(
        SevaroApp(
          home: ServiceSession(
            services: fake.services,
            me: fake.auth.me.value!,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('Sevaro Coverage Call'), findsNothing);

      final id = fake.offers.pushNewOffer();
      await fake.services.physicianFeed.refreshNow();
      await tester.pumpAndSettle();
      expect(find.text('Sevaro Coverage Call'), findsOneWidget);
      expect(find.text('Synthetic demonstration'), findsOneWidget);
      expect(find.text('Suncrest Medical Pavilion'), findsOneWidget);
      expect(find.text('19:00–23:00 ET · 4 h'), findsOneWidget);
      expect(find.textContaining('Answer within '), findsOneWidget);
      expect(alerts.ringing, isTrue);

      await tap(tester, 'Decline call');
      expect(find.text('Sevaro Coverage Call'), findsNothing);
      expect(alerts.ringing, isFalse);
      expect((await fake.offers.getOffer(id)).status, OfferStatus.sent);

      await fake.services.physicianFeed.refreshNow();
      await tester.pumpAndSettle();
      expect(find.text('Sevaro Coverage Call'), findsNothing);
      expect(alerts.rings, 1);
    },
  );

  testWidgets('accept shows the accepted outcome', (tester) async {
    await answered(tester);
    await tap(tester, 'Accept shift');
    expect(
      find.text("You're on Suncrest Medical Pavilion 19:00–23:00 ET"),
      findsOneWidget,
    );
    expect(find.text('Accept shift'), findsNothing);
  });

  testWidgets('accept shows already_filled when another physician won', (
    tester,
  ) async {
    final fake = await answered(tester);
    fake.offers.fillByOther('OFF-0007');
    await tap(tester, 'Accept shift');
    expect(find.text('Another physician took this shift'), findsOneWidget);
  });

  testWidgets('accept after the server expiry shows expired', (tester) async {
    final fake = await answered(tester);
    fake.clock.advance(const Duration(minutes: 11));
    await tap(tester, 'Accept shift');
    expect(find.text('This offer expired'), findsOneWidget);
  });

  testWidgets('audio 503 hides the play button and keeps the text', (
    tester,
  ) async {
    await answered(tester);
    expect(alerts.plays, 0);
    expect(find.text('Play message again'), findsNothing);
    expect(
      find.text(
        "Suncrest will be one physician short from 19:00. You'd be the second.",
      ),
      findsOneWidget,
    );
    expect(find.text('Accept shift'), findsOneWidget);
    expect(find.text('Decline shift'), findsOneWidget);
  });

  testWidgets('answering plays the server audio and stops the ring', (
    tester,
  ) async {
    await answered(tester, audio: Uint8List.fromList([1, 2, 3]));
    expect(alerts.ringing, isFalse);
    expect(alerts.plays, 1);
    expect(find.text('Play message again'), findsOneWidget);
  });

  testWidgets('the call ends when the feed says the offer was filled', (
    tester,
  ) async {
    final fake = await prepare(tester, 'okafor');
    fake.services.physicianFeed.start();
    final offer = await fake.offers.getOffer('OFF-0007');
    await tester.pumpWidget(
      SevaroApp(
        home: IncomingCallScreen(services: fake.services, offer: offer),
      ),
    );
    await tester.pumpAndSettle();
    fake.offers.fillByOther('OFF-0007');
    await fake.services.physicianFeed.refreshNow();
    await tester.pumpAndSettle();
    expect(find.text('Another physician took this shift'), findsOneWidget);
    expect(find.text('Answer'), findsNothing);
    expect(alerts.ringing, isFalse);
    await tester.pumpWidget(const SizedBox());
    fake.services.physicianFeed.stop();
  });
}
