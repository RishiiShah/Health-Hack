import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'shared.dart';
import 'theme.dart';

/// Repository adapters update this widget from the returned offer/outcome,
/// then return null, or return a mapped error message. No optimistic updates.
typedef OfferActionCallback = Future<String?> Function(String action);

/// Presentation only: the parent supplies ET-formatted times and remaining
/// duration from ServerClock, plus enum names from Chandan's parsed DTOs.
class OfferDetailScreen extends StatefulWidget {
  const OfferDetailScreen({
    super.key,
    required this.offerId,
    required this.hospital,
    required this.hoursEt,
    required this.signInByEt,
    required this.expiresAtEt,
    required this.gapSummary,
    required this.whyYou,
    required this.status,
    required this.allowedActions,
    required this.remaining,
    required this.onAction,
    this.statusReason,
    this.outcome,
    this.routingHospitals = const [],
    this.nextSteps = const [],
    this.coverageAfter,
    this.reconnecting = false,
  });

  final String offerId;
  final String hospital;
  final String hoursEt;
  final String signInByEt;
  final String expiresAtEt;
  final String gapSummary;
  final List<String> whyYou;
  final String status;
  final String? statusReason;
  final String? outcome;
  final Set<String> allowedActions;
  final ValueListenable<Duration> remaining;
  final OfferActionCallback onAction;
  final List<String> routingHospitals;
  final List<String> nextSteps;
  final String? coverageAfter;
  final bool reconnecting;

  @override
  State<OfferDetailScreen> createState() => _OfferDetailScreenState();
}

class _OfferDetailScreenState extends State<OfferDetailScreen> {
  bool _busy = false;
  bool _confirming = false;
  String? _error;

  // Outcomes have precedence over the tapped action and the prior offer status.
  String get _state {
    if (widget.outcome != null) {
      return switch (widget.outcome) {
        'accepted' || 'declined' || 'expired' || 'released' => widget.outcome!,
        'already_filled' => 'filled',
        'not_open' => 'closed',
        _ => 'unknown',
      };
    }
    if (widget.status == 'withdrawn') {
      return switch (widget.statusReason) {
        'filled_by_another_physician' => 'filled',
        'gap_closed' => 'closed',
        _ => 'unknown',
      };
    }
    return widget.status;
  }

  bool _canAct(String action) {
    if (!widget.allowedActions.contains(action)) return false;
    if (action == 'release') return _state == 'accepted';
    return _state == 'sent' && widget.remaining.value > Duration.zero;
  }

