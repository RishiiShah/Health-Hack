// In-memory backend that follows the contract's rules, seeded from the sample
// JSON in assets/contracts/ (embedded via fake_samples.g.dart).
//
// Used for: Hitanshu's widget tests (no network), `API_MODE=fake` builds, and
// the backup demo URL. With LIVE_REPOS (e.g. "auth") some repositories are
// live and the rest come from here; see AppServices.fromEnvironment(). Every response goes through the same strict parsers as
// live mode, so a fake that drifts from the contract fails loudly.
//
// Scripting (tests and offline demo):
//   final fake = FakeServices(ticking: false);
//   fake.offers.pushNewOffer();            // a new `sent` offer for the signed-in physician
//   fake.offers.expire('OFF-0007');        // → expired (Missed)
//   fake.offers.audio = bytes;             // spoken offer; null (default) → Unavailable
//   fake.offers.fillByOther('OFF-0007');   // → withdrawn / filled_by_another_physician
//   fake.clock.set(DateTime.parse('2026-03-17T18:34:59-04:00'));
//   fake.lead.addProposal();               // another proposal in the lead queue
//   fake.failNext(const NetworkError());   // next call (any repository) throws
//   await fake.signInAs('okafor');         // skip the sign-in screen
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../../web_alerts.dart';
import '../api.dart';
import '../clock.dart';
import 'fake_samples.g.dart';
import '../feeds.dart';
import '../platform/browser.dart';

typedef JsonMap = Map<String, dynamic>;

JsonMap _sample(String name) {
  final raw = kSamples[name];
  if (raw == null) throw StateError('Missing sample $name');
  return jsonDecode(raw) as JsonMap;
}

T _copy<T>(T json) => jsonDecode(jsonEncode(json)) as T;

/// "2026-03-17T18:25:00-04:00"
String isoEt(DateTime utc) {
  final off = etOffset(utc);
  final e = utc.toUtc().add(off);
  String two(int n) => n.toString().padLeft(2, '0');
  final h = off.inHours.abs();
  final sign = off.isNegative ? '-' : '+';
  return '${e.year}-${two(e.month)}-${two(e.day)}T${two(e.hour)}:${two(e.minute)}:${two(e.second)}'
      '$sign${two(h)}:00';
}

DateTime _t(Object? s) => DateTime.parse(s as String).toUtc();

/// The demo clock starts here in fake mode (inside the 18:20–18:30 window).
final DateTime kFakeStart = DateTime.parse('2026-03-17T18:25:00-04:00');

const _accounts = {
  'lead@demo.sevaro': ('demo-lead', 'mobile_me_lead.json'),
  'shah@demo.sevaro': ('demo-shah', 'mobile_me_shah.json'),
  'okafor@demo.sevaro': ('demo-okafor', 'mobile_me_physician.json'),
  'brennan@demo.sevaro': ('demo-brennan', 'mobile_me_brennan.json'),
};

class FakeServices {
  FakeServices({
    bool ticking = true,
    DateTime Function()? deviceNow,
    DateTime? startAt,
    Browser? browser,
    WebAlerts? alerts,
    Duration latency = Duration.zero,
    bool autoAnswer = true,
    bool allowAnyCredentials = false,
  }) {
    final b = browser ?? sharedBrowser;
    clock = OffsetServerClock(ticking: ticking, deviceNow: deviceNow)
      ..set(startAt ?? kFakeStart);
    backend = FakeBackend(clock, latency: latency, autoAnswer: autoAnswer);
    auth = FakeAuthRepository(
      backend,
      b,
      allowAnyCredentials: allowAnyCredentials,
    );
    offers = FakeOfferRepository(backend);
    shifts = FakeShiftRepository(backend);
    lead = FakeLeadRepository(backend);
    final physicianFeed = PollingPhysicianFeed(offers, browser: b);
    final leadFeed = PollingLeadFeed(lead, browser: b);
    auth.signedOut.listen((_) {
      physicianFeed.stop();
      leadFeed.stop();
    });
    services = AppServices(
      auth: auth,
      offers: offers,
      shifts: shifts,
      lead: lead,
      physicianFeed: physicianFeed,
      leadFeed: leadFeed,
      clock: clock,
      alerts: alerts ?? createWebAlerts(),
      isFake: true,
    );
  }

  late final OffsetServerClock clock;
  late final FakeBackend backend;
  late final FakeAuthRepository auth;
  late final FakeOfferRepository offers;
  late final FakeShiftRepository shifts;
  late final FakeLeadRepository lead;
  late final AppServices services;

  /// The next call to any repository throws [e] (once).
  void failNext(ApiException e) => backend.failNext = e;

