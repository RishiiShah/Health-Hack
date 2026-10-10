// The few browser APIs the data layer needs, behind an interface so the data
// layer and its tests run on the Dart VM too. The web implementation is picked
// by a conditional import; tests use MemoryBrowser.
import 'dart:async';

import 'browser_stub.dart' if (dart.library.js_interop) 'browser_web.dart' as impl;

Browser? _shared;

/// One Browser per app (the web one adds a document listener).
Browser get sharedBrowser => _shared ??= Browser();

abstract class Browser {
  /// The real browser on web, an in-memory stand-in elsewhere.
  factory Browser() => impl.createBrowser();

  /// The address the app was opened with (for `?token=` and `?offer=`).
  Uri get initialUri;

  /// Replace the address bar without reloading (history.replaceState).
  void replaceUrl(Uri uri);

  String? readSession(String key);
  void writeSession(String key, String value);
  void removeSession(String key);

  /// document.hidden
  bool get hidden;

  /// Emits `hidden` on every visibilitychange.
  Stream<bool> get visibilityChanges;
}

/// For tests and non-web runs.
class MemoryBrowser implements Browser {
  MemoryBrowser({Uri? initialUri}) : _uri = initialUri ?? Uri.parse('http://localhost/');

  Uri _uri;
  final Map<String, String> session = {};
  final _vis = StreamController<bool>.broadcast();
  bool _hidden = false;

  Uri get currentUri => _uri;

  @override
  Uri get initialUri => _uri;

  @override
  void replaceUrl(Uri uri) => _uri = uri;

  @override
  String? readSession(String key) => session[key];

  @override
  void writeSession(String key, String value) => session[key] = value;

  @override
  void removeSession(String key) => session.remove(key);

  @override
  bool get hidden => _hidden;

  /// Tests: simulate the tab being hidden or shown.
  set hidden(bool v) {
    if (v == _hidden) return;
    _hidden = v;
    _vis.add(v);
  }

  @override
  Stream<bool> get visibilityChanges => _vis.stream;
}