  Future<void> _act(String action) async {
    if (_busy || _confirming || !_canAct(action)) return;
    final offerId = widget.offerId;
    setState(() {
      _confirming = true;
      _error = null;
    });
    final title = switch (action) {
      'accept' => 'Accept this shift?',
      'decline' => 'Decline this request?',
      _ => "Can't make this shift?",
    };
    final message = switch (action) {
      'accept' => 'Cover ${widget.hospital}, ${widget.hoursEt}?',
      'decline' => "Declining doesn't change your schedule.",
      _ => "Let your clinical lead know you can't make it.",
    };
    final confirmed = await confirmAction(
      context,
      title: title,
      message: message,
      confirmLabel: switch (action) {
        'accept' => 'Confirm acceptance',
        'decline' => 'Decline request',
        _ => 'Notify clinical lead',
      },
    );
    if (!mounted) return;
    setState(() => _confirming = false);
    // The feed or clock may have changed while the confirmation was open.
    if (!confirmed || offerId != widget.offerId || !_canAct(action)) return;
    setState(() => _busy = true);
    String? error;
    try {
      error = await widget.onAction(action);
    } catch (_) {
      error = "Can't reach Sevaro. Please try again.";
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (offerId == widget.offerId) _error = error;
    });
  }

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<Duration>(
    valueListenable: widget.remaining,
    builder: (context, remaining, _) {
      final state = _state;
      final title = switch (state) {
        'sent' => 'New request',
        'accepted' => "You're on",
        'declined' => 'Declined',
        'expired' => 'Missed',
        'filled' => 'Already filled',
        'closed' => 'No longer needed',
        'released' => 'Released',
        _ => null,
      };
      if (title == null) {
        return const ErrorScreen(
          message: 'This request has an unrecognized status.',
        );
      }
      final seconds = remaining.inSeconds.clamp(0, 86400000);
      final countdown =
          '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
      return Scaffold(
        appBar: AppBar(title: Text(title)),
        body: ScreenBody(
          children: [
            Align(
              alignment: Alignment.topCenter,
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 520),
                child: Container(
                  padding: const EdgeInsets.all(24),
                  decoration: OverlapStyle.panel().copyWith(
                    border: const Border(
                      top: BorderSide(color: OverlapStyle.teal, width: 4),
                      left: BorderSide(color: OverlapStyle.line),
                      right: BorderSide(color: OverlapStyle.line),
                      bottom: BorderSide(color: OverlapStyle.line),
                    ),
                    borderRadius: BorderRadius.zero,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (widget.reconnecting) ...[
                        const Notice('Reconnecting…'),
                        const SizedBox(height: 16),
                      ],
                      if (state == 'sent') ...[
                        const Text('Approved by your clinical lead'),
                        const SizedBox(height: 16),
                        Semantics(
                          label: remaining <= Duration.zero
                              ? 'Expiring'
                              : 'Time remaining $countdown',
                          child: ExcludeSemantics(
                            child: Text(
                              remaining <= Duration.zero
                                  ? 'Expiring…'
                                  : countdown,
                              style: Theme.of(context).textTheme.displaySmall
                                  ?.copyWith(
                                    fontFamily: OverlapStyle.mono,
                                    color: OverlapStyle.tealDark,
                                  ),
                            ),
                          ),
                        ),
                        const SizedBox(height: 24),
                        Text(
                          'Cover ${widget.hospital} tonight?',
                          style: Theme.of(context).textTheme.headlineMedium,
                        ),
                        const SizedBox(height: 12),
                        Text(widget.gapSummary),
                      ] else ...[
                        Text(switch (state) {
                          'accepted' =>
                            "Confirmed. You're on at ${widget.hospital} tonight.",
                          'declined' => 'You declined this request.',
                          'expired' =>
                            widget.outcome == 'expired'
                                ? 'Your response arrived after the request expired.'
                                : 'This request expired at ${widget.expiresAtEt} without a response.',
                          'filled' =>
                            'Already filled, thank you. Nothing changed on your schedule.',
                          'closed' => 'This shift no longer needs coverage.',
                          'released' =>
                            "You let your clinical lead know you can't make it.",
                          _ => '',
                        }, style: Theme.of(context).textTheme.headlineSmall),
                      ],
                      if (state == 'sent' || state == 'accepted') ...[
                        const SizedBox(height: 24),
                        _Detail(label: 'Hospital', value: widget.hospital),
                        _Detail(label: 'Hours (ET)', value: widget.hoursEt),
                        _Detail(label: 'Sign in by', value: widget.signInByEt),
                      ],
                      if (state == 'sent') ...[
                        const SizedBox(height: 16),
                        Text(
                          'Why you',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                        for (final reason in widget.whyYou)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text('• $reason'),
                          ),
                        const SizedBox(height: 24),
                        const Text(
                          "No patient details are shared until you accept. Declining doesn't change your schedule.",
                        ),
                      ],
                      if (state == 'accepted') ...[
                        const SizedBox(height: 16),
                        Text(
                          "You'll only be routed ${widget.routingHospitals.join(', ')} consults during these hours.",
                        ),
                        if (widget.coverageAfter != null) ...[
                          const SizedBox(height: 16),
                          Notice(widget.coverageAfter!),
                        ],
                        if (widget.nextSteps.isNotEmpty) ...[
                          const SizedBox(height: 24),
                          Text(
                            'What happens next',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          for (final step in widget.nextSteps)
                            Padding(
                              padding: const EdgeInsets.only(top: 8),
                              child: Text(step),
                            ),
                        ],
                      ],
                      if (_error != null) ...[
                        const SizedBox(height: 16),
                        Notice(_error!, isError: true),
                      ],
                      if (_busy) ...[
                        const SizedBox(height: 16),
                        const Center(
                          child: CircularProgressIndicator(
                            semanticsLabel: 'Sending response',
                          ),
                        ),
                      ],
                      for (final action in ['accept', 'decline', 'release'])
                        if (widget.allowedActions.contains(action) &&
                            (action == 'release'
                                ? state == 'accepted'
                                : state == 'sent')) ...[
                          const SizedBox(height: 12),
                          OutlinedButton(
                            style: OutlinedButton.styleFrom(
                              backgroundColor: action == 'accept'
                                  ? OverlapStyle.tealDark
                                  : Colors.white,
                              foregroundColor: action == 'accept'
                                  ? Colors.white
                                  : OverlapStyle.red,
                              disabledForegroundColor: OverlapStyle.muted,
                            ),
                            onPressed: _busy || _confirming || !_canAct(action)
                                ? null
                                : () => _act(action),
                            child: Text(switch (action) {
                              'accept' => "Accept, I'll cover it",
                              'decline' => 'Not tonight',
                              _ => "I can't make it after all",
                            }),
                          ),
                        ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        ),
      );
    },
  );
}

class _Detail extends StatelessWidget {
  const _Detail({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(
            context,
          ).textTheme.labelLarge?.copyWith(color: OverlapStyle.muted),
        ),
        const SizedBox(height: 4),
        Text(value, style: Theme.of(context).textTheme.titleMedium),
      ],
    ),
  );
}
