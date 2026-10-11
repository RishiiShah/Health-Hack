import 'dart:async';

import 'package:flutter/foundation.dart';

import 'api.dart';

/// Contract section 8: `offset = server_now − device time at receipt`, updated
/// on every response; `now() = device time + offset`.
///
/// Also used by the fakes: [set] pins the clock to a time (the demo starts at
/// 18:25 on 17 March) and it keeps ticking from there. Pass `ticking: false` in
/// widget tests so no periodic timer is left pending; then [set]/[advance] drive it.
class OffsetServerClock implements ServerClock {
  OffsetServerClock({DateTime Function()? deviceNow, bool ticking = true})
    : _deviceNow = deviceNow ?? DateTime.now {
    _ticks = ValueNotifier(now());
    if (ticking) {
      _timer = Timer.periodic(
        const Duration(seconds: 1),
        (_) => _ticks.value = now(),
      );
    }
  }

  final DateTime Function() _deviceNow;
  Duration _offset = Duration.zero;
  DateTime? _fixed;
  late final ValueNotifier<DateTime> _ticks;
  Timer? _timer;

  Duration get offset => _offset;

  /// Call with every response's `server_now`.
  void observe(DateTime serverNow, {bool? fixed}) {
    _fixed = (fixed ?? (_fixed != null)) ? serverNow.toUtc() : null;
    _offset = serverNow.toUtc().difference(_deviceNow().toUtc());
    _ticks.value = now();
  }

  /// Fakes and tests: make `now()` equal [t] from this instant.
  void set(DateTime t) => observe(t);

  /// Fakes and tests: move the clock forward.
  void advance(Duration d) {
    if (_fixed != null) _fixed = _fixed!.add(d);
    _offset += d;
    _ticks.value = now();
  }

  @override
  DateTime now() => _fixed ?? _deviceNow().toUtc().add(_offset);

  @override
  Duration remaining(DateTime until) {
    final d = until.toUtc().difference(now());
    return d.isNegative ? Duration.zero : d;
  }

  @override
  ValueListenable<DateTime> get ticks => _ticks;

  void dispose() {
    _timer?.cancel();
    _ticks.dispose();
  }
}
