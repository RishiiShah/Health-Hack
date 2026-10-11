// Eastern Time formatting without a timezone package.
//
// All DateTimes from the data layer are UTC. Screens format them here and label
// them "ET". America/New_York: EDT (UTC-4) from the second Sunday in March at
// 02:00 local to the first Sunday in November at 02:00 local; EST (UTC-5) otherwise.

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// UTC offset of America/New_York at the instant [utc].
Duration etOffset(DateTime utc) {
  final u = utc.toUtc();
  final y = u.year;
  // DST starts 2nd Sunday of March, 02:00 EST = 07:00 UTC.
  final start = _nthSunday(y, 3, 2).add(const Duration(hours: 7));
  // DST ends 1st Sunday of November, 02:00 EDT = 06:00 UTC.
  final end = _nthSunday(y, 11, 1).add(const Duration(hours: 6));
  final dst = !u.isBefore(start) && u.isBefore(end);
  return Duration(hours: dst ? -4 : -5);
}

DateTime _nthSunday(int year, int month, int n) {
  final first = DateTime.utc(year, month, 1);
  final toSunday = (DateTime.sunday - first.weekday) % 7;
  return first.add(Duration(days: toSunday + 7 * (n - 1)));
}

/// Wall-clock fields in ET, carried in a UTC DateTime (only use its fields).
DateTime toEtFields(DateTime utc) => utc.toUtc().add(etOffset(utc));

String _two(int n) => n.toString().padLeft(2, '0');

/// "19:00"
String formatEt(DateTime utc) {
  final e = toEtFields(utc);
  return '${_two(e.hour)}:${_two(e.minute)}';
}

/// "19:00 ET"
String formatEtLabel(DateTime utc) => '${formatEt(utc)} ET';

/// "19:00–23:00 ET"
String formatEtRange(DateTime start, DateTime end) => '${formatEt(start)}–${formatEt(end)} ET';

/// "Tue 17 Mar"
String formatEtDay(DateTime utc) {
  final e = toEtFields(utc);
  return '${_weekdays[e.weekday - 1]} ${e.day} ${_months[e.month - 1]}';
}

/// "Tue 17 Mar · 18:22 ET" (lead header)
String formatEtHeader(DateTime utc) => '${formatEtDay(utc)} · ${formatEtLabel(utc)}';

/// The ET calendar date of [utc], as UTC midnight (use with formatDate()).
DateTime etDate(DateTime utc) {
  final e = toEtFields(utc);
  return DateTime.utc(e.year, e.month, e.day);
}

/// The Sunday starting the ET week that contains [utc], as UTC midnight.
DateTime etWeekStart(DateTime utc) {
  final d = etDate(utc);
  return d.subtract(Duration(days: d.weekday % 7));
}

/// "9:41" countdown (m:ss), never negative.
String formatCountdown(Duration d) {
  final s = d.isNegative ? 0 : d.inSeconds;
  return '${s ~/ 60}:${_two(s % 60)}';
}

/// "1 h 36 min" (time left on shift), never negative.
String formatHoursMinutes(Duration d) {
  final m = d.isNegative ? 0 : d.inMinutes;
  final h = m ~/ 60;
  final r = m % 60;
  if (h == 0) return '$r min';
  return '$h h $r min';
}
