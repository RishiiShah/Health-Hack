// Chime, call ring, spoken-offer playback, vibration and tab-title badge. The browser implementation is picked by a conditional
// import; tests and the VM get RecordingWebAlerts.
import 'dart:typed_data';

import 'data/api.dart';
import 'web_alerts_stub.dart' if (dart.library.js_interop) 'web_alerts_web.dart' as impl;

WebAlerts createWebAlerts() => impl.createWebAlerts();

/// Does nothing but count calls. Use it in widget tests to check that a new
/// offer chimes, vibrates and sets the badge.
class RecordingWebAlerts implements WebAlerts {
  bool _sound = false;
  int chimes = 0;
  int vibrations = 0;
  int badge = 0;
  bool ringing = false;
  int rings = 0;
  int plays = 0;

  @override
  Future<void> enableSound() async => _sound = true;
  @override
  bool get soundEnabled => _sound;
  @override
  void chime() {
    if (_sound) chimes++;
  }

  @override
  void vibrate() => vibrations++;
  @override
  void startRing() {
    ringing = true;
    rings++;
  }

  @override
  Future<void> play(Uint8List mp3) async {
    ringing = false;
    plays++;
  }

  @override
  void stopSound() => ringing = false;
  @override
  void setBadge(int count) => badge = count;
}
