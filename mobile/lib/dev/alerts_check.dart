// Debug page for task 11: chime, vibration and tab-title badge on a real phone.
// Not part of the app; run it with its own entry point:
//   flutter run -d chrome -t lib/dev/alerts_check.dart --dart-define-from-file=config/fake.json
//   flutter build web -t lib/dev/alerts_check.dart --dart-define-from-file=config/fake.json
import 'package:flutter/material.dart';

import '../data/api.dart';
import '../data/fake/fakes.dart';

void main() => runApp(const _AlertsCheckApp());

class _AlertsCheckApp extends StatelessWidget {
  const _AlertsCheckApp();

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Alerts check',
    theme: ThemeData(useMaterial3: true),
    home: const _AlertsCheckPage(),
  );
}

class _AlertsCheckPage extends StatefulWidget {
  const _AlertsCheckPage();

  @override
  State<_AlertsCheckPage> createState() => _AlertsCheckPageState();
}

class _AlertsCheckPageState extends State<_AlertsCheckPage> {
  final _fake = FakeServices();
  late final AppServices _s = _fake.services;
  bool _signedIn = false;

  @override
  void initState() {
    super.initState();
    // Same reaction the app has to a new offer: chime, vibrate, tab-title badge.
    _s.physicianFeed.newOffer.listen((offer) {
      _s.alerts.chime();
      _s.alerts.vibrate();
      _s.alerts.setBadge(1);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'New offer ${offer.offerId} · ${offer.hospitals.map((h) => h.name).join(', ')}',
          ),
        ),
      );
    });
  }

  @override
  void dispose() {
    _s.physicianFeed.stop();
    _fake.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    await _fake.signInAs('okafor');
    _s.physicianFeed.start();
    setState(() => _signedIn = true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Alerts check')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          ValueListenableBuilder<DateTime>(
            valueListenable: _s.clock.ticks,
            builder: (_, now, _) => Text(
              formatEtHeader(now),
              style: Theme.of(context).textTheme.headlineSmall,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Sound: ${_s.alerts.soundEnabled ? 'enabled' : 'not enabled (tap Enable sound first)'}',
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton(
                onPressed: () async {
                  await _s.alerts.enableSound();
                  setState(() {});
                },
                child: const Text('Enable sound'),
              ),
              FilledButton.tonal(
                onPressed: _s.alerts.chime,
                child: const Text('Chime'),
              ),
              FilledButton.tonal(
                onPressed: _s.alerts.vibrate,
                child: const Text('Vibrate'),
              ),
              OutlinedButton(
                onPressed: () => _s.alerts.setBadge(1),
                child: const Text('Badge 1'),
              ),
              OutlinedButton(
                onPressed: () => _s.alerts.setBadge(0),
                child: const Text('Badge 0'),
              ),
            ],
          ),
          const Divider(height: 32),
          FilledButton(
            onPressed: _signedIn ? null : _signIn,
            child: Text(
              _signedIn
                  ? 'Signed in as okafor (fake)'
                  : 'Sign in as okafor (fake)',
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'Signing in starts the physician feed. Okafor already has one open offer, so it '
            'shows as a new offer right away, with the chime, vibration and badge.',
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _signedIn ? _fake.offers.pushNewOffer : null,
            child: const Text('Push another new offer (fake)'),
          ),
        ],
      ),
    );
  }
}
