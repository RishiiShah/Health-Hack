// Live contract checker: signs in to API_BASE_URL with each demo account and
// calls every endpoint that account may use, through the real repositories,
// then prints endpoint · HTTP status · parsed OK / the ParseError message.
// Read-only unless MUTATE=true. Skips (does not fail) if the backend is down.
//
//   flutter test integration/contract_check_test.dart \
//       --dart-define-from-file=config/local.json
//   flutter test integration/contract_check_test.dart \
//       --dart-define-from-file=config/local.json --dart-define=MUTATE=true
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:sevaro_mobile/data/api.dart';
import 'package:sevaro_mobile/data/config.dart';
import 'package:sevaro_mobile/data/live/live.dart';
import 'package:sevaro_mobile/data/platform/browser.dart';

const _mutate = bool.fromEnvironment('MUTATE');

/// Remembers the HTTP status of the last response per "METHOD /path".
class _Recorder extends http.BaseClient {
  final _inner = http.Client();
  final status = <String, int>{};

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final res = await _inner.send(request);
    status['${request.method} ${request.url.path}'] = res.statusCode;
    return res;
  }
}

class _Row {
  _Row(this.endpoint, this.status, this.verdict, this.ok);
  final String endpoint;
  final String status;
  final String verdict;
  final bool ok;
}

class _Account {
  _Account(this.email) : recorder = _Recorder(), browser = MemoryBrowser() {
    services = LiveServices.create(
      Uri.parse(AppConfig.apiBaseUrl),
      httpClient: recorder,
      browser: browser,
    );
  }

  final String email;
  final _Recorder recorder;
  final MemoryBrowser browser;
  late final AppServices services;
  final rows = <_Row>[];

  /// Runs [call] and records one row. [path] is the "METHOD /path" the client
  /// sends (to look up the HTTP status). [expect] is the exception type a
  /// negative check should produce instead of a parsed result.
  Future<T?> row<T>(
    String label,
    String path,
    Future<T> Function() call, {
    Type? expect,
  }) async {
    String verdict;
    var ok = false;
    T? result;
    try {
      result = await call();
      verdict = expect == null ? 'parsed OK' : 'expected $expect, got a result';
      ok = expect == null;
    } on ParseError catch (e) {
      verdict = 'ParseError: ${e.message}';
    } on ApiException catch (e) {
      verdict = '${e.runtimeType}: ${e.message}';
      ok = expect != null && e.runtimeType == expect;
      if (ok) verdict = 'parsed OK (${e.runtimeType} as expected)';
    }
    final code = recorder.status[path];
    rows.add(_Row(label, code?.toString() ?? '—', verdict, ok));
    return result;
  }

  void printTable() {
    final w = rows.fold<int>(
      8,
      (m, r) => r.endpoint.length > m ? r.endpoint.length : m,
    );
    final out = StringBuffer('\n── $email ${'─' * 40}\n');
    for (final r in rows) {
      out.writeln(
        '${r.ok ? '✓' : '✗'} ${r.endpoint.padRight(w)} · ${r.status.padLeft(3)} · ${r.verdict}',
      );
    }
    // ignore: avoid_print
    print(out);
  }

  List<_Row> get problems => rows.where((r) => !r.ok).toList();
}

Future<bool> _reachable() async {
  final probe = _Account('probe');
  try {
    await probe.services.auth.signIn('lead@demo.sevaro', 'demo');
  } on NetworkError {
    return false;
  } on ApiException {
    // The backend answered (even with an error): reachable.
  }
  return true;
}

/// POST /auth/login plus GET /me. False when no token could be obtained.
Future<bool> _signIn(_Account a) async {
  final me = await a.row(
    'POST /auth/login',
    'POST /auth/login',
    () => a.services.auth.signIn(a.email, 'demo'),
  );
  if (me == null) return false;
  await a.row('GET /me', 'GET /me', () => a.services.auth.refreshMe());
  return true;
}

