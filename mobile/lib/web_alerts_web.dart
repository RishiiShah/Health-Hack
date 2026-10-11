import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

import 'data/api.dart';

WebAlerts createWebAlerts() => _BrowserAlerts();

class _BrowserAlerts implements WebAlerts {
  _BrowserAlerts() : _baseTitle = web.document.title;

  final String _baseTitle;
  web.HTMLAudioElement? _audio;
  bool _enabled = false;
  String? _voiceUrl;

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
  void chime() => _playChime(loop: false);

  @override
  void startRing() => _playChime(loop: true);

  void _playChime({required bool loop}) {
    final a = _audio;
    if (!_enabled || a == null) return;
    _useChime(a);
    a.loop = loop;
    a.currentTime = 0;
    a.play().toDart.catchError((Object _) => null);
  }

  @override
  Future<void> play(Uint8List mp3) async {
    // Reuse the element enableSound() unlocked: iOS Safari unlocks per element.
    final a = _audio ??= web.HTMLAudioElement();
    a.pause();
    _useChime(a);
    final url = web.URL.createObjectURL(
      web.Blob(<web.BlobPart>[mp3.toJS].toJS, web.BlobPropertyBag(type: 'audio/mpeg')),
    );
    _voiceUrl = url;
    a.src = url;
    a.loop = false;
    await a.play().toDart;
  }

  @override
  void stopSound() {
    final a = _audio;
    if (a == null) return;
    a.pause();
    a.loop = false;
    _useChime(a);
  }

  /// Points the element back at the chime after a spoken offer.
  void _useChime(web.HTMLAudioElement a) {
    final voice = _voiceUrl;
    if (voice == null) return;
    a.src = _chimeUrl;
    web.URL.revokeObjectURL(voice);
    _voiceUrl = null;
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
