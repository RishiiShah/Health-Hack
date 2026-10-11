import 'dart:js_interop';

import 'package:web/web.dart' as web;

import 'data/api.dart';

WebAlerts createWebAlerts() => _BrowserAlerts();

class _BrowserAlerts implements WebAlerts {
  _BrowserAlerts() : _baseTitle = web.document.title;

  final String _baseTitle;
  web.HTMLAudioElement? _audio;
  bool _enabled = false;

  // Flutter web serves assets under assets/<path from pubspec>.
  static const _chimeUrl = 'assets/assets/chime.mp3';

  @override
  Future<void> enableSound() async {
    // Must run inside a tap handler: playing (muted) once unlocks audio on iOS
    // Safari and Chrome's autoplay policy for the rest of the session.
    final a = _audio ??= (web.HTMLAudioElement()
      ..src = _chimeUrl
      ..preload = 'auto');
    a.muted = true;
    try {
      await a.play().toDart;
      a.pause();
      a.currentTime = 0;
      _enabled = true;
    } catch (_) {
      _enabled = false;
    } finally {
      a.muted = false;
    }
  }

  @override
  bool get soundEnabled => _enabled;

  @override
  void chime() {
    final a = _audio;
    if (!_enabled || a == null) return;
    a.currentTime = 0;
    a.play().toDart.catchError((Object _) => null);
  }

  @override
  void vibrate() {
    // Android Chrome only; silently does nothing on iPhone.
    try {
      web.window.navigator.vibrate([200, 100, 200].map((n) => n.toJS).toList().toJS);
    } catch (_) {}
  }

  @override
  void setBadge(int count) {
    web.document.title = count > 0 ? '($count) New coverage request' : _baseTitle;
  }
}