  /// Every call throws [e] until called again with null (e.g. "backend down").
  void failAll(ApiException? e) => backend.failAll = e;

  /// Sign in without the form: 'lead', 'shah', 'okafor' or 'brennan'.
  Future<Me> signInAs(String who) => auth.signIn('$who@demo.sevaro', 'demo');

  void dispose() => clock.dispose();
}

class FakeBackend {
  FakeBackend(this.clock, {this.latency = Duration.zero, this.autoAnswer = true}) {
    for (final e in _accounts.entries) {
      mes[e.key] = _sample(e.value.$2);
    }
    offersBy['PHY-009'] = (_sample('mobile_offers.json')['offers'] as List).cast<JsonMap>();
    offersBy['PHY-013'] = [];
    offersBy['PHY-005'] = [];
    notificationsBy['PHY-009'] =
        (_sample('mobile_notifications.json')['items'] as List).cast<JsonMap>();
    final p = _sample('mobile_proposal.json')..remove('server_now');
    proposals[p['proposal_id'] as String] = p;
    final esc = _sample('mobile_escalation.json');
    escalations[esc['escalation_id'] as String] = esc;
    automated = (_sample('mobile_lead_queue.json')['automated_actions'] as List).cast<JsonMap>();
    candidates = _sample('mobile_candidates.json');
    coverage = _sample('mobile_lead_coverage.json');
  }

  final OffsetServerClock clock;
  final Duration latency;
  final bool autoAnswer;

  ApiException? failNext;
  ApiException? failAll;

  /// Email of the signed-in user, or null.
  String? user;

  final Map<String, JsonMap> mes = {};
  final Map<String, List<JsonMap>> offersBy = {}; // physicianId → newest first
  final Map<String, List<JsonMap>> notificationsBy = {};
  final Map<String, JsonMap> proposals = {}; // insertion order = oldest first
  final Map<String, JsonMap> escalations = {};
  final List<JsonMap> broadcasts = [];
  late List<JsonMap> automated;
  late JsonMap candidates;
  late JsonMap coverage;
  final Set<String> filledGaps = {};
  final Map<String, DateTime> _autoAccept = {};
  int _nextOffer = 100;
  int _nextNotification = 100;
  int _nextProposal = 10;

  String get nowIso => isoEt(clock.now());
  JsonMap? get me => user == null ? null : mes[user];
  String? get physicianId => me?['physician_id'] as String?;
  bool get isLead => me?['role'] == 'clinical_lead';

  // ------------------------------------------------------------ plumbing

  Future<T> respond<T>(Object? Function() build, T Function(Object?) parse,
      {bool needsUser = true, bool lead = false, bool physician = false}) async {
    if (latency == Duration.zero) {
      await Future<void>.value();
    } else {
      await Future<void>.delayed(latency);
    }
    final fail = failAll ?? failNext;
    failNext = null;
    if (fail != null) throw fail;
    if (needsUser && me == null) {
      onUnauthorized?.call();
      throw const Unauthorized();
    }
    if (lead && !isLead) throw const Forbidden('Only the clinical lead on duty can do this.');
    if (physician && physicianId == null) throw const Forbidden();
    tick();
    final json = _copy(build());
    if (json is Map<String, dynamic> && json.containsKey('server_now')) {
      json['server_now'] = nowIso;
    }
    return parse(json);
  }

  void Function()? onUnauthorized;

  /// Apply time-based changes: expiry and the scripted auto-answer.
  void tick() {
    final now = clock.now();
    for (final list in offersBy.values) {
      for (final o in list) {
        if (o['status'] == 'sent' && !now.isBefore(_t(o['expires_at']))) {
          _setStatus(o, 'expired');
        }
      }
    }
    for (final e in _autoAccept.entries.toList()) {
      if (!now.isBefore(e.value)) {
        _autoAccept.remove(e.key);
        final o = findOffer(e.key);
        if (o != null && o['status'] == 'sent') acceptOffer(o);
      }
    }
  }

  JsonMap? findOffer(String id, {String? owner}) {
    for (final entry in offersBy.entries) {
      if (owner != null && entry.key != owner) continue;
      for (final o in entry.value) {
        if (o['offer_id'] == id) return o;
      }
    }
    return null;
  }

  String? ownerOf(String offerId) {
    for (final entry in offersBy.entries) {
      if (entry.value.any((o) => o['offer_id'] == offerId)) return entry.key;
    }
    return null;
  }

