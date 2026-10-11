// Debug entry for checking the phone app on the fake backend, without the
// dummy web dashboard. Not part of the app; run it with its own entry point:
//   flutter run -d chrome -t lib/dev/phone_app.dart
// Sign in with okafor@demo.sevaro / demo (physician) or lead@demo.sevaro / demo.
// "New call" pushes a new `sent` offer, which rings the simulated coverage call.
import 'package:flutter/material.dart';

import '../data/fake/fakes.dart';
import '../main.dart';
import '../screens/auth_gate.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final fake = FakeServices(autoAnswer: false);
  runApp(
    SevaroApp(
      home: Stack(
        children: [
          RepositoryAuthGate(services: fake.services),
          Positioned(
            right: 12,
            bottom: 96,
            child: FloatingActionButton.extended(
              onPressed: () {
                fake.offers.pushNewOffer();
                fake.services.physicianFeed.refreshNow();
              },
              label: const Text('New call'),
            ),
          ),
        ],
      ),
    ),
  );
}
