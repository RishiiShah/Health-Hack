import 'exceptions.dart';

/// Strict JSON reading (contract section 2).
///
/// * Required field missing or `null` → [ParseError].
/// * Wrong type → [ParseError].
/// * Unknown enum value → [ParseError].
/// * Nullable fields (`...N` readers) accept `null` or a missing key.
/// * Timestamps must carry a UTC offset (`Z` or `±hh:mm`) and are returned in UTC.
class J {
  J(Object? raw, this.path)
      : m = raw is Map<String, dynamic>
            ? raw
            : throw ParseError('$path: expected an object, got ${_kind(raw)}');

  final Map<String, dynamic> m;
  final String path;

  Object? _req(String k) {
    if (!m.containsKey(k)) throw ParseError('$path.$k: required field missing');
    final v = m[k];
    if (v == null) throw ParseError('$path.$k: required field is null');
    return v;
  }

  T _as<T>(String k, Object? v) {
    if (v is T) return v;
    throw ParseError('$path.$k: expected $T, got ${_kind(v)}');
  }

  String str(String k) => _as<String>(k, _req(k));
  String? strN(String k) => m[k] == null ? null : _as<String>(k, m[k]);

  bool boolean(String k) => _as<bool>(k, _req(k));
  bool? boolN(String k) => m[k] == null ? null : _as<bool>(k, m[k]);

  int integer(String k) => _int(k, _req(k));
  int? intN(String k) => m[k] == null ? null : _int(k, m[k]);
  int _int(String k, Object? v) {
    if (v is int) return v;
    throw ParseError('$path.$k: expected int, got ${_kind(v)}');
  }

  double number(String k) {
    final v = _req(k);
    if (v is num) return v.toDouble();
    throw ParseError('$path.$k: expected number, got ${_kind(v)}');
  }

  DateTime time(String k) => parseTimestamp(str(k), '$path.$k');
  DateTime? timeN(String k) =>
      m[k] == null ? null : parseTimestamp(_as<String>(k, m[k]), '$path.$k');

  /// `YYYY-MM-DD`, returned as UTC midnight of that calendar date.
  DateTime date(String k) => parseDate(str(k), '$path.$k');

  E enumv<E extends WireEnum>(String k, List<E> values) =>
      parseWire(values, str(k), '$path.$k');
  E? enumN<E extends WireEnum>(String k, List<E> values) =>
      m[k] == null ? null : parseWire(values, _as<String>(k, m[k]), '$path.$k');

  J obj(String k) => J(_req(k), '$path.$k');
  J? objN(String k) => m[k] == null ? null : J(m[k], '$path.$k');

  T one<T>(String k, T Function(J) f) => f(obj(k));
  T? oneN<T>(String k, T Function(J) f) {
    final o = objN(k);
    return o == null ? null : f(o);
  }

  List<T> list<T>(String k, T Function(J) f) {
    final v = _as<List<dynamic>>(k, _req(k));
    return List.unmodifiable([
      for (var i = 0; i < v.length; i++) f(J(v[i], '$path.$k[$i]')),
    ]);
  }

  List<String> strings(String k) {
    final v = _as<List<dynamic>>(k, _req(k));
    return List.unmodifiable([
      for (var i = 0; i < v.length; i++)
        v[i] is String
            ? v[i] as String
            : throw ParseError('$path.$k[$i]: expected String, got ${_kind(v[i])}'),
    ]);
  }

  List<DateTime> times(String k) {
    final v = _as<List<dynamic>>(k, _req(k));
    return List.unmodifiable([
      for (var i = 0; i < v.length; i++)
        v[i] is String
            ? parseTimestamp(v[i] as String, '$path.$k[$i]')
            : throw ParseError('$path.$k[$i]: expected timestamp, got ${_kind(v[i])}'),
    ]);
  }

  List<E> enums<E extends WireEnum>(String k, List<E> values) => List.unmodifiable([
        for (final (i, s) in strings(k).indexed) parseWire(values, s, '$path.$k[$i]'),
      ]);
}

/// Enums carry the exact `snake_case` value used on the wire.
abstract interface class WireEnum {
  String get wire;
}

E parseWire<E extends WireEnum>(List<E> values, String s, String path) {
  for (final v in values) {
    if (v.wire == s) return v;
  }
  throw ParseError('$path: unknown value "$s"');
}

final _offset = RegExp(r'(Z|[+-]\d\d:\d\d)$');
final _dateOnly = RegExp(r'^\d{4}-\d{2}-\d{2}$');

DateTime parseTimestamp(String s, String path) {
  if (!_offset.hasMatch(s)) {
    throw ParseError('$path: timestamp "$s" has no UTC offset');
  }
  final d = DateTime.tryParse(s);
  if (d == null) throw ParseError('$path: bad timestamp "$s"');
  return d.toUtc();
}

DateTime parseDate(String s, String path) {
  if (!_dateOnly.hasMatch(s)) throw ParseError('$path: bad date "$s"');
  final d = DateTime.tryParse('${s}T00:00:00Z');
  if (d == null) throw ParseError('$path: bad date "$s"');
  return d;
}

/// `YYYY-MM-DD` for query strings (`week_start`, `date`). Uses the calendar
/// fields of [d] as given; pass a date from `etDate()` or a UTC-midnight date.
String formatDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

String _kind(Object? v) => switch (v) {
      null => 'null',
      String() => 'String',
      bool() => 'bool',
      int() => 'int',
      double() => 'double',
      List() => 'List',
      Map() => 'Map',
      _ => v.runtimeType.toString(),
    };
