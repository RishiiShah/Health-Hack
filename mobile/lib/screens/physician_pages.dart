import 'dart:async';
import 'package:flutter/material.dart';

import '../data/api.dart';
import 'data_widgets.dart';
import 'offer_detail_screen.dart';
import 'shared.dart';

class OffersPage extends StatelessWidget {
  const OffersPage({
    super.key,
    required this.services,
    required this.me,
    required this.openOffer,
  });
  final AppServices services;
  final Me me;
  final ValueChanged<String> openOffer;
  @override
  Widget build(BuildContext context) => FeedView<OfferList>(
    feed: services.physicianFeed.offers,
    refresh: services.physicianFeed.refreshNow,
    builder: (context, list) {
      final sent =
          list.offers.where((o) => o.status == OfferStatus.sent).toList()
            ..sort((a, b) {
              final c = b.sentAt.compareTo(a.sentAt);
              return c != 0 ? c : a.offerId.compareTo(b.offerId);
            });
      final accepted =
          list.offers.where((o) => o.status == OfferStatus.accepted).toList()
            ..sort((a, b) {
              final c = a.start.compareTo(b.start);
              return c != 0 ? c : a.offerId.compareTo(b.offerId);
            });
      final recent =
          list.offers
              .where(
                (o) =>
                    o.status != OfferStatus.sent &&
                    o.status != OfferStatus.accepted,
              )
              .toList()
            ..sort((a, b) {
              final c = b.sentAt.compareTo(a.sentAt);
              return c != 0 ? c : a.offerId.compareTo(b.offerId);
            });
      return ScreenBody(
        children: [
          Text(
            me.onShift == null
                ? me.displayName
                : '${me.displayName} · ${me.onShift == true ? 'on shift' : 'off shift'}',
          ),
          if (me.offersReceived7d != null && me.weeklyOfferLimit != null)
            SectionTitle(
              '${me.offersReceived7d} of ${me.weeklyOfferLimit} requests this week',
            ),
          if (me.splitShiftOptIn == false)
            const Notice("You won't receive coverage requests."),
          if (list.offers.isEmpty) const SectionTitle('No coverage requests'),
          for (final group in [
            ('New requests', sent),
            ('Accepted shifts', accepted),
            ('Recent', recent),
          ])
            if (group.$2.isNotEmpty) ...[
              SectionTitle(group.$1),
              for (final offer in group.$2)
                DataCard(
                  children: [
                    Text(
                      offerLabel(offer.status, offer.statusReason),
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    SectionTitle(hospitalsLabel(offer.hospitals)),
                    Text(
                      '${formatEtDay(offer.start)} · ${formatEtRange(offer.start, offer.end)}',
                    ),
                    if (offer.status == OfferStatus.sent)
                      ClockBuilder(
                        clock: services.clock,
                        builder: (_) => Text(
                          '${formatCountdown(services.clock.remaining(offer.expiresAt))} left',
                        ),
                      ),
                    const SizedBox(height: 12),
                    OutlinedButton(
                      onPressed: () => openOffer(offer.offerId),
                      child: const Text('View request'),
                    ),
                  ],
                ),
            ],
        ],
      );
    },
  );
}

class ConnectedOffer extends StatefulWidget {
  const ConnectedOffer({
    super.key,
    required this.services,
    required this.offerId,
  });
  final AppServices services;
  final String offerId;
  @override
  State<ConnectedOffer> createState() => _ConnectedOfferState();
}

class _ConnectedOfferState extends State<ConnectedOffer> {
  Offer? _offer;
  OfferOutcome? _outcome;
  Object? _error;
  bool _actionBusy = false;
  int _version = 0;
  final _remaining = ValueNotifier(Duration.zero);
  AppServices get s => widget.services;
  @override
  void initState() {
    super.initState();
    s.clock.ticks.addListener(_tick);
    s.physicianFeed.offers.addListener(_feedChanged);
    s.alerts.setBadge(0);
    _load();
  }

  void _tick() {
    if (_offer != null) _remaining.value = s.clock.remaining(_offer!.expiresAt);
  }

  void _feedChanged() {
    if (_actionBusy) return;
    final offer = s.physicianFeed.offers.value.data?.offers
        .where((o) => o.offerId == widget.offerId)
        .firstOrNull;
    if (offer == null || !mounted) return;
    _version++;
    setState(() {
      if (_offer?.status != offer.status ||
          _offer?.statusReason != offer.statusReason) {
        _outcome = null;
      }
      _offer = offer;
    });
    _tick();
  }

  Future<void> _load() async {
    final version = ++_version;
    try {
      final offer = await s.offers.getOffer(widget.offerId);
      if (!mounted || version != _version) return;
      setState(() {
        _offer = offer;
        _error = null;
      });
      _tick();
    } catch (error) {
      if (mounted && version == _version) setState(() => _error = error);
    }
  }