  void _setStatus(JsonMap o, String status, {String? reason}) {
    o['status'] = status;
    o['status_reason'] = reason;
    o['allowed_actions'] = status == 'sent'
        ? ['accept', 'decline']
        : status == 'accepted'
            ? ['release']
            : <String>[];
    if (status == 'accepted' || status == 'declined') o['responded_at'] = nowIso;
    // Mirror into the lead's tracker.
    for (final b in broadcasts) {
      for (final bo in (b['offers'] as List).cast<JsonMap>()) {
        if (bo['offer_id'] == o['offer_id']) {
          bo['status'] = status;
          bo['status_reason'] = reason;
          bo['responded_at'] = o['responded_at'];
        }
      }
      _refreshBroadcast(b);
    }
  }

  void _refreshBroadcast(JsonMap b) {
    final offers = (b['offers'] as List).cast<JsonMap>();
    final accepted = offers.where((o) => o['status'] == 'accepted').toList();
    if (accepted.isNotEmpty) {
      b['status'] = 'filled';
      b['filled_by'] = {
        'physician_id': accepted.first['physician_id'],
        'display_name': accepted.first['display_name'],
      };
    } else if (offers.every((o) => o['status'] != 'sent')) {
      b['status'] = 'unfilled';
      b['filled_by'] = null;
    } else {
      b['status'] = 'open';
      b['filled_by'] = null;
    }
  }

  void _notify(String physicianId, JsonMap n) {
    (notificationsBy[physicianId] ??= []).insert(0, n);
  }

  void _markRead(String offerId) {
    for (final list in notificationsBy.values) {
      for (final n in list) {
        if (n['offer_id'] == offerId) n['unread'] = false;
      }
    }
  }

  // ------------------------------------------------------------ offer rules (4.5)

  JsonMap actionResult(String outcome, bool applied, JsonMap offer) =>
      {'outcome': outcome, 'applied': applied, 'offer': offer, 'server_now': nowIso};

  JsonMap acceptOffer(JsonMap o) {
    final gap = o['gap_id'] as String;
    switch ((o['status'], o['status_reason'])) {
      case ('sent', _) when filledGaps.contains(gap):
        _setStatus(o, 'withdrawn', reason: 'filled_by_another_physician');
        return actionResult('already_filled', false, o);
      case ('sent', _):
        _setStatus(o, 'accepted');
        o['next_steps'] = _sample('mobile_offer_accept_accepted.json')['offer']['next_steps'];
        o['coverage_after'] = {'staffed': 2, 'required': 2, 'from': o['start']};
        filledGaps.add(gap);
        for (final list in offersBy.values) {
          for (final other in list) {
            if (other != o && other['gap_id'] == gap && other['status'] == 'sent') {
              _setStatus(other, 'withdrawn', reason: 'filled_by_another_physician');
            }
          }
        }
        _markCovered(o);
        return actionResult('accepted', true, o);
      case ('accepted', _):
        return actionResult('accepted', false, o);
      case ('withdrawn', 'filled_by_another_physician'):
        return actionResult('already_filled', false, o);
      case ('withdrawn', _):
        return actionResult('not_open', false, o);
      case ('expired', _):
        return actionResult('expired', false, o);
      case ('declined', _):
        return actionResult('declined', false, o);
      default:
        return actionResult('released', false, o);
    }
  }

  JsonMap declineOffer(JsonMap o) {
    switch ((o['status'], o['status_reason'])) {
      case ('sent', _):
        _setStatus(o, 'declined');
        return actionResult('declined', true, o);
      case ('declined', _):
        return actionResult('declined', false, o);
      case ('accepted', _):
        return actionResult('accepted', false, o);
      case ('withdrawn', 'filled_by_another_physician'):
        return actionResult('already_filled', false, o);
      case ('withdrawn', _):
        return actionResult('not_open', false, o);
      case ('expired', _):
        return actionResult('expired', false, o);
      default:
        return actionResult('released', false, o);
    }
  }

  JsonMap releaseOffer(JsonMap o) {
    switch ((o['status'], o['status_reason'])) {
      case ('accepted', _):
        _setStatus(o, 'released');
        o['next_steps'] = <Object>[];
        o['coverage_after'] = null;
        filledGaps.remove(o['gap_id']);
        _markShort(o);
        return actionResult('released', true, o);
      case ('released', _):
        return actionResult('released', false, o);
      case ('declined', _):
        return actionResult('declined', false, o);
      case ('withdrawn', 'filled_by_another_physician'):
        return actionResult('already_filled', false, o);
      case ('withdrawn', _):
        return actionResult('not_open', false, o);
      case ('expired', _):
        return actionResult('expired', false, o);
      default:
        return actionResult('not_open', false, o);
    }
  }

