import 'dart:async';

import 'platform/browser.dart';

/// For screens that poll on their own (My shift every 30 s, Coverage every 15 s).
///
/// ```dart
/// late final _poller = Poller(const Duration(seconds: 30), _load);
/// @override void initState() { super.initState(); _poller.start(); }
/// @override void dispose() { _poller.stop(); super.dispose(); }
/// ```
///
/// Runs [callback] immediately on start, then every [interval]. Skips ticks
/// while the tab is hidden and runs immediately when it becomes visible again.
/// Never runs two callbacks at once.
class Poller {
  Poller(this.interval, this.callback, {Browser? browser}) : _browser = browser ?? sharedBrowser;

  final Duration interval;
  final Future<void> Function() callback;
  final Browser _browser;

  Timer? _timer;
  StreamSubscription<bool>? _vis;
  bool _busy = false;

  bool get running => _timer != null;

  void start() {
    if (running) return;
    _timer = Timer.periodic(interval, (_) => _run());
    _vis = _browser.visibilityChanges.listen((hidden) {
      if (!hidden) _run();
    });
    _run();
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
    _vis?.cancel();
    _vis = null;
  }

  Future<void> _run() async {
    if (_busy || _browser.hidden || !running) return;
    _busy = true;
    try {
      await callback();
    } catch (_) {
      // The screen's callback handles its own errors; a failed tick must not
      // stop the poller.
    } finally {
      _busy = false;
    }
  }
}
