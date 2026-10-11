/// Every failure the data layer can surface to a screen (contract section 6).
///
/// Business results (filled, expired, already decided) are NOT exceptions:
/// they arrive as a 200 with an `outcome`.
sealed class ApiException implements Exception {
  const ApiException(this.message);

  /// Human-readable text. For [InvalidRequest] and a login [Unauthorized]
  /// this is the server's message and is safe to show as-is.
  final String message;

  @override
  String toString() => '$runtimeType: $message';
}

/// 401. Any call except sign-in also fires `AuthRepository.signedOut`.
final class Unauthorized extends ApiException {
  const Unauthorized([super.message = 'Please sign in again.']);
}

/// 403. Show "You don't have permission for this." Nothing changes.
final class Forbidden extends ApiException {
  const Forbidden([super.message = "You don't have permission for this."]);
}

/// 404. Also returned for another physician's offer.
final class NotFound extends ApiException {
  const NotFound([super.message = 'This item is no longer available.']);
}

/// A native backend business conflict. Adapters can reload the authoritative state.
final class Conflict extends ApiException {
  const Conflict(super.message, this.body);
  final Object? body;
}

/// 422. [message] is the server's text, e.g. an empty reject reason.
final class InvalidRequest extends ApiException {
  const InvalidRequest(super.message);
}

/// 503 (or any other 5xx).
final class Unavailable extends ApiException {
  const Unavailable([super.message = "Can't reach Sevaro."]);
}

/// A workflow outside the implemented backend capabilities; retry cannot add it.
final class UnsupportedFeature extends ApiException {
  const UnsupportedFeature(super.message);
}

/// No response, connection failure, or the 10 s timeout.
final class NetworkError extends ApiException {
  const NetworkError([super.message = "Can't reach Sevaro."]);
}

/// Bad JSON, a missing required field, a wrong type, or an unknown enum value.
final class ParseError extends ApiException {
  const ParseError(super.message);
}
