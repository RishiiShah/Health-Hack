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
      // The call may have rung without a tap (browsers then block sound);
      // Answer is a tap, so unlock playback here, before the audio fetch.
      if (!s.alerts.soundEnabled) await s.alerts.enableSound();
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
    final result = _result;
    final ringing = result == null && !_answered;
    final hours = _offer.hours == _offer.hours.roundToDouble()
        ? _offer.hours.toStringAsFixed(0)
        : _offer.hours.toString();
    final accepted =
        _outcome == OfferOutcome.accepted ||
        (_outcome == null && _offer.status == OfferStatus.accepted);
    return Scaffold(
      backgroundColor: _night,
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF1E2A40), _night],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(24, 20, 24, 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Align(child: _Chip('Synthetic demonstration')),
                    const SizedBox(height: 28),
                    Text(
                      result != null
                          ? 'CALL ENDED'
                          : _answered
                          ? 'ON CALL'
                          : 'INCOMING CALL',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontFamily: OverlapStyle.mono,
                        fontSize: 12,
                        letterSpacing: 2.4,
                        color: _mint,
                      ),
                    ),
                    const SizedBox(height: 20),
                    Center(
                      child: _Avatar(pulsing: ringing, done: result != null),
                    ),
                    const SizedBox(height: 20),
                    Semantics(
                      header: true,
                      child: const Text(
                        'Sevaro Coverage Call',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontFamily: OverlapStyle.heading,
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    const Text(
                      'Sevaro Operations · split-shift request',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: _soft),
                    ),
                    const SizedBox(height: 24),
                    _Panel(
                      children: [
                        Text(
                          _hospital,
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.w700,
                            color: Colors.white,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '$_hours · $hours h',
                          textAlign: TextAlign.center,
                          style: const TextStyle(
                            fontFamily: OverlapStyle.mono,
                            fontSize: 15,
                            color: Color(0xFFE2E8F0),
                          ),
                        ),
                        if (result == null) ...[
                          const SizedBox(height: 12),
                          ClockBuilder(
                            clock: s.clock,
                            builder: (_) => Text(
                              '${_answered ? 'Reply' : 'Answer'} within ${formatCountdown(s.clock.remaining(_offer.expiresAt))}',
                              textAlign: TextAlign.center,
                              style: const TextStyle(
                                fontFamily: OverlapStyle.mono,
                                fontWeight: FontWeight.w600,
                                color: Color(0xFFFCD34D),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                    if (result != null) ...[
                      const SizedBox(height: 24),
                      Icon(
                        accepted ? Icons.check_circle : Icons.info_outline,
                        size: 40,
                        color: accepted ? _mint : _soft,
                      ),
                      const SizedBox(height: 10),
                      Text(
                        result,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(height: 24),
                      _Pill(
                        label: 'Close',
                        filled: true,
                        onPressed: () => Navigator.of(context).pop(),
                      ),
                    ] else if (ringing) ...[
                      const SizedBox(height: 40),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                        children: [
                          _RoundAction(
                            label: 'Decline call',
                            icon: Icons.call_end,
                            color: const Color(0xFFDC2626),
                            onPressed: () => Navigator.of(context).pop(),
                          ),
                          _RoundAction(
                            label: 'Answer',
                            icon: Icons.call,
                            color: OverlapStyle.teal,
                            onPressed: _answer,
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      const Text(
                        'Declining the call keeps the request open in Offers.',
                        textAlign: TextAlign.center,
                        style: TextStyle(fontSize: 13, color: _faint),
                      ),
                    ] else ...[
                      const SizedBox(height: 16),
                      _Panel(
                        children: [
                          Row(
                            children: [
                              Icon(
                                _audioAvailable
                                    ? Icons.graphic_eq
                                    : Icons.notes,
                                color: _mint,
                                size: 20,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  _loadingAudio
                                      ? 'Connecting…'
                                      : _audioAvailable
                                      ? 'Spoken offer from Sevaro'
                                      : 'Offer details',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    color: _mint,
                                  ),
                                ),
                              ),
                              if (_loadingAudio)
                                const SizedBox.square(
                                  dimension: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: _mint,
                                    semanticsLabel: 'Loading the spoken offer',
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Text(
                            _offer.gapSummary,
                            style: const TextStyle(
                              color: Color(0xFFE2E8F0),
                              height: 1.4,
                            ),
                          ),
                          if (_audioAvailable && !_loadingAudio) ...[
                            const SizedBox(height: 8),
                            Align(
                              alignment: Alignment.centerLeft,
                              child: TextButton.icon(
                                onPressed: _replay,
                                style: TextButton.styleFrom(
                                  foregroundColor: Colors.white,
                                ),
                                icon: const Icon(Icons.replay, size: 18),
                                label: const Text('Play message again'),
                              ),
                            ),
                          ],
                        ],
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
                          _Pill(
                            label: action == OfferAction.accept
                                ? 'Accept shift'
                                : 'Decline shift',
                            filled: action == OfferAction.accept,
                            onPressed: _busy ? null : () => _respond(action),
                          ),
                        ],
                    ],
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

const _night = Color(0xFF111827);
const _mint = Color(0xFF5EEAD4);
const _soft = Color(0xFFCBD5E1);
const _faint = Color(0xFF94A3B8);

class _Chip extends StatelessWidget {
  const _Chip(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .08),
      borderRadius: BorderRadius.circular(999),
      border: Border.all(color: Colors.white.withValues(alpha: .14)),
    ),
    child: Text(text, style: const TextStyle(fontSize: 12, color: _soft)),
  );
}

class _Panel extends StatelessWidget {
  const _Panel({required this.children});
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .07),
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: Colors.white.withValues(alpha: .1)),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: children,
    ),
  );
}

/// The caller badge. While ringing it pulses: a timer flips an implicit
/// animation (so widget tests still settle); reduced motion keeps it still.
class _Avatar extends StatefulWidget {
  const _Avatar({required this.pulsing, required this.done});
  final bool pulsing;
  final bool done;
  @override
  State<_Avatar> createState() => _AvatarState();
}

class _AvatarState extends State<_Avatar> {
  Timer? _timer;
  bool _big = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _sync();
  }

  @override
  void didUpdateWidget(_Avatar old) {
    super.didUpdateWidget(old);
    _sync();
  }

  void _sync() {
    final animate = widget.pulsing && !MediaQuery.of(context).disableAnimations;
    if (animate && _timer == null) {
      _timer = Timer.periodic(
        const Duration(milliseconds: 1200),
        (_) => setState(() => _big = !_big),
      );
    } else if (!animate) {
      _timer?.cancel();
      _timer = null;
      _big = false;
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: AnimatedContainer(
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeInOut,
      width: 132,
      height: 132,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: OverlapStyle.teal.withValues(alpha: _big ? .10 : .22),
        border: Border.all(
          color: _mint.withValues(
            alpha: widget.pulsing ? (_big ? .15 : .5) : .25,
          ),
          width: _big ? 14 : 4,
        ),
      ),
      child: Container(
        width: 88,
        height: 88,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: widget.done ? const Color(0xFF334155) : OverlapStyle.teal,
        ),
        child: const Text(
          'S',
          style: TextStyle(
            fontFamily: OverlapStyle.heading,
            fontSize: 40,
            fontWeight: FontWeight.w700,
            color: Colors.white,
          ),
        ),
      ),
    ),
  );
}

/// A round call button with its label underneath. The whole column is the
/// tap target, so the label is part of the button.
class _RoundAction extends StatelessWidget {
  const _RoundAction({
    required this.label,
    required this.icon,
    required this.color,
    required this.onPressed,
  });
  final String label;
  final IconData icon;
  final Color color;
  final VoidCallback onPressed;
  @override
  Widget build(BuildContext context) => Semantics(
    button: true,
    child: InkWell(
      onTap: onPressed,
      borderRadius: BorderRadius.circular(24),
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 76,
              height: 76,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: color,
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: .45),
                    blurRadius: 24,
                    offset: const Offset(0, 8),
                  ),
                ],
              ),
              child: Icon(icon, color: Colors.white, size: 34),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.label,
    required this.filled,
    required this.onPressed,
  });
  final String label;
  final bool filled;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) {
    const shape = StadiumBorder();
    const size = Size.fromHeight(54);
    return filled
        ? FilledButton(
            onPressed: onPressed,
            style: FilledButton.styleFrom(
              backgroundColor: OverlapStyle.teal,
              foregroundColor: Colors.white,
              minimumSize: size,
              shape: shape,
            ),
            child: Text(label),
          )
        : OutlinedButton(
            onPressed: onPressed,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: BorderSide(color: Colors.white.withValues(alpha: .35)),
              minimumSize: size,
              shape: shape,
            ),
            child: Text(label),
          );
  }
}
