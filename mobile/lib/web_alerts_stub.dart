import 'dart:io';

import 'package:flutter/services.dart';

import 'data/api.dart';
import 'web_alerts.dart';

// The installed Android app plays sound through MainActivity.kt (Android's own
// MediaPlayer and ringtone, no plugin); tests and other platforms record calls.
WebAlerts createWebAlerts() =>
    Platform.isAndroid ? _AndroidAlerts() : RecordingWebAlerts();

class _AndroidAlerts implements WebAlerts {
  static const _sound = MethodChannel('sevaro/sound');

  @override
  Future<void> enableSound() async {}
  @override
  bool get soundEnabled => true;
  @override
  void chime() => _sound.invokeMethod<void>('chime');
  @override
  void vibrate() => HapticFeedback.heavyImpact();
  @override
  void startRing() => _sound.invokeMethod<void>('ring');
  @override
  Future<void> play(Uint8List mp3) => _sound.invokeMethod<void>('play', mp3);
  @override
  void stopSound() => _sound.invokeMethod<void>('stop');
  @override
  void setBadge(int count) {}
}