Future<void> _physician(_Account a) async {
  if (!await _signIn(a)) return;
  final s = a.services;
  final list = await a.row(
    'GET /offers',
    'GET /offers',
    () => s.offers.listOffers(),
  );
  await a.row(
    'GET /notifications',
    'GET /notifications',
    () => s.offers.notifications(),
  );
  await a.row('GET /me/shift', 'GET /me/shift', () => s.shifts.myShift());
  await a.row(
    'GET /me/schedule?week_start=',
    'GET /me/schedule',
    () => s.shifts.mySchedule(etWeekStart(s.clock.now())),
  );
  final first = list?.offers.firstOrNull;
  if (first != null) {
    await a.row(
      'GET /offers/{id}',
      'GET /offers/${first.offerId}',
      () => s.offers.getOffer(first.offerId),
    );
  }
  await a.row(
    'GET /lead/queue (must be 403)',
    'GET /lead/queue',
    () => s.lead.queue(),
    expect: Forbidden,
  );
}

Future<void> _lead(_Account a) async {
  if (!await _signIn(a)) return;
  final s = a.services;
  final queue = await a.row(
    'GET /lead/queue',
    'GET /lead/queue',
    () => s.lead.queue(),
  );
  await a.row(
    'GET /lead/offers?active=true',
    'GET /lead/offers',
    () => s.lead.activeOffers(),
  );
  await a.row(
    'GET /lead/coverage',
    'GET /lead/coverage',
    () => s.lead.coverage(),
  );
  await a.row(
    'GET /lead/schedule?date=',
    'GET /lead/schedule',
    () => s.lead.schedule(etDate(s.clock.now())),
  );

  final summary = queue?.proposals.firstOrNull;
  if (summary == null) {
    a.rows.add(
      _Row(
        'GET /proposals/{id} and /gaps/{id}/*',
        '—',
        'no pending proposal in /lead/queue to read',
        false,
      ),
    );
    return;
  }
  final id = summary.proposalId;
  final gap = summary.gapId;
  await a.row(
    'GET /proposals/{id}',
    'GET /proposals/$id',
    () => s.lead.proposal(id),
  );
  await a.row(
    'GET /gaps/{id}/candidates',
    'GET /gaps/$gap/candidates',
    () => s.lead.candidates(gap),
  );
  await a.row(
    'GET /gaps/{id}/trap-check',
    'GET /gaps/$gap/trap-check',
    () => s.lead.trapCheck(gap),
  );
  await a.row(
    'GET /gaps/{id}/audit',
    'GET /gaps/$gap/audit',
    () => s.lead.audit(gap),
  );
  if (queue!.escalations.isEmpty) {
    a.rows.add(
      _Row(
        'POST /escalations/{id}/authorize',
        '—',
        'skipped: no pending escalation',
        true,
      ),
    );
  }
}