  void _markCovered(JsonMap o) {
    final hid = (o['hospitals'] as List).cast<JsonMap>().first['hospital_id'];
    for (final h in (coverage['hospitals'] as List).cast<JsonMap>()) {
      if (h['hospital_id'] != hid) continue;
      final cells = (h['cells'] as List).cast<JsonMap>();
      if (cells.length > 1) cells[1]['staffed'] = (cells[1]['required'] as int);
      h['level'] = 'covered';
      final name = mes.values.firstWhere((m) => m['physician_id'] == ownerOf(o['offer_id'] as String),
          orElse: () => {'display_name': 'a physician'})['display_name'];
      h['status_text'] = 'Covered from ${formatEt(_t(o['start']))} · $name';
    }
  }

  void _markShort(JsonMap o) {
    final hid = (o['hospitals'] as List).cast<JsonMap>().first['hospital_id'];
    for (final h in (coverage['hospitals'] as List).cast<JsonMap>()) {
      if (h['hospital_id'] != hid) continue;
      final cells = (h['cells'] as List).cast<JsonMap>();
      if (cells.length > 1) cells[1]['staffed'] = (cells[1]['required'] as int) - 1;
      h['level'] = 'short';
      h['status_text'] = 'Short at ${formatEt(_t(o['start']))} · physician released';
    }
  }

  // ------------------------------------------------------------ creating offers

  JsonMap newOfferFor(String physicianId, {JsonMap? fromProposal}) {
    final now = clock.now();
    final base = _sample('mobile_offers.json')['offers'][0] as JsonMap;
    final id = 'OFF-${(_nextOffer++).toString().padLeft(4, '0')}';
    final o = _copy(base)
      ..['offer_id'] = id
      ..['sent_at'] = isoEt(now)
      ..['approved_at'] = isoEt(now)
      ..['expires_at'] = isoEt(now.add(const Duration(minutes: 10)))
      ..['responded_at'] = null
      ..['status'] = 'sent'
      ..['status_reason'] = null
      ..['allowed_actions'] = ['accept', 'decline']
      ..['next_steps'] = <Object>[]
      ..['coverage_after'] = null;
    if (fromProposal != null) {
      final gap = fromProposal['gap'] as JsonMap;
      o['gap_id'] = fromProposal['gap_id'];
      o['hospitals'] = gap['hospitals'];
      o['routing_hospitals'] = gap['hospitals'];
      o['start'] = gap['start'];
      o['end'] = gap['end'];
      o['hours'] = gap['hours'];
    }
    final hospital = ((o['hospitals'] as List).first as JsonMap)['name'] as String;
    if (physicianId != 'PHY-009') {
      o['why_you'] = ['Credentialed at ${hospital.split(' ').first}', 'Opted in to extra shifts'];
    }
    (offersBy[physicianId] ??= []).insert(0, o);
    final m = mes.values.where((m) => m['physician_id'] == physicianId).firstOrNull;
    if (m != null) m['offers_received_7d'] = (m['offers_received_7d'] as int? ?? 0) + 1;
    _notify(physicianId, {
      'notification_id': 'N-${(_nextNotification++).toString().padLeft(4, '0')}',
      'kind': 'offer',
      'title': 'Extra shift tonight at ${hospital.split(' ').first}',
      'body': '${formatEt(_t(o['start']))} to ${formatEt(_t(o['end']))} ET, approved by your '
          'clinical lead. Please answer within 10 min.',
      'at': isoEt(now),
      'offer_id': id,
      'unread': true,
    });
    return o;
  }

  // ------------------------------------------------------------ lead

  /// R1 follows each physician's live opt-in, so Brennan opting in shows up here.
  JsonMap currentCandidates() {
    final c = _copy(candidates);
    final list = (c['candidates'] as List).cast<JsonMap>();
    for (final cand in list) {
      final m = mes.values.where((m) => m['physician_id'] == cand['physician_id']).firstOrNull;
      if (m == null) continue;
      final r1 = (cand['rules'] as List).cast<JsonMap>().first;
      final optIn = m['split_shift_opt_in'] == true;
      r1['passed'] = optIn;
      r1['detail'] = optIn ? 'Opted in to split shifts' : 'Opted out of split shifts';
    }
    var rank = 0;
    for (final cand in list) {
      final ok = (cand['rules'] as List).cast<JsonMap>().every((r) => r['passed'] == true);
      cand['eligible'] = ok;
      cand['rank'] = ok ? ++rank : null;
    }
    c['server_now'] = nowIso;
    return c;
  }

