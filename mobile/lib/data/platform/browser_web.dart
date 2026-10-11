import 'dart:async';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

import 'browser.dart';

Browser createBrowser() => _WebBrowser();

class _WebBrowser implements Browser {
  _WebBrowser() : initialUri = Uri.base {
    web.document.addEventListener(
      'visibilitychange',
      ((web.Event _) => _vis.add(web.document.hidden)).toJS,
    );
  }

  @override
  final Uri initialUri;

  final _vis = StreamController<bool>.broadcast();

  @override
  void replaceUrl(Uri uri) => web.window.history.replaceState(null, '', uri.toString());

  @override
  String? readSession(String key) => web.window.sessionStorage.getItem(key);

  @override
  void writeSession(String key, String value) => web.window.sessionStorage.setItem(key, value);

  @override
  void removeSession(String key) => web.window.sessionStorage.removeItem(key);

  @override
  bool get hidden => web.document.hidden;

  @override
  Stream<bool> get visibilityChanges => _vis.stream;
}