/// MUTATE=true: the demo flow. Changes backend state; /admin/reset afterwards.
Future<void> _mutations(Map<String, _Account> by) async {
  final lead = by['lead']!;
  final okafor = by['okafor']!;
  final brennan = by['brennan']!;
  final queue = await lead.services.lead.queue();
  final proposal = queue.proposals.firstOrNull;
  if (proposal == null) {
    lead.rows.add(
      _Row(
        'POST /proposals/{id}/approve',
        '—',
        'MUTATE: no pending proposal',
        false,
      ),
    );
    return;
  }
  final id = proposal.proposalId;
  await lead.row(
    'POST /proposals/{id}/reject (empty reason → 422)',
    'POST /proposals/$id/reject',
    () => lead.services.lead.reject(id, ''),
    expect: InvalidRequest,
  );
  final approved = await lead.row(
    'POST /proposals/{id}/approve',
    'POST /proposals/$id/approve',
    () => lead.services.lead.approve(id),
  );
  await lead.row(
    'POST /proposals/{id}/approve (repeat → applied false)',
    'POST /proposals/$id/approve',
    () async {
      final r = await lead.services.lead.approve(id);
      if (r.applied) {
        throw const ParseError('repeat approve returned applied: true');
      }
      return r;
    },
  );
  if (approved == null) return;

  final okOffer = (await okafor.services.offers.listOffers()).offers
      .where((o) => o.status == OfferStatus.sent)
      .firstOrNull;
  if (okOffer == null) {
    okafor.rows.add(
      _Row(
        'POST /offers/{id}/accept',
        '—',
        'MUTATE: no sent offer after approve',
        false,
      ),
    );
    return;
  }
  await okafor.row(
    'POST /offers/{id}/accept',
    'POST /offers/${okOffer.offerId}/accept',
    () async {
      final r = await okafor.services.offers.accept(okOffer.offerId);
      if (r.outcome != OfferOutcome.accepted) {
        throw ParseError('expected outcome accepted, got ${r.outcome.wire}');
      }
      return r;
    },
  );
  await okafor.row(
    'POST /offers/{id}/accept (repeat → applied false)',
    'POST /offers/${okOffer.offerId}/accept',
    () async {
      final r = await okafor.services.offers.accept(okOffer.offerId);
      if (r.applied) {
        throw const ParseError('repeat accept returned applied: true');
      }
      return r;
    },
  );

  final brOffer =
      (await brennan.services.offers.listOffers()).offers.firstOrNull;
  if (brOffer != null) {
    await brennan.row(
      'POST /offers/{id}/accept (late → already_filled)',
      'POST /offers/${brOffer.offerId}/accept',
      () async {
        final r = await brennan.services.offers.accept(brOffer.offerId);
        if (r.outcome != OfferOutcome.alreadyFilled) {
          throw ParseError('expected already_filled, got ${r.outcome.wire}');
        }
        return r;
      },
    );
  }
}

void main() {
  final accounts = <String, _Account>{};
  var up = true;

  setUpAll(() async {
    // ignore: avoid_print
    print(
      'Contract check against ${AppConfig.apiBaseUrl}${_mutate ? ' (MUTATE=true)' : ' (read-only)'}',
    );
    up = await _reachable();
    if (!up) {
      // ignore: avoid_print
      print(
        '\nBackend not reachable at ${AppConfig.apiBaseUrl}; skipping the contract check.',
      );
      return;
    }
    for (final name in ['lead', 'okafor', 'brennan', 'shah']) {
      accounts[name] = _Account('$name@demo.sevaro');
    }
  });

  for (final name in ['lead', 'okafor', 'brennan', 'shah']) {
    test('$name@demo.sevaro', () async {
      if (!up) {
        markTestSkipped('backend not reachable at ${AppConfig.apiBaseUrl}');
        return;
      }
      final a = accounts[name]!;
      name == 'lead' ? await _lead(a) : await _physician(a);
      expect(a.problems.map((r) => '${r.endpoint}: ${r.verdict}'), isEmpty);
    });
  }

  test('mutations (MUTATE=true)', () async {
    if (!up || !_mutate) {
      markTestSkipped(
        up
            ? 'read-only run; pass --dart-define=MUTATE=true'
            : 'backend not reachable',
      );
      return;
    }
    await _mutations(accounts);
    final problems = [for (final a in accounts.values) ...a.problems];
    expect(problems.map((r) => '${r.endpoint}: ${r.verdict}'), isEmpty);
  });

  tearDownAll(() {
    if (!up) return;
    for (final a in accounts.values) {
      a.printTable();
    }
    final problems = {for (final e in accounts.entries) e.key: e.value.problems}
      ..removeWhere((_, v) => v.isEmpty);
    // ignore: avoid_print
    print(
      problems.isEmpty
          ? '\nAll checked endpoints match the contract.'
          : '\nDrift: ${problems.values.fold<int>(0, (n, v) => n + v.length)} endpoint(s) to fix, see ✗ rows above.',
    );
  });
}
