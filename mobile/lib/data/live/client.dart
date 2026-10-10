import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../clock.dart';
import '../exceptions.dart';
import '../json.dart';
import '../models.dart';

/// Where the session token lives. The token is the only thing the app stores.
abstract class TokenStore {
  String? read();
  void write(String token);
  void clear();
}

/// HTTP for the contract (sections 2, 6, 8).
///
/// * Sends `Authorization: Bearer <token>` on every request.
/// * Maps status codes to [ApiException]s; 401 also calls [onUnauthorized].
/// * No response or a [timeout] (10 s) → [NetworkError]; bad JSON → [ParseError].
/// * Feeds every top-level `server_now` to the [clock].
class ApiClient {
  ApiClient({
    required this.baseUrl,
    required this.tokens,
    required this.clock,
    required this.onUnauthorized,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 10),
  }) : _http = httpClient ?? http.Client();

  final Uri baseUrl;
  final TokenStore tokens;
  final OffsetServerClock clock;
  final void Function() onUnauthorized;
  final Duration timeout;
  final http.Client _http;

  Future<T> get<T>(String path, T Function(Object?) parse, {Map<String, String>? query}) =>
      _send('GET', path, parse, query: query);

  Future<T> post<T>(String path, T Function(Object?) parse,
          {Object? body, bool signOutOn401 = true}) =>
      _send('POST', path, parse, body: body, signOutOn401: signOutOn401);

  Future<T> put<T>(String path, T Function(Object?) parse, {Object? body}) =>
      _send('PUT', path, parse, body: body);

  Uri _uri(String path, Map<String, String>? query) {
    final basePath = baseUrl.path.endsWith('/')
        ? baseUrl.path.substring(0, baseUrl.path.length - 1)
        : baseUrl.path;
    return baseUrl.replace(path: '$basePath$path', queryParameters: query);
  }

  Future<T> _send<T>(
    String method,
    String path,
    T Function(Object?) parse, {
    Map<String, String>? query,
    Object? body,
    bool signOutOn401 = true,
  }) async {
    final request = http.Request(method, _uri(path, query));
    request.headers['Accept'] = 'application/json';
    final token = tokens.read();
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }

    final http.Response res;
    try {
      res = await (() async => http.Response.fromStream(await _http.send(request)))()
          .timeout(timeout);
    } on TimeoutException {
      throw const NetworkError();
    } on http.ClientException {
      throw const NetworkError();
    } catch (_) {
      // Browser fetch failures (CORS, offline) surface as various types.
      throw const NetworkError();
    }

    Object? decoded;
    final text = utf8.decode(res.bodyBytes, allowMalformed: true);
    if (text.isNotEmpty) {
      try {
        decoded = jsonDecode(text);
      } on FormatException {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          throw ParseError('$method $path: response is not JSON');
        }
      }
    }
    _observeServerNow(decoded);

    final code = res.statusCode;
    if (code >= 200 && code < 300) return parse(decoded);

    final message = _errorMessage(decoded);
    switch (code) {
      case 401:
        if (signOutOn401) {
          tokens.clear();
          onUnauthorized();
        }
        throw Unauthorized(message ?? 'Please sign in again.');
      case 403:
        throw Forbidden(message ?? "You don't have permission for this.");
      case 404:
        throw const NotFound();
      case 422:
        throw InvalidRequest(message ?? 'The request was not valid.');
      default:
        throw Unavailable(code == 503 ? (message ?? "Can't reach Sevaro.") : "Can't reach Sevaro.");
    }
  }

  void _observeServerNow(Object? decoded) {
    if (decoded is Map<String, dynamic> && decoded['server_now'] is String) {
      try {
        clock.observe(parseTimestamp(decoded['server_now'] as String, 'server_now'));
      } on ParseError {
        // The body's own parser reports this.
      }
    }
  }

  String? _errorMessage(Object? decoded) {
    try {
      return ApiErrorBody.parse(decoded).message;
    } on ParseError {
      return null;
    }
  }

  void close() => _http.close();
}

/// Accept, decline, release, approve, reject, authorize and opt-in: on
/// [NetworkError], retry once automatically; the server returns the same
/// result for a repeat (contract section 3), so this is safe.
Future<T> retryOnceOnNetwork<T>(Future<T> Function() call) async {
  try {
    return await call();
  } on NetworkError {
    return call();
  }
}
