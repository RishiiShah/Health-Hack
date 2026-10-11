import 'dart:async';
import 'package:flutter/material.dart';
import '../data/api.dart';
import 'account_page.dart';
import 'data_widgets.dart';
import 'incoming_call_screen.dart';
import 'lead_pages.dart';
import 'physician_pages.dart';
import 'role_home.dart';
import 'schedule_pages.dart';
import 'shared.dart';

/// Auth-independent application shell. A future auth entry supplies Me/services.
/// All routes share this session and disappear together on sign-out or a 401.
class ServiceSession extends StatefulWidget {
  const ServiceSession({
    super.key,
    required this.services,
    required this.me,
    this.onEnded,
    this.onOpenWebDashboard,
    this.actions = const [],
    this.accountBuilder,
  });
  final AppServices services;
  final Me me;
  final VoidCallback? onEnded;
  final VoidCallback? onOpenWebDashboard;
  final List<Widget> actions;
  final WidgetBuilder? accountBuilder;
  @override
  State<ServiceSession> createState() => _ServiceSessionState();
}

class _ServiceSessionState extends State<ServiceSession> {
  final _navigator = GlobalKey<NavigatorState>();
  final _tab = ValueNotifier(0);
  final _opened = <String>{};
  final _pending = <String, Offer>{};
  final _subscriptions = <StreamSubscription<dynamic>>[];
  Poller? _mePoller;
  bool _ended = false;
  bool _lockOpen = false;
  String? _initialOffer;
  AppServices get s => widget.services;
  @override
  void initState() {
    super.initState();
    _subscriptions.add(s.auth.signedOut.listen((_) => _end()));
    if (widget.me.role == Role.physician) {
      _initialOffer = s.auth.takeInitialOfferId();
      _subscriptions.add(s.physicianFeed.newOffer.listen(_newOffer));
      _mePoller = Poller(const Duration(seconds: 60), () async {
        await s.auth.refreshMe();
      });
      s.physicianFeed.start();
      _mePoller!.start();
    } else if (widget.me.role == Role.clinicalLead) {
      _mePoller = Poller(const Duration(seconds: 60), () async {
        await s.auth.refreshMe();
      });
      _mePoller!.start();
      _subscriptions.add(s.leadFeed.answers.listen(_answer));
      s.leadFeed.start();
    }
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || _ended) return;
      if (_initialOffer != null) {
        _openOffer(_initialOffer!);
      } else {
        _showPending();
      }
    });
  }

  void _end() {
    if (!mounted || _ended) return;
    s.physicianFeed.stop();
    s.leadFeed.stop();
    _mePoller?.stop();
    s.alerts.setBadge(0);
    setState(() => _ended = true);
    // Dispose the nested navigator (including dialogs) before ending the parent.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.onEnded?.call();
    });
  }

  void _newOffer(Offer offer) {
    if (_ended ||
        _opened.contains(offer.offerId) ||
        offer.offerId == _initialOffer) {
      return;
    }
    _pending[offer.offerId] = offer;
    _showPending();
  }

  void _showPending() {
    if (!mounted ||
        _ended ||
        _lockOpen ||
        _pending.isEmpty ||
        _navigator.currentState == null) {
      return;
    }
    _lockOpen = true;
    final offer = _pending.values.last;
    s.alerts.setBadge(
      s.physicianFeed.notifications.value.data?.unreadOffers ?? _pending.length,
    );
    _navigator.currentState!
        .push(
          MaterialPageRoute<void>(
            builder: (_) => IncomingCallScreen(services: s, offer: offer),
          ),
        )
        .whenComplete(() {
          _lockOpen = false;
          _pending.clear();
          s.alerts.setBadge(0);
        });
  }

  void _openOffer(String id) {
    if (!mounted || _ended) return;
    _opened.add(id);
    _pending.remove(id);
    s.alerts.setBadge(0);
    final route = MaterialPageRoute<void>(
      builder: (_) => ConnectedOffer(services: s, offerId: id),
    );
    _navigator.currentState?.push(route);
  }

  void _openProposal(String id) {
    if (!_ended) {
      _navigator.currentState?.push(
        MaterialPageRoute<void>(
          builder: (_) => ProposalScreen(services: s, proposalId: id),
        ),
      );
    }
  }

  void _answer(AnswerEvent event) {
    if (!mounted || _ended) return;
    if (![
      OfferStatus.accepted,
      OfferStatus.declined,
      OfferStatus.expired,
      OfferStatus.released,
    ].contains(event.offer.status)) {
      return;
    }
    final text =
        '${event.offer.displayName} ${event.offer.status.wire} · ${hospitalsLabel(event.broadcast.hospitals)} ${formatEtRange(event.broadcast.start, event.broadcast.end)}';
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    if (s.alerts.soundEnabled) s.alerts.chime();
  }

  @override
  void dispose() {
    for (final subscription in _subscriptions) {
      subscription.cancel();
    }
    _mePoller?.stop();
    s.physicianFeed.stop();
    s.leadFeed.stop();
    s.alerts.setBadge(0);
    _tab.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_ended) return const ErrorScreen(message: 'Please sign in again.');
    return NavigatorPopHandler(
      onPopWithResult: (result) => _navigator.currentState?.pop(result),
      child: Navigator(
        key: _navigator,
        onGenerateRoute: (_) => MaterialPageRoute<void>(
          builder: (context) => ValueListenableBuilder<Me?>(
            valueListenable: s.auth.me,
            builder: (context, current, _) {
              final me = current ?? widget.me;
              return RoleHome(
                role: me.role.wire,
                tabIndex: _tab,
                actions: widget.actions,
                onOpenWebDashboard: widget.onOpenWebDashboard,
                physicianPages: [
                  (_) => ShiftPage(
                    services: s,
                    me: me,
                    onOffers: () => _tab.value = 2,
                  ),
                  (_) => PhysicianSchedulePage(services: s),
                  (_) => OffersPage(services: s, me: me, openOffer: _openOffer),
                  widget.accountBuilder ??
                      (_) => AccountPage(services: s, me: me),
                ],
                leadPages: [
                  (_) => ApprovalsPage(
                    services: s,
                    me: me,
                    openProposal: _openProposal,
                  ),
                  (_) => LeadSchedulePage(
                    services: s,
                    openProposal: _openProposal,
                  ),
                  (_) => CoveragePage(services: s),
                  widget.accountBuilder ??
                      (_) => AccountPage(services: s, me: me),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}