  /// A proposal as the lead sees it now: recipients and excluded follow R1.
  JsonMap currentProposal(JsonMap p) {
    if (p['status'] != 'proposed' || p['gap_id'] != candidates['gap_id']) return p;
    final cands = (currentCandidates()['candidates'] as List).cast<JsonMap>();
    final out = _copy(p);
    out['recipients'] = [
      for (final c in cands.where((c) => c['eligible'] == true))
        {
          'physician_id': c['physician_id'],
          'display_name': c['display_name'],
          'rank': c['rank'],
          'rank_reason': (p['recipients'] as List)
                  .cast<JsonMap>()
                  .where((r) => r['physician_id'] == c['physician_id'])
                  .firstOrNull?['rank_reason'] ??
              'Covers the gap hospital, opted in',
        }
    ];
    out['excluded'] = [
      for (final c in cands.where((c) => c['eligible'] != true)) _excludedEntry(c),
    ];
    return out;
  }

  JsonMap _excludedEntry(JsonMap c) {
    final failed = (c['rules'] as List).cast<JsonMap>().firstWhere((r) => r['passed'] != true);
    return {
      'physician_id': c['physician_id'],
      'display_name': c['display_name'],
      'failed_rule': failed['rule'],
      'detail': failed['detail'],
    };
  }

  JsonMap _summary(JsonMap p) {
    final gap = p['gap'] as JsonMap;
    return {
      'proposal_id': p['proposal_id'],
      'gap_id': p['gap_id'],
      'hospitals': gap['hospitals'],
      'start': gap['start'],
      'end': gap['end'],
      'recipient_count': (p['recipients'] as List).length,
      'proposed_at': p['proposed_at'],
    };
  }

  JsonMap queueJson() {
    final open = proposals.values.where((p) => p['status'] == 'proposed').toList().reversed;
    final pendingEsc =
        escalations.values.where((e) => e['status'] == 'pending').toList().reversed.toList();
    final summaries = [for (final raw in open) _summary(currentProposal(raw))];
    return {
      'pending_count': summaries.length + pendingEsc.length,
      'proposals': summaries,
      'escalations': pendingEsc,
      'automated_actions': automated,
      'server_now': nowIso,
    };
  }

  JsonMap proposalResult(String outcome, bool applied, JsonMap p,
          {List<JsonMap> offers = const [], List<JsonMap> skipped = const []}) =>
      {
        'outcome': outcome,
        'applied': applied,
        'proposal': p,
        'offers': offers,
        'skipped': skipped,
        'server_now': nowIso,
      };

  JsonMap approve(JsonMap stored) {
    if (stored['status'] == 'approved') return proposalResult('approved', false, stored);
    if (stored['status'] != 'proposed') return proposalResult('already_decided', false, stored);
    final p = currentProposal(stored);
    proposals[p['proposal_id'] as String] = p
      ..['status'] = 'approved'
      ..['decided_by'] = 'Clinical lead on duty'
      ..['decided_at'] = nowIso;
    final sent = <JsonMap>[];
    final tracker = <JsonMap>[];
    for (final r in (p['recipients'] as List).cast<JsonMap>()) {
      final pid = r['physician_id'] as String;
      // Reuse an open offer for this gap (keeps R7: one open offer per physician).
      final existing = (offersBy[pid] ?? [])
          .where((o) => o['gap_id'] == p['gap_id'] && o['status'] == 'sent')
          .firstOrNull;
      final o = existing ?? newOfferFor(pid, fromProposal: p);
      sent.add({'offer_id': o['offer_id'], 'physician_id': pid, 'status': 'sent'});
      tracker.add({
        'offer_id': o['offer_id'],
        'physician_id': pid,
        'display_name': r['display_name'],
        'status': o['status'],
        'status_reason': o['status_reason'],
        'expires_at': o['expires_at'],
        'responded_at': o['responded_at'],
      });
    }
    final gap = p['gap'] as JsonMap;
    broadcasts.insert(0, {
      'proposal_id': p['proposal_id'],
      'gap_id': p['gap_id'],
      'hospitals': gap['hospitals'],
      'start': gap['start'],
      'end': gap['end'],
      'status': 'open',
      'filled_by': null,
      'offers': tracker,
    });
    // Offline demo: the top recipient "answers" 15 s later so the lead sees a toast.
    if (autoAnswer && sent.isNotEmpty) {
      _autoAccept[sent.first['offer_id'] as String] = clock.now().add(const Duration(seconds: 15));
    }
    return proposalResult('approved', true, p, offers: sent);
  }

  JsonMap reject(JsonMap p, String reason) {
    if (p['status'] == 'rejected') return proposalResult('rejected', false, p);
    if (p['status'] != 'proposed') return proposalResult('already_decided', false, p);
    p
      ..['status'] = 'rejected'
      ..['decided_by'] = 'Clinical lead on duty'
      ..['decided_at'] = nowIso
      ..['reject_reason'] = reason;
    return proposalResult('rejected', true, p);
  }

