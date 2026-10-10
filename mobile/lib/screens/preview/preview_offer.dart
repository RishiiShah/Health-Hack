import 'package:flutter/material.dart';

import '../offer_detail_screen.dart';
import 'preview_widgets.dart';

/// Local, deterministic screen scenarios, not an Auth/OfferRepository fake.
class PreviewOffer extends StatefulWidget {
  const PreviewOffer({super.key, this.initialScenario = 'sent'});
  final String initialScenario;

  @override
  State<PreviewOffer> createState() => _PreviewOfferState();
}

class _PreviewOfferState extends State<PreviewOffer> {
  late String _scenario = widget.initialScenario;
  late final ValueNotifier<Duration> _remaining = ValueNotifier(
    _scenario == 'expiring'
        ? Duration.zero
        : const Duration(minutes: 9, seconds: 41),
  );
  String? _outcome;
  int _revision = 0;

  static const _scenarios = {
    'sent': 'New request',
    'accepted': 'Accepted',
    'declined': 'Declined',
    'expired': 'Missed',
    'filled': 'Already filled',
    'closed': 'No longer needed',
    'released': 'Released',
    'expiring': 'Expiring at 0:00',
    'race': 'Accept returns already filled',
    'late': 'Accept returns expired',
    'forbidden': 'Permission error on response',
  };

  @override
  void dispose() {
    _remaining.dispose();
    super.dispose();
  }

  void _select(String scenario) {
    setState(() {
      _scenario = scenario;
      _outcome = null;
      _revision++;
    });
    _remaining.value = scenario == 'expiring'
        ? Duration.zero
        : const Duration(minutes: 9, seconds: 41);
  }

  Future<String?> _respond(String action) async {
    final revision = _revision;
    final scenario = _scenario;
    // A visible pending state for device review. Never contacts the network.
    await Future<void>.delayed(const Duration(milliseconds: 650));
    if (!mounted || revision != _revision) return null;
    if (scenario == 'forbidden') return "You don't have permission for this.";
    setState(() {
      _outcome = action == 'accept' && scenario == 'race'
          ? 'already_filled'
          : action == 'accept' && scenario == 'late'
          ? 'expired'
          : switch (action) {
              'accept' => 'accepted',
              'decline' => 'declined',
              _ => 'released',
            };
    });
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final status = switch (_scenario) {
      'expiring' || 'race' || 'late' || 'forbidden' => 'sent',
      'filled' || 'closed' => 'withdrawn',
      _ => _scenario,
    };
    final accepted =
        _outcome == 'accepted' || (_outcome == null && status == 'accepted');
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Material(
              color: Colors.white,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                child: Column(
                  children: [
                    DropdownButton<String>(
                      isExpanded: true,
                      value: _scenario,
                      items: [
                        for (final item in _scenarios.entries)
                          DropdownMenuItem(
                            value: item.key,
                            child: Text(item.value),
                          ),
                      ],
                      onChanged: (value) {
                        if (value != null) _select(value);
                      },
                    ),
                    Wrap(
                      spacing: 8,
                      children: [
                        TextButton.icon(
                          onPressed: () => _select(_scenario),
                          icon: const Icon(Icons.restart_alt),
                          label: const Text('Reset'),
                        ),
                        TextButton(
                          onPressed: () {
                            final seconds = (_remaining.value.inSeconds - 60)
                                .clamp(0, 600);
                            _remaining.value = Duration(seconds: seconds);
                          },
                          child: const Text('Advance 1 min'),
                        ),
                        TextButton(
                          onPressed: () => _remaining.value = Duration.zero,
                          child: const Text('Set 0:00'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: OfferDetailScreen(
                key: ValueKey(_revision),
                offerId: 'PREVIEW-OFFER',
                hospital: 'Suncrest Medical Pavilion',
                hoursEt: '19:00 to 23:00 ET',
                signInByEt: '18:55 ET',
                expiresAtEt: '18:35 ET',
                gapSummary:
                    "Suncrest will be one physician short from 19:00. You'd be the second.",
                whyYou: const [
                  'Credentialed at Suncrest',
                  '12 h rested since your last shift',
                  '40 of 60 h this week, so you stay under the limit',
                ],
                status: status,
                statusReason: _scenario == 'filled'
                    ? 'filled_by_another_physician'
                    : _scenario == 'closed'
                    ? 'gap_closed'
                    : null,
                outcome: _outcome,
                allowedActions: accepted
                    ? {'release'}
                    : _outcome == null && status == 'sent'
                    ? {'accept', 'decline'}
                    : {},
                remaining: _remaining,
                onAction: _respond,
                routingHospitals: const ['Suncrest Medical Pavilion'],
                coverageAfter: 'Suncrest now shows 2 of 2 from 19:00 ET.',
                nextSteps: const [
                  '18:50 ET · Reminder to sign in',
                  '19:00 ET · Consults start arriving in My shift',
                  '23:00 ET · Shift ends, routing stops',
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class PreviewLockScreen extends StatelessWidget {
  const PreviewLockScreen({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
    backgroundColor: const Color(0xFFE1E8E4),
    appBar: AppBar(
      backgroundColor: Colors.transparent,
      title: const Text('Simulated lock screen'),
    ),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 24),
            const Text('Tuesday 17 March', textAlign: TextAlign.center),
            const Text(
              '18:23',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 68,
                fontWeight: FontWeight.w300,
                color: previewInk,
              ),
            ),
            const Text('ET', textAlign: TextAlign.center),
            const SizedBox(height: 32),
            Semantics(
              button: true,
              label: 'Open extra shift request',
              child: Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(24),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) =>
                          const PreviewSurface(child: PreviewOffer()),
                    ),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Sevaro · now',
                          style: TextStyle(
                            color: previewTeal,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 10),
                        Text(
                          'Extra shift tonight at Suncrest',
                          style: TextStyle(
                            fontWeight: FontWeight.w800,
                            fontSize: 18,
                          ),
                        ),
                        SizedBox(height: 8),
                        Text(
                          '19:00 to 23:00 ET, approved by your clinical lead. Please answer within 10 min.',
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 16),
            const PreviewCard(
              children: [
                Text('Sevaro · Mon 08:02 ET'),
                SizedBox(height: 8),
                Text('Your next shift: Wed 18 Mar, 19:00 ET.'),
              ],
            ),
            const SizedBox(height: 40),
            const Text(
              "Dr. Okafor's phone · off shift · simulated",
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    ),
  );
}
