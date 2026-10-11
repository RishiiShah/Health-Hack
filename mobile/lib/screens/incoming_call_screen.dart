import 'dart:async';

import 'package:flutter/material.dart';

import '../data/api.dart';
import 'data_widgets.dart';
import 'shared.dart';
import 'theme.dart';

/// The simulated coverage call for one `sent` offer: it rings, the physician
/// answers, the server's audio plays, then they accept or decline the shift.
/// Display only: the server decides expiry, eligibility and who wins the gap.
class IncomingCallScreen extends StatefulWidget {
  const IncomingCallScreen({
    super.key,
    required this.services,
    required this.offer,
  });
  final AppServices services;
  final Offer offer;
  @override
  State<IncomingCallScreen> createState() => _IncomingCallScreenState();
}

class _IncomingCallScreenState extends State<IncomingCallScreen> {
  late Offer _offer = widget.offer;
  bool _answered = false;
  bool _loadingAudio = false;
  bool _audioAvailable = false;
  bool _busy = false;
  OfferOutcome? _outcome;
  String? _error;
  AppServices get s => widget.services;

  @override
  void initState() {
    super.initState();
    s.physicianFeed.offers.addListener(_feedChanged);
    s.alerts.startRing();
    s.alerts.vibrate();
  }

  @override
  void dispose() {
    s.physicianFeed.offers.removeListener(_feedChanged);
    s.alerts.stopSound();
    super.dispose();
  }

  // The offer can expire or be filled while the call is on screen.
  void _feedChanged() {
    if (_busy || _outcome != null) return;
    final offer = s.physicianFeed.offers.value.data?.offers
        .where((o) => o.offerId == _offer.offerId)
        .firstOrNull;
    if (offer == null || !mounted) return;
    if (offer.status != OfferStatus.sent) s.alerts.stopSound();
    setState(() => _offer = offer);
  }

  Future<void> _answer() async {
    s.alerts.stopSound();
    setState(() {
      _answered = true;
      _loadingAudio = true;
    });
    var available = false;
    try {
      final audio = await s.offers.getOfferAudio(_offer.offerId);
      if (!mounted) return;
      await s.alerts.play(audio);
      available = true;
    } catch (_) {
      // No audio (503, blocked playback, offline): the text below is the offer.
    }
    if (!mounted) return;
    setState(() {
      _loadingAudio = false;
      _audioAvailable = available;
    });
  }

  Future<void> _replay() async {
    try {
      await s.alerts.play(await s.offers.getOfferAudio(_offer.offerId));
    } catch (_) {
      if (mounted) setState(() => _audioAvailable = false);
    }
  }

  Future<void> _respond(OfferAction action) async {
    if (_busy) return;
    s.alerts.stopSound();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final result = action == OfferAction.accept
          ? await s.offers.accept(_offer.offerId)
          : await s.offers.decline(_offer.offerId);
      if (!mounted) return;
      setState(() {
        _offer = result.offer;
        _outcome = result.outcome;
      });
      unawaited(s.physicianFeed.refreshNow());
    } catch (error) {
      if (mounted) setState(() => _error = errorText(error));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String get _hospital => hospitalsLabel(_offer.hospitals);
  String get _hours => formatEtRange(_offer.start, _offer.end);

  /// The server's answer, or the server's status if the offer closed meanwhile.
  String? get _result {
    switch (_outcome) {
      case OfferOutcome.accepted:
        return "You're on $_hospital $_hours";
      case OfferOutcome.alreadyFilled:
        return 'Another physician took this shift';
      case OfferOutcome.expired:
        return 'This offer expired';
      case OfferOutcome.declined:
        return 'You declined this shift';
      case OfferOutcome.notOpen:
      case OfferOutcome.released:
        return 'This offer is no longer open';
      case null:
        return switch (_offer.status) {
          OfferStatus.sent => null,
          OfferStatus.accepted => "You're on $_hospital $_hours",
          OfferStatus.declined => 'You declined this shift',
          OfferStatus.expired => 'This offer expired',
          OfferStatus.withdrawn =>
            _offer.statusReason == StatusReason.filledByAnotherPhysician
                ? 'Another physician took this shift'
                : 'This offer is no longer open',
          OfferStatus.released => 'This offer is no longer open',
        };
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final result = _result;
    final hours = _offer.hours == _offer.hours.roundToDouble()
        ? _offer.hours.toStringAsFixed(0)
        : _offer.hours.toString();
    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        title: const Text('Sevaro Coverage Call'),
      ),
      body: ScreenBody(
        children: [
          Align(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Notice('Synthetic demonstration'),
                  const SizedBox(height: 24),
                  Text(
                    result != null
                        ? 'Call ended'
                        : _answered
                        ? 'Coverage request'
                        : 'Incoming call',
                    style: text.labelLarge?.copyWith(color: OverlapStyle.muted),
                  ),
                  const SizedBox(height: 8),
                  Text(_hospital, style: text.headlineMedium),
                  const SizedBox(height: 8),
                  Text('$_hours · $hours h', style: text.titleMedium),
                  const SizedBox(height: 24),
                  if (result != null) ...[
                    Text(result, style: text.headlineSmall),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('Close'),
                    ),
                  ] else ...[
                    ClockBuilder(
                      clock: s.clock,
                      builder: (_) => Text(
                        'Answer within ${formatCountdown(s.clock.remaining(_offer.expiresAt))}',
                        style: text.titleLarge?.copyWith(
                          fontFamily: OverlapStyle.mono,
                          color: OverlapStyle.tealDark,
                        ),
                      ),
                    ),
                    const SizedBox(height: 24),
                    if (!_answered) ...[
                      FilledButton(
                        onPressed: _answer,
                        child: const Text('Answer'),
                      ),
                      const SizedBox(height: 12),
                      OutlinedButton(
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Decline call'),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Declining the call keeps the request open in Offers.',
                      ),
                    ] else ...[
                      Text(_offer.gapSummary),
                      const SizedBox(height: 16),
                      if (_loadingAudio)
                        const Center(
                          child: CircularProgressIndicator(
                            semanticsLabel: 'Loading the spoken offer',
                          ),
                        )
                      else if (_audioAvailable)
                        TextButton(
                          onPressed: _replay,
                          child: const Text('Play message again'),
                        ),
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        Notice(_error!, isError: true),
                      ],
                      for (final action in [
                        OfferAction.accept,
                        OfferAction.decline,
                      ])
                        if (_offer.allows(action)) ...[
                          const SizedBox(height: 12),
                          action == OfferAction.accept
                              ? FilledButton(
                                  onPressed: _busy
                                      ? null
                                      : () => _respond(action),
                                  child: const Text('Accept shift'),
                                )
                              : OutlinedButton(
                                  onPressed: _busy
                                      ? null
                                      : () => _respond(action),
                                  child: const Text('Decline shift'),
                                ),
                        ],
                    ],
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