  String addProposal() {
    final id = 'PRP-${(_nextProposal++).toString().padLeft(4, '0')}';
    final p = _sample('mobile_proposal.json')
      ..remove('server_now')
      ..['proposal_id'] = id
      ..['gap_id'] = 'GAP-SYN-008-2000-$id'
      ..['proposed_at'] = nowIso;
    final gap = p['gap'] as JsonMap;
    gap['hospitals'] = [
      {'hospital_id': 'SYN-008', 'name': 'Northfield Medical'}
    ];
    gap['start'] = '2026-03-17T20:00:00-04:00';
    gap['end'] = '2026-03-17T23:00:00-04:00';
    gap['hours'] = 3.0;
    proposals[id] = p;
    return id;
  }
}

// ============================================================== repositories

class FakeAuthRepository implements AuthRepository {
  FakeAuthRepository(
    this._b,
    this._browser, {
    this.allowAnyCredentials = false,
  }) {
    _b.onUnauthorized = () {
      _me.value = null;
      _signedOut.add(null);
    };
  }

  final FakeBackend _b;
  final Browser _browser;
  final bool allowAnyCredentials;
  Role previewRole = Role.physician;
  final Map<String, String> _previewTokens = {};
  final _signedOut = StreamController<void>.broadcast();
  final _me = ValueNotifier<Me?>(null);
  bool _urlRead = false;
  String? _initialOfferId;
  static const _key = 'sevaro_token';

  String? _emailForToken(String? token) =>
      _previewTokens[token] ??
      _accounts.entries.where((e) => e.value.$1 == token).firstOrNull?.key;

  void _readUrlOnce() {
    if (_urlRead) return;
    _urlRead = true;
    final uri = _browser.initialUri;
    final token = uri.queryParameters['token'];
    final offer = uri.queryParameters['offer'];
    if (token != null && token.isNotEmpty) _browser.writeSession(_key, token);
    if (offer != null && offer.isNotEmpty) _initialOfferId = offer;
    if (token != null || offer != null) {
      final rest = Map<String, String>.of(uri.queryParameters)
        ..remove('token')
        ..remove('offer');
      _browser.replaceUrl(uri.replace(queryParameters: rest.isEmpty ? null : rest));
    }
  }

  @override
  Future<Me?> currentUser() async {
    _readUrlOnce();
    final email = _emailForToken(_browser.readSession(_key));
    if (email == null) {
      _browser.removeSession(_key);
      return null;
    }
    _b.user = email;
    return refreshMe();
  }

  @override
  Future<Me> refreshMe() async {
    final me = await _b.respond(() => _b.me, Me.parse);
    _me.value = me;
    return me;
  }

  @override
  Future<Me> signIn(String email, String password) async {
    final key = email.trim().toLowerCase();
    final account = _accounts[key];
    final r = await _b.respond(() {
      if (allowAnyCredentials) {
        if (key.isEmpty || password.isEmpty) {
          throw const Unauthorized('Enter your email and password.');
        }
        final sample = _sample(
          previewRole == Role.clinicalLead
              ? 'mobile_me_lead.json'
              : 'mobile_me_shah.json',
        );
        sample['user_id'] = 'dummy-$key';
        sample['display_name'] = email.trim();
        _b.mes[key] = sample;
        return {'token': 'dummy-${previewRole.wire}:$key', 'me': sample};
      }
      if (account == null || password != 'demo') {
        throw const Unauthorized('Wrong email or password. Demo accounts use the password "demo".');
      }
      return {'token': account.$1, 'me': _b.mes[key]};
    }, LoginResult.parse, needsUser: false);
    _b.user = key;
    if (allowAnyCredentials) _previewTokens[r.token] = key;
    _browser.writeSession(_key, r.token);
    _me.value = r.me;
    return r.me;
  }

  @override
  Future<void> signOut() async {
    _b.user = null;
    _browser.removeSession(_key);
    _me.value = null;
    _signedOut.add(null);
  }

  @override
  Future<PreferencesResult> setOptIn(bool optIn, {bool declineOpenOffer = false}) async {
    final r = await _b.respond(() {
      final me = _b.me!;
      final pid = _b.physicianId!;
      final open = (_b.offersBy[pid] ?? []).where((o) => o['status'] == 'sent').firstOrNull;
      if (me['split_shift_opt_in'] == optIn) {
        return {'applied': false, 'outcome': 'unchanged', 'open_offer_id': null, 'me': me, 'server_now': ''};
      }
      if (!optIn && open != null && !declineOpenOffer) {
        return {
          'applied': false,
          'outcome': 'open_offer_exists',
          'open_offer_id': open['offer_id'],
          'me': me,
          'server_now': '',
        };
      }
      if (!optIn && open != null) _b.declineOffer(open);
      me['split_shift_opt_in'] = optIn;
      return {'applied': true, 'outcome': 'updated', 'open_offer_id': null, 'me': me, 'server_now': ''};
    }, PreferencesResult.parse, physician: true);
    _me.value = r.me;
    return r;
  }

