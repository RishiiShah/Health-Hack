import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

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

  Future<T> get<T>(
    String path,
    T Function(Object?) parse, {
    Map<String, String>? query,
  }) => _send('GET', path, parse, query: query);

  Future<T> post<T>(
    String path,
    T Function(Object?) parse, {
    Object? body,
    bool signOutOn401 = true,
    String? idempotencyKey,
  }) => _send(
    'POST',
    path,
    parse,
    body: body,
    signOutOn401: signOutOn401,
    idempotencyKey: idempotencyKey,
  );

  Future<T> put<T>(String path, T Function(Object?) parse, {Object? body}) =>
      _send('PUT', path, parse, body: body);

  /// A binary body (offer audio). Same auth, timeout and error mapping as JSON
  /// calls; any non-2xx other than 401/403/404/422 is [Unavailable], including 409 (offer not sent):
  /// the screen shows the offer text instead.
  Future<Uint8List> getBytes(String path, {String accept = 'audio/mpeg'}) async {
    final (res, token) = await _exchange('GET', path, accept: accept);
    if (res.statusCode >= 200 && res.statusCode < 300) return res.bodyBytes;
    Object? decoded;
    try {
      decoded = jsonDecode(utf8.decode(res.bodyBytes, allowMalformed: true));
    } on FormatException {
      // Error bodies are optional.
    }
    if (res.statusCode == 409) throw Unavailable(_errorMessage(decoded) ?? 'Offer audio is unavailable.');
    throw _failure(res.statusCode, decoded, token, signOutOn401: true);
  }

  Uri _uri(String path, Map<String, String>? query) {
    final basePath = baseUrl.path.endsWith('/')
        ? baseUrl.path.substring(0, baseUrl.path.length - 1)
        : baseUrl.path;
    return baseUrl.replace(path: '$basePath$path', queryParameters: query);
  }

  /// Sends one request and returns the response with the token it was sent with.
  Future<(http.Response, String?)> _exchange(
    String method,
    String path, {
    Map<String, String>? query,
    Object? body,
    String accept = 'application/json',
    String? idempotencyKey,
  }) async {
    final request = http.Request(method, _uri(path, query));
    request.headers['Accept'] = accept;
    if (idempotencyKey != null) {
      request.headers['Idempotency-Key'] = idempotencyKey;
    }
    final token = tokens.read();
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json';
      request.body = jsonEncode(body);
    }
    try {
      final res = await (() async => http.Response.fromStream(await _http.send(request)))()
          .timeout(timeout);
      return (res, token);
    } on TimeoutException {
      throw const NetworkError();
    } on http.ClientException {
      throw const NetworkError();
    } catch (_) {
      // Browser fetch failures (CORS, offline) surface as various types.
      throw const NetworkError();
    }
  }

  Future<T> _send<T>(
    String method,
    String path,
    T Function(Object?) parse, {
    Map<String, String>? query,
    Object? body,
    bool signOutOn401 = true,
    String? idempotencyKey,
  }) async {
    final (res, token) = await _exchange(
      method,
      path,
      query: query,
      body: body,
      idempotencyKey: idempotencyKey,
    );

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
    throw _failure(code, decoded, token, signOutOn401: signOutOn401);
  }

  ApiException _failure(int code, Object? decoded, String? token, {required bool signOutOn401}) {
    final message = _errorMessage(decoded);
    switch (code) {
      case 401:
        if (signOutOn401 && tokens.read() == token) {
          tokens.clear();
          onUnauthorized();
        }
        return Unauthorized(message ?? 'Please sign in again.');
      case 403:
        return Forbidden(message ?? "You don't have permission for this.");
      case 404:
        return const NotFound();
      case 409:
        return Conflict(message ?? 'This item has changed.', decoded);
      case 422:
        return InvalidRequest(message ?? 'The request was not valid.');
      default:
        return Unavailable(
          code == 503
              ? (message ?? "Can't reach Sevaro.")
              : "Can't reach Sevaro.",
        );
    }
  }

  void _observeServerNow(Object? decoded) {
    if (decoded is Map<String, dynamic> && decoded['server_now'] is String) {
      try {
        clock.observe(
          parseTimestamp(decoded['server_now'] as String, 'server_now'),
          fixed: decoded.containsKey('clock_mode')
              ? decoded['clock_mode'] == 'fixed'
              : null,
        );
      } on ParseError {
        // The body's own parser reports this.
      }
    }
  }

  String? _errorMessage(Object? decoded) {
    try {
      return ApiErrorBody.parse(decoded).message;
    } on ParseError {
      // The implemented FastAPI auth API uses {"detail": "…"}.
      if (decoded is Map<String, dynamic> && decoded['detail'] is String) {
        return decoded['detail'] as String;
      }
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
