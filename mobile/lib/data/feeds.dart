import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';
import 'platform/browser.dart';

/// Contract section 7. Works against any OfferRepository (live or fake).
///
/// * `/offers` + `/notifications` every 3 s, so a newly sent offer rings promptly.
/// * Stops while the tab is hidden; refreshes immediately when visible.
/// * A failed poll keeps the last good data and sets `error`; the next success clears it.
class PollingPhysicianFeed implements PhysicianFeed {
  PollingPhysicianFeed(
    this._repo, {
    Browser? browser,
    this.interval = const Duration(seconds: 3),
  }) : _browser = browser ?? sharedBrowser;

  final OfferRepository _repo;
  final Browser _browser;
  final Duration interval;

  final _offers = ValueNotifier<FeedState<OfferList>>(const FeedState.loading());
  final _notifications = ValueNotifier<FeedState<NotificationList>>(const FeedState.loading());
  final _newOffer = StreamController<Offer>.broadcast();
  final _changed = StreamController<Offer>.broadcast();

  final Set<String> _seenSent = {};
  Map<String, OfferStatus>? _lastStatus;
  Timer? _timer;
  StreamSubscription<bool>? _vis;
  bool _running = false;
  int _generation = 0;
  Future<void>? _inFlight;

  @override
  ValueListenable<FeedState<OfferList>> get offers => _offers;
  @override
  ValueListenable<FeedState<NotificationList>> get notifications => _notifications;
  @override
  Stream<Offer> get newOffer => _newOffer.stream;
  @override
  Stream<Offer> get offerChanged => _changed.stream;

  @override
  void start() {
    if (_running) return;
    _running = true;
    _vis = _browser.visibilityChanges.listen((hidden) {
      if (hidden) {
        _timer?.cancel();
      } else {
        _poll();
      }
    });
    _poll();
  }

  @override
  void stop() {
    _running = false;
    _generation++;
    _inFlight = null;
    _timer?.cancel();
    _vis?.cancel();
    _vis = null;
    // Next start() is a fresh session (e.g. another user signs in).
    _seenSent.clear();
    _lastStatus = null;
    _offers.value = const FeedState.loading();
    _notifications.value = const FeedState.loading();
  }

  @override
  Future<void> refreshNow() => _poll();

  Future<void> _poll() {
    if (!_running || _browser.hidden) return Future.value();
    final generation = _generation;
    return _inFlight ??= _doPoll(generation).whenComplete(() {
      if (generation == _generation) _inFlight = null;
    });
  }

  Future<void> _doPoll(int generation) async {
    _timer?.cancel();
    await Future.wait([_loadOffers(generation), _loadNotifications(generation)]);
    if (_running && generation == _generation && !_browser.hidden) _timer = Timer(interval, _poll);
  }

  Future<void> _loadOffers(int generation) async {
    try {
      final list = await _repo.listOffers();
      if (!_running || generation != _generation) return;
      _offers.value = FeedState(data: list);
      _detect(list);
    } catch (e) {
      if (!_running || generation != _generation) return;
      _offers.value = FeedState(data: _offers.value.data, error: e);
    }
  }

  Future<void> _loadNotifications(int generation) async {
    try {
      final list = await _repo.notifications();
      if (!_running || generation != _generation) return;
      _notifications.value = FeedState(data: list);
    } catch (e) {
      if (!_running || generation != _generation) return;
      _notifications.value = FeedState(data: _notifications.value.data, error: e);
    }
  }

  void _detect(OfferList list) {
    final previous = _lastStatus;
    for (final o in list.offers) {
      if (o.status == OfferStatus.sent && _seenSent.add(o.offerId)) {
        _newOffer.add(o);
      }
      final before = previous?[o.offerId];
      if (before != null && before != o.status) _changed.add(o);
    }
    _lastStatus = {for (final o in list.offers) o.offerId: o.status};
  }
}

/// `/lead/queue` + `/lead/offers?active=true` every 5 s. Emits an [AnswerEvent]
/// whenever a recipient's offer status differs from the previous poll.
class PollingLeadFeed implements LeadFeed {
  PollingLeadFeed(
    this._repo, {
    Browser? browser,
    this.interval = const Duration(seconds: 5),
  }) : _browser = browser ?? sharedBrowser;

  final LeadRepository _repo;
  final Browser _browser;
  final Duration interval;

  final _queue = ValueNotifier<FeedState<LeadQueue>>(const FeedState.loading());
  final _active = ValueNotifier<FeedState<BroadcastList>>(const FeedState.loading());
  final _answers = StreamController<AnswerEvent>.broadcast();

  Map<String, OfferStatus>? _lastStatus;
  Timer? _timer;
  StreamSubscription<bool>? _vis;
  bool _running = false;
  int _generation = 0;
  Future<void>? _inFlight;

  @override
  ValueListenable<FeedState<LeadQueue>> get queue => _queue;
  @override
  ValueListenable<FeedState<BroadcastList>> get activeOffers => _active;
  @override
  Stream<AnswerEvent> get answers => _answers.stream;

  @override
  void start() {
    if (_running) return;
    _running = true;
    _vis = _browser.visibilityChanges.listen((hidden) {
      if (hidden) {
        _timer?.cancel();
      } else {
        _poll();
      }
    });
    _poll();
  }

  @override
  void stop() {
    _running = false;
    _generation++;
    _inFlight = null;
    _timer?.cancel();
    _vis?.cancel();
    _vis = null;
    _lastStatus = null;
    _queue.value = const FeedState.loading();
    _active.value = const FeedState.loading();
  }

  @override
  Future<void> refreshNow() => _poll();

  Future<void> _poll() {
    if (!_running || _browser.hidden) return Future.value();
    final generation = _generation;
    return _inFlight ??= _doPoll(generation).whenComplete(() {
      if (generation == _generation) _inFlight = null;
    });
  }

  Future<void> _doPoll(int generation) async {
    _timer?.cancel();
    await Future.wait([_loadQueue(generation), _loadActive(generation)]);
    if (_running && generation == _generation && !_browser.hidden) _timer = Timer(interval, _poll);
  }

  Future<void> _loadQueue(int generation) async {
    try {
      final q = await _repo.queue();
      if (!_running || generation != _generation) return;
      _queue.value = FeedState(data: q);
    } catch (e) {
      if (!_running || generation != _generation) return;
      _queue.value = FeedState(data: _queue.value.data, error: e);
    }
  }

  Future<void> _loadActive(int generation) async {
    try {
      final list = await _repo.activeOffers();
      if (!_running || generation != _generation) return;
      _active.value = FeedState(data: list);
      final previous = _lastStatus;
      for (final b in list.broadcasts) {
        for (final o in b.offers) {
          final before = previous?[o.offerId];
          if (before != null && before != o.status) {
            _answers.add(AnswerEvent(broadcast: b, offer: o, previousStatus: before));
          }
        }
      }
      // Keep statuses of offers that dropped off the active list, so one that
      // comes back isn't reported twice.
      _lastStatus = {
        ...?previous,
        for (final b in list.broadcasts)
          for (final o in b.offers) o.offerId: o.status,
      };
    } catch (e) {
      if (!_running || generation != _generation) return;
      _active.value = FeedState(data: _active.value.data, error: e);
    }
  }
}