  @override
  String? takeInitialOfferId() {
    _readUrlOnce();
    final id = _initialOfferId;
    _initialOfferId = null;
    return id;
  }

  @override
  Stream<void> get signedOut => _signedOut.stream;

  @override
  ValueListenable<Me?> get me => _me;
}

class FakeOfferRepository implements OfferRepository {
  FakeOfferRepository(this._b);
  final FakeBackend _b;

  JsonMap _own(String id) {
    final o = _b.findOffer(id, owner: _b.physicianId);
    if (o == null) throw const NotFound();
    return o;
  }

  @override
  Future<OfferList> listOffers() => _b.respond(
      () => {'offers': _b.offersBy[_b.physicianId] ?? [], 'server_now': ''}, OfferList.parse,
      physician: true);

  @override
  Future<Offer> getOffer(String offerId) => _b.respond(() {
        final o = _own(offerId);
        _b._markRead(offerId);
        return {...o, 'server_now': ''};
      }, Offer.parse, physician: true);

  @override
  Future<OfferActionResult> accept(String offerId) => _b.respond(() {
        _b._markRead(offerId);
        return _b.acceptOffer(_own(offerId));
      }, OfferActionResult.parse, physician: true);

  @override
  Future<OfferActionResult> decline(String offerId) => _b.respond(() {
        _b._markRead(offerId);
        return _b.declineOffer(_own(offerId));
      }, OfferActionResult.parse, physician: true);

  @override
  Future<OfferActionResult> release(String offerId) =>
      _b.respond(() => _b.releaseOffer(_own(offerId)), OfferActionResult.parse, physician: true);

  /// The spoken offer [getOfferAudio] returns. Null: there is no text-to-speech
  /// without a server, so the call is [Unavailable] and screens show the text.
  Uint8List? audio;

  @override
  Future<Uint8List> getOfferAudio(String offerId) => _b.respond(() {
        _own(offerId);
        return null;
      }, (_) => audio ?? (throw const Unavailable('Text-to-speech unavailable.')), physician: true);

  @override
  Future<NotificationList> notifications() => _b.respond(
      () => {'items': _b.notificationsBy[_b.physicianId] ?? [], 'server_now': ''},
      NotificationList.parse,
      physician: true);

  // ---------------------------------------------------------- scripting

  /// A new `sent` offer (10-minute timer from the fake clock) for [physicianId],
  /// default the signed-in physician (else Okafor). Returns its offer_id.
  String pushNewOffer({String? physicianId}) {
    final pid = physicianId ?? _b.physicianId ?? 'PHY-009';
    for (final o in _b.offersBy[pid] ?? <JsonMap>[]) {
      if (o['status'] == 'sent') _b._setStatus(o, 'withdrawn', reason: 'gap_closed'); // keep R7
    }
    return _b.newOfferFor(pid)['offer_id'] as String;
  }

  void expire(String offerId) {
    final o = _b.findOffer(offerId);
    if (o == null) throw StateError('No offer $offerId');
    _b._setStatus(o, 'expired');
  }

  void fillByOther(String offerId) {
    final o = _b.findOffer(offerId);
    if (o == null) throw StateError('No offer $offerId');
    _b.filledGaps.add(o['gap_id'] as String);
    _b._setStatus(o, 'withdrawn', reason: 'filled_by_another_physician');
  }

  void closeGap(String offerId) {
    final o = _b.findOffer(offerId);
    if (o == null) throw StateError('No offer $offerId');
    _b._setStatus(o, 'withdrawn', reason: 'gap_closed');
  }
}

class FakeShiftRepository implements ShiftRepository {
  FakeShiftRepository(this._b);
  final FakeBackend _b;

  @override
  Future<MyShift> myShift() => _b.respond(
      () => _sample(_b.me?['on_shift'] == true ? 'mobile_shift_on.json' : 'mobile_shift_off.json'),
      MyShift.parse,
      physician: true);