  Future<String?> _action(String action) async {
    _actionBusy = true;
    _version++;
    try {
      final result = await switch (action) {
        'accept' => s.offers.accept(widget.offerId),
        'decline' => s.offers.decline(widget.offerId),
        'release' => s.offers.release(widget.offerId),
        _ => throw const InvalidRequest('Unknown offer action'),
      };
      if (!mounted) return null;
      setState(() {
        _offer = result.offer;
        _outcome = result.outcome;
        _error = null;
      });
      _tick();
      unawaited(s.physicianFeed.refreshNow());
      return null;
    } catch (error) {
      return errorText(error);
    } finally {
      _actionBusy = false;
    }
  }

  @override
  void dispose() {
    s.clock.ticks.removeListener(_tick);
    s.physicianFeed.offers.removeListener(_feedChanged);
    _remaining.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final offer = _offer;
    if (offer == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Coverage request')),
        body: _error == null
            ? const Center(child: CircularProgressIndicator())
            : DataFailure(error: _error!, retry: _load),
      );
    }
    final coverage = offer.coverageAfter;
    return OfferDetailScreen(
      offerId: offer.offerId,
      hospital: hospitalsLabel(offer.hospitals),
      hoursEt: formatEtRange(offer.start, offer.end),
      signInByEt: formatEtLabel(offer.signInBy),
      expiresAtEt: formatEtLabel(offer.expiresAt),
      gapSummary: offer.gapSummary,
      whyYou: offer.whyYou.isEmpty ? [offer.reason] : offer.whyYou,
      status: offer.status.wire,
      statusReason: offer.statusReason?.wire,
      outcome: _outcome?.wire,
      allowedActions: offer.allowedActions.map((a) => a.wire).toSet(),
      remaining: _remaining,
      onAction: _action,
      routingHospitals: offer.routingHospitals.map((h) => h.name).toList(),
      nextSteps: offer.nextSteps
          .map((step) => '${formatEtLabel(step.at)} · ${step.label}')
          .toList(),
      coverageAfter: coverage == null
          ? null
          : '${hospitalsLabel(offer.hospitals)} now shows ${coverage.staffed} of ${coverage.required} from ${formatEtLabel(coverage.from)}.',
      reconnecting: s.physicianFeed.offers.value.stale,
    );
  }
}

class ShiftPage extends StatelessWidget {
  const ShiftPage({
    super.key,
    required this.services,
    required this.me,
    required this.onOffers,
  });
  final AppServices services;
  final Me me;
  final VoidCallback onOffers;
  @override
  Widget build(BuildContext context) => RepositoryView<MyShift>(
    load: services.shifts.myShift,
    interval: const Duration(seconds: 30),
    builder: (context, shift) => ScreenBody(
      children: [
        SectionTitle(me.displayName),
        if (!shift.onShift) ...[
          const SectionTitle("You're off shift"),
          if (shift.nextShift != null)
            Text(
              'Next shift: ${formatEtDay(shift.nextShift!.start)} · ${formatEtRange(shift.nextShift!.start, shift.nextShift!.end)}',
            ),
          FilledButton(onPressed: onOffers, child: const Text('View offers')),
        ] else ...[
          if (shift.shiftEnd != null)
            Text('Until ${formatEtLabel(shift.shiftEnd!)}'),
          if (shift.update != null)
            DataCard(
              children: [
                Text('${formatEtLabel(shift.update!.at)} · Schedule updated'),
                const SizedBox(height: 8),
                Text(shift.update!.text),
              ],
            ),
          if (shift.consults.isEmpty)
            const SectionTitle('No consults right now'),
          for (final consult in shift.consults)
            DataCard(
              children: [
                SectionTitle(consult.consultId),
                Text(
                  [
                    if (consult.badge != null) consult.badge!,
                    consult.consultType,
                  ].join(' · '),
                ),
                Text(consult.hospitalName),
                const SizedBox(height: 12),
                Text(
                  consult.statusText,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: switch (consult.level) {
                      ConsultLevel.critical => const Color(0xFFB42318),
                      ConsultLevel.warning => const Color(0xFF8A5A00),
                      ConsultLevel.ok => const Color(0xFF0D9488),
                    },
                  ),
                ),
              ],
            ),
          ClockBuilder(
            clock: services.clock,
            builder: (_) => Text(
              '${shift.shiftEnd == null ? '' : '${formatHoursMinutes(services.clock.remaining(shift.shiftEnd!))} left · '}${shift.consultsToday} consults this shift',
            ),
          ),
        ],
      ],
    ),
  );
}
