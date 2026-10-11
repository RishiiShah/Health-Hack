import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import '../data/api.dart';
import '../data/fake/fakes.dart';
import '../data/platform/browser.dart';
import 'data_widgets.dart';
import 'service_session.dart';
import 'shared.dart';

/// Explicit debug-only entrance to the integrated app while live auth is deferred.
class DemoWorkspace extends StatefulWidget {
  const DemoWorkspace({super.key});
  @override
  State<DemoWorkspace> createState() => _DemoWorkspaceState();
}

class _DemoWorkspaceState extends State<DemoWorkspace> {
  late final FakeServices _fake = FakeServices(browser: _DemoBrowser());
  Me? _me;
  String? _error;
  bool _busy = false;
  Future<void> _choose(String who) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final me = await _fake.signInAs(who);
      if (mounted) setState(() => _me = me);
    } catch (error) {
      if (mounted) setState(() => _error = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _reset() {
    _fake.clock.set(kFakeStart);
    // Role changes preserve this demo backend; a new workspace resets all data.
    _fake.services.physicianFeed.refreshNow();
    _fake.services.leadFeed.refreshNow();
  }

  @override
  void dispose() {
    _fake.services.physicianFeed.stop();
    _fake.services.leadFeed.stop();
    _fake.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (!kDebugMode) {
      return const ErrorScreen(
        message: 'Demo workspace is available only in development.',
      );
    }
    if (_me == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Working demo')),
        body: ScreenBody(
          children: [
            const Notice(
              'Synthetic demo data. Choose a role to use the connected app. Roles share data within this workspace.',
            ),
            for (final account in const [
              ('lead', 'Clinical lead'),
              ('shah', 'Physician · on shift'),
              ('okafor', 'Physician · off shift'),
              ('brennan', 'Physician · opted out'),
            ])
              Padding(
                padding: const EdgeInsets.only(top: 16),
                child: FilledButton(
                  onPressed: _busy ? null : () => _choose(account.$1),
                  child: Text(account.$2),
                ),
              ),
            if (_error != null) Notice(_error!, isError: true),
          ],
        ),
      );
    }
    return Column(
      children: [
        Material(
          color: const Color(0xFF172831),
          child: SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                'WORKING DEMO · synthetic data',
                style: Theme.of(
                  context,
                ).textTheme.labelLarge?.copyWith(color: Colors.white),
              ),
            ),
          ),
        ),
        Expanded(
          child: ServiceSession(
            key: ValueKey(_me!.userId),
            services: _fake.services,
            me: _me!,
            onEnded: () => setState(() => _me = null),
            actions: [
              PopupMenuButton<String>(
                tooltip: 'Demo controls',
                onSelected: (value) async {
                  if (value == 'roles') {
                    await _fake.auth.signOut();
                  }
                  if (value == 'advance') {
                    _fake.clock.advance(const Duration(minutes: 11));
                    await _fake.services.physicianFeed.refreshNow();
                    await _fake.services.leadFeed.refreshNow();
                  }
                  if (value == 'offer') {
                    _fake.offers.pushNewOffer();
                    await _fake.services.physicianFeed.refreshNow();
                  }
                  if (value == 'clock') _reset();
                },
                itemBuilder: (_) => [
                  const PopupMenuItem(
                    value: 'roles',
                    child: Text('Choose another role'),
                  ),
                  const PopupMenuItem(
                    value: 'advance',
                    child: Text('Advance demo clock 11 min'),
                  ),
                  if (_me!.role == Role.physician)
                    const PopupMenuItem(
                      value: 'offer',
                      child: Text('Send new demo request'),
                    ),
                  const PopupMenuItem(
                    value: 'clock',
                    child: Text('Reset demo clock'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// Keep demo tokens in memory while honoring the real browser's visibility.
class _DemoBrowser extends MemoryBrowser {
  @override
  bool get hidden => sharedBrowser.hidden;
  @override
  Stream<bool> get visibilityChanges => sharedBrowser.visibilityChanges;
}