  @override
  Future<MySchedule> mySchedule(DateTime weekStart) => _b.respond(() {
        final s = _sample('mobile_schedule.json');
        if (formatDate(weekStart) != s['week_start']) {
          // Other weeks: same shape, nothing scheduled with you.
          s['week_start'] = formatDate(weekStart);
          s['days'] = [
            for (var i = 0; i < 7; i++)
              {'date': formatDate(weekStart.add(Duration(days: i))), 'kind': i == 0 || i == 6 ? 'off' : 'day'}
          ];
          s['with_you'] = null;
        }
        return s;
      }, MySchedule.parse, physician: true);
}

class FakeLeadRepository implements LeadRepository {
  FakeLeadRepository(this._b);
  final FakeBackend _b;

  JsonMap _proposal(String id) {
    final p = _b.proposals[id];
    if (p == null) throw const NotFound();
    return p;
  }

  @override
  Future<LeadQueue> queue() => _b.respond(_b.queueJson, LeadQueue.parse, lead: true);

  @override
  Future<Proposal> proposal(String proposalId) => _b.respond(
      () => {..._b.currentProposal(_proposal(proposalId)), 'server_now': ''}, Proposal.parse,
      lead: true);

  @override
  Future<ProposalActionResult> approve(String proposalId) =>
      _b.respond(() => _b.approve(_proposal(proposalId)), ProposalActionResult.parse, lead: true);

  @override
  Future<ProposalActionResult> reject(String proposalId, String reason) => _b.respond(() {
        if (reason.trim().isEmpty) throw const InvalidRequest('Please give a reason for rejecting.');
        return _b.reject(_proposal(proposalId), reason.trim());
      }, ProposalActionResult.parse, lead: true);

  @override
  Future<CandidateList> candidates(String gapId) =>
      _b.respond(_b.currentCandidates, CandidateList.parse, lead: true);

  @override
  Future<TrapCheck> trapCheck(String gapId) =>
      _b.respond(() => _sample('mobile_trap_check.json')..['gap_id'] = gapId, TrapCheck.parse, lead: true);

  @override
  Future<AuditLog> audit(String gapId) => _b.respond(() {
        final log = _sample('mobile_audit.json')..['gap_id'] = gapId;
        final entries = (log['entries'] as List).cast<JsonMap>().take(3).toList();
        for (final p in _b.proposals.values.where((p) => p['gap_id'] == gapId && p['decided_at'] != null)) {
          entries.add({
            'at': p['decided_at'],
            'actor': 'Clinical lead on duty',
            'action': 'proposal_${p['status']}',
            'detail': p['status'] == 'approved'
                ? 'Sent to ${(p['recipients'] as List).length} physician(s)'
                : 'Reason: ${p['reject_reason']}',
          });
        }
        for (final b in _b.broadcasts.where((b) => b['gap_id'] == gapId)) {
          for (final o in (b['offers'] as List).cast<JsonMap>().where((o) => o['responded_at'] != null)) {
            entries.add({
              'at': o['responded_at'],
              'actor': o['display_name'],
              'action': 'offer_${o['status']}',
              'detail': 'Offer ${o['offer_id']}',
            });
          }
        }
        entries.sort((a, b) => _t(a['at']).compareTo(_t(b['at'])));
        log['entries'] = entries;
        return log;
      }, AuditLog.parse, lead: true);

  @override
  Future<BroadcastList> activeOffers() =>
      _b.respond(() => {'broadcasts': _b.broadcasts, 'server_now': ''}, BroadcastList.parse, lead: true);

  @override
  Future<EscalationActionResult> authorize(String escalationId) => _b.respond(() {
        final e = _b.escalations[escalationId];
        if (e == null) throw const NotFound();
        final applied = e['status'] == 'pending';
        if (applied) {
          e
            ..['status'] = 'authorized'
            ..['authorized_by'] = 'Clinical lead on duty'
            ..['authorized_at'] = _b.nowIso;
        }
        return {
          'outcome': applied ? 'authorized' : 'already_authorized',
          'applied': applied,
          'escalation': e,
          'server_now': '',
        };
      }, EscalationActionResult.parse, lead: true);

  @override
  Future<CoverageBoard> coverage() => _b.respond(() => _b.coverage, CoverageBoard.parse, lead: true);

  @override
  Future<LeadSchedule> schedule(DateTime date) => _b.respond(() {
        final s = _sample('mobile_lead_schedule.json');
        final open = _b.proposals.values.where((p) => p['status'] == 'proposed').firstOrNull;
        s['banner'] = open == null
            ? null
            : {'text': s['banner']['text'], 'proposal_id': open['proposal_id']};
        return s;
      }, LeadSchedule.parse, lead: true);

  // ---------------------------------------------------------- scripting

  /// Adds another proposal (Northfield 20:00–23:00) to the queue; returns its id.
  String addProposal() => _b.addProposal();
}
