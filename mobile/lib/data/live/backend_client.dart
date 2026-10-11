import '../exceptions.dart';
import '../json.dart';
import 'client.dart';

typedef Json = Map<String, dynamic>;

/// Presentation adapter for the implemented backend. Decisions, eligibility,
/// rankings, staffing counts and state transitions always come from the server.
/// The older mobile contract remains available to previews and contract tests.
class BackendApiClient extends ApiClient {
  BackendApiClient({
    required super.baseUrl,
    required super.tokens,
    required super.clock,
    required super.onUnauthorized,
    super.httpClient,
  });

  Future<Json> _read(String path, {Map<String, String>? query}) =>
      super.get(path, (raw) => J(raw, path).m, query: query);
  final _proposals = <String, Json>{};
  void clearWorkflowCache() => _proposals.clear();

  String _now(Json row) => J(row, 'Backend').str('server_now');
  List<Json> _items(Json row, [String key = 'items']) =>
      J(row, 'Backend').list(key, (j) => j.m);
  List<Json> _hospitals(Json row) {
    final j = J(row, 'Backend');
    final ids = j.strings('hospital_ids'), names = j.strings('hospital_names');
    if (ids.length != names.length) {
      throw const ParseError('Hospital IDs and names do not match.');
    }
    return [
      for (var i = 0; i < ids.length; i++)
        {'hospital_id': ids[i], 'name': names[i]},
    ];
  }

  double _hours(Json row) {
    final j = J(row, 'Window');
    return j.time('end').difference(j.time('start')).inMinutes / 60;
  }

  String _status(Json row) => switch (J(row, 'Offer').str('state')) {
    'Sent' => 'sent',
    'Accepted' => 'accepted',
    'Declined' => 'declined',
    'Expired' => 'expired',
    'Withdrawn' || 'Cancelled' || 'Already filled' => 'withdrawn',
    final state => throw ParseError('Offer is not physician-visible: $state'),
  };
  String _proposalStatus(Json row) => switch (row['state']) {
    'Proposed' => 'proposed',
    'Rejected' => 'rejected',
    'Cancelled' => 'cancelled',
    'Sent' ||
    'Accepted' ||
    'Declined' ||
    'Expired' ||
    'Withdrawn' ||
    'Already filled' => 'approved',
    final state => throw ParseError('Unknown proposal state: $state'),
  };
  Json _offer(Json row) {
    final status = _status(row), sites = _hospitals(row);
    final reason =
        row['message'] ??
        row['reason'] ??
        'Coverage offer for ${sites.map((h) => h['name']).join(', ')}';
    return {
      ...row,
      'hospitals': sites,
      'hours': _hours(row),
      'reason': reason,
      'status': status,
      'status_reason': status == 'withdrawn' ? 'gap_closed' : null,
      'routing_hospitals': sites,
      'gap_summary': reason,
      'sign_in_by': row['start'],
      'why_you': <String>[],
      'allowed_actions': status == 'sent' ? ['accept', 'decline'] : <String>[],
      'next_steps': <Json>[],
      'coverage_after': null,
    };
  }

  Json _me(Json row) {
    final permissions = J(row, 'Me').strings('permissions');
    return {
      ...row,
      'role': row['role'] == 'lead' ? 'clinical_lead' : row['role'],
      'permissions': [
        if (permissions.contains('offers.respond')) ...[
          'offers.accept',
          'offers.decline',
        ],
        if (permissions.contains('approvals.decide')) ...[
          'proposal.approve',
          'proposal.reject',
          'escalation.authorize',
        ],
        if (permissions.contains('ops.view')) 'audit.read',
      ],
    };
  }

  Json _shift(Json row) {
    final j = J(row, 'Shift');
    if (j.intN('consults_this_shift') == null ||
        j.intN('calls_this_shift') == null) {
      throw const Unavailable('Shift counters require loaded reference data.');
    }
    return {
      ...row,
      'consults_today': j.integer('consults_this_shift'),
      'calls_today': j.integer('calls_this_shift'),
      'hospitals_count': j.strings('hospitals').length,
      'consults': [
        for (final c in _items(row, 'consults'))
          {
            ...c,
            'status_text': '${c['stage']} · ${c['minutes_in_stage']} min',
            'level': switch (c['level']) {
              'Critical' => 'critical',
              'Warning' => 'warning',
              'none' || null => 'ok',
              final level => throw ParseError('Unknown consult level: $level'),
            },
          },
      ],
      'update': null,
      'next_shift': null,
    };
  }

  Json _candidates(Json row) {
    final labels = {for (final r in _items(row, 'rules')) r['id']: r['label']};
    return {
      'gap_id': J(row, 'Candidates').obj('gap').str('gap_id'),
      'evaluated_at': _now(row),
      'server_now': _now(row),
      'candidates': [
        for (final c in _items(row, 'candidates'))
          {
            ...c,
            'display_name': c['name'],
            'rules': [
              for (final r in _items(c, 'results'))
                {
                  'rule': r['rule'],
                  'name': labels[r['rule']],
                  'passed': switch (r['status']) {
                    'pass' => true,
                    'fail' => false,
                    final status => throw ParseError(
                      'Unknown rule result: $status',
                    ),
                  },
                  'detail': r['explanation'],
                },
            ],
          },
      ],
    };
  }

  Json _trap(Json row) {
    if (row['seed_consults'] == null ||
        (row['unknown_demand'] is List &&
            (row['unknown_demand'] as List).isNotEmpty)) {
      throw Unavailable(J(row, 'Trap').strings('reasons').join('; '));
    }
    return {
      ...row,
      'result': row['passed'] == true ? 'pass' : 'fail',
      'explanation': J(row, 'Trap').strings('reasons').join('; '),
      'joiner_projected_consults': row['joiner_load'],
      'busiest_peer_projected_consults': row['busiest_peer_load'],
    };
  }

  Json _summary(Json row) => {
    ...row,
    'proposal_id': row['offer_id'],
    'hospitals': _hospitals(row),
    'recipient_count': 1,
  };
  Json _escalation(Json row) => {
    'escalation_id': row['intervention_id'] ?? row['id'],
    'hospital_name': 'Coverage escalation',
    'reason': row['reason'] ?? '',
    'proposed_intervention': row['reason'] ?? 'Escalation requested',
    'status': switch (row['state']) {
      'REQUESTED' => 'pending',
      'AUTHORIZED' => 'authorized',
      final state => throw ParseError('Unknown escalation state: $state'),
    },
    'created_at': row['created_at'],
    'authorized_by': row['authorized_by'],
    'authorized_at': row['authorized_at'],
  };

  Future<Json> _proposal(String path) async {
    final row = await _read(path.replaceFirst('/proposals/', '/offers/'));
    final gapId = Uri.encodeComponent(J(row, 'Offer').str('gap_id'));
    final candidates = await _read('/gaps/$gapId/candidates');
    final trap = await _read('/gaps/$gapId/trap-check');
    final gap = J(candidates, 'Candidates').obj('gap');
    final required = gap.intN('required');
    final counted = required == null ? null : gap.intN('count');
    final selected = _items(
      candidates,
      'candidates',
    ).where((c) => c['physician_id'] == row['physician_id']).firstOrNull;
    final proposal = {
      ...row,
      'proposal_id': row['offer_id'],
      'status': _proposalStatus(row),
      'gap': {
        ...gap.m,
        'hospitals': _hospitals(row),
        'start': row['start'],
        'end': row['end'],
        'hours': _hours(row),
        'counted': counted,
        'shortfall': required != null && counted != null
            ? required - counted
            : null,
      },
      'recipients': [
        {
          'physician_id': row['physician_id'],
          'display_name': row['physician_name'],
          'rank': selected?['rank'],
          'rank_reason':
              selected?['rank_reason'] ??
              selected?['primary_reason'] ??
              'Selected by the coordinator; rechecked by the server at approval.',
        },
      ],
      'excluded': [
        for (final c in _items(
          candidates,
          'candidates',
        ).where((c) => c['eligible'] == false))
          {
            'physician_id': c['physician_id'],
            'display_name': c['name'],
            'failed_rule':
                _items(
                  c,
                  'results',
                ).where((r) => r['status'] == 'fail').firstOrNull?['rule'] ??
                'Low value',
            'detail': c['primary_reason'] ?? '',
          },
      ],
      'trap_check': {
        'result': trap['passed'] == true ? 'pass' : 'fail',
        'explanation': J(trap, 'Trap').strings('reasons').join('; '),
      },
      'coverage_preview': {
        'times': trap['steps'],
        'without': [for (final c in _items(trap, 'without')) _staffing(c)],
        'with': [for (final c in _items(trap, 'with')) _staffing(c)],
      },
      'decided_by': row['approved_by'],
      'decided_at': row['approved_at'],
      'decision_reason': row['reason'],
    };
    _proposals[path] = proposal;
    return proposal;
  }

  Json _staffing(Json cell) {
    if (cell['required'] == null) {
      throw const Unavailable(
        'Required coverage is unknown; no staffing estimate is displayed.',
      );
    }
    return {'staffed': cell['count'], 'required': cell['required']};
  }

  Json _coverage(Json snapshot) {
    final coverage = J(snapshot, 'Snapshot').obj('coverage');
    if (!coverage.boolean('supported')) {
      throw const Unavailable('Coverage requires loaded reference data.');
    }
    final steps = coverage.times('steps');
    return {
      'server_now': J(snapshot, 'Snapshot').obj('clock').str('now'),
      'columns': [
        for (var i = 0; i < steps.length; i++)
          {
            'at': steps[i].toIso8601String(),
            'label': i == 0 ? 'Now' : '+${i * 15} min',
          },
      ],
      'hospitals': [
        for (final h in _items(coverage.m, 'hospitals'))
          {
            'hospital_id': h['hospital_id'],
            'name': h['hospital_name'],
            'status_text': J(
              h,
              'Hospital',
            ).list('cells', (j) => j.str('status')).first,
            'level': switch (_items(h, 'cells').first['status']) {
              'gap' => 'short',
              'at_minimum' =>
                h['nobody_reachable_now'] == true
                    ? 'no_one_free'
                    : 'at_minimum',
              'above_minimum' =>
                h['nobody_reachable_now'] == true ? 'no_one_free' : 'covered',
              final status => throw Unavailable(
                'Coverage status is $status; no estimate is displayed.',
              ),
            },
            'cells': [for (final c in _items(h, 'cells')) _staffing(c)],
          },
      ],
      'footnotes': [
        {'marker': '*', 'text': coverage.str('assumption')},
      ],
    };
  }

  @override
  Future<T> get<T>(
    String path,
    T Function(Object?) parse, {
    Map<String, String>? query,
  }) async {
    final Json adapted;
    if (path == '/me') {
      adapted = _me(await _read(path));
    } else if (path == '/me/shift') {
      adapted = _shift(await _read(path));
    } else if (path == '/offers' || path == '/notifications') {
      final rows = await _read('/me/offers');
      final offers = _items(rows);
      if (path == '/offers') {
        adapted = {
          'offers': [for (final o in offers) _offer(o)],
          'server_now': rows['now'],
        };
      } else {
        // Offer activity derived from sent records; "unread" means actionable,
        // not a server-side read receipt (the backend has no read-state store).
        adapted = {
          'server_now': rows['now'],
          'items': [
            for (final o in offers)
              {
                'notification_id': 'offer:${o['offer_id']}',
                'kind': 'offer',
                'title': 'Coverage offer',
                'body': o['message'] ?? o['reason'] ?? '',
                'at': o['sent_at'],
                'offer_id': o['offer_id'],
                'unread': o['state'] == 'Sent',
              },
          ],
        };
      }
    } else if (path.startsWith('/offers/')) {
      adapted = _offer(await _read(path));
    } else if (path == '/lead/queue') {
      final offers = await _read('/offers');
      final interventions = await _read(
        '/interventions',
        query: {'state': 'pending'},
      );
      final proposals = _items(
        offers,
      ).where((o) => o['state'] == 'Proposed').toList();
      adapted = {
        'server_now': _now(interventions),
        'pending_count': proposals.length + _items(interventions).length,
        'proposals': [for (final o in proposals) _summary(o)],
        'escalations': [for (final e in _items(interventions)) _escalation(e)],
        'automated_actions': <Json>[],
      };
    } else if (path.startsWith('/proposals/')) {
      adapted = await _proposal(path);
    } else if (path.endsWith('/candidates')) {
      adapted = _candidates(await _read(path));
    } else if (path.endsWith('/trap-check')) {
      adapted = _trap(await _read(path));
    } else if (path.startsWith('/gaps/') && path.endsWith('/audit')) {
      final gapId = Uri.decodeComponent(path.substring(6, path.length - 6));
      final audit = await _read('/audit', query: {'gap_id': gapId});
      adapted = {
        'gap_id': gapId,
        'entries': audit['items'],
        'server_now': _now(audit),
      };
    } else if (path == '/lead/coverage') {
      final snapshot = await _read('/snapshot');
      final c = J(snapshot, 'Snapshot').obj('clock');
      clock.observe(c.time('now'), fixed: c.str('mode') == 'fixed');
      adapted = _coverage(snapshot);
    } else if (path == '/lead/offers') {
      final rows = await _read('/offers');
      final me = await _read('/me');
      adapted = {
        'server_now': _now(me),
        'broadcasts': [
          for (final o in _items(rows).where((o) => o['sent_at'] != null))
            {
              'proposal_id': o['offer_id'],
              'gap_id': o['gap_id'],
              'hospitals': _hospitals(o),
              'start': o['start'],
              'end': o['end'],
              'status': o['state'] == 'Sent'
                  ? 'open'
                  : o['state'] == 'Accepted'
                  ? 'filled'
                  : 'unfilled',
              'filled_by': o['state'] == 'Accepted'
                  ? {
                      'physician_id': o['physician_id'],
                      'display_name': o['physician_name'],
                    }
                  : null,
              'offers': [
                {
                  ..._offer(o),
                  'physician_id': o['physician_id'],
                  'display_name': o['physician_name'],
                },
              ],
            },
        ],
      };
    } else if (path == '/me/schedule' || path == '/lead/schedule') {
      throw const UnsupportedFeature(
        'Schedule views are not available from this backend.',
      );
    } else {
      return super.get(path, parse, query: query);
    }
    return parse(adapted);
  }

  @override
  Future<T> post<T>(
    String path,
    T Function(Object?) parse, {
    Object? body,
    bool signOutOn401 = true,
    String? idempotencyKey,
  }) async {
    if (path.endsWith('/release')) {
      throw const UnsupportedFeature(
        'Offer release is not available from this backend.',
      );
    }
    if (path.startsWith('/offers/') &&
        (path.endsWith('/accept') || path.endsWith('/decline'))) {
      final command = path.split('/').last;
      Json row;
      var applied = true;
      try {
        row = await super.post(
          path,
          (raw) => J(raw, path).m,
          idempotencyKey: 'mobile:$path',
        );
      } on Conflict {
        row = await _read(path.substring(0, path.lastIndexOf('/')));
        if (row['state'] == 'Sent') rethrow;
        applied = false;
      }
      final outcome = switch (row['state']) {
        'Accepted' => command == 'accept' ? 'accepted' : 'not_open',
        'Declined' => command == 'decline' ? 'declined' : 'not_open',
        'Already filled' => 'already_filled',
        'Expired' => 'expired',
        _ => 'not_open',
      };
      return parse({
        'outcome': outcome,
        'applied':
            applied &&
            outcome == (command == 'accept' ? 'accepted' : 'declined'),
        'offer': _offer(row),
        'server_now': _now(row),
      });
    }
    if (path.startsWith('/proposals/')) {
      final proposalPath = path.substring(0, path.lastIndexOf('/'));
      final before = _proposals[proposalPath] ?? await _proposal(proposalPath);
      final nativePath = path.replaceFirst('/proposals/', '/offers/');
      Json row;
      var applied = true;
      try {
        row = await super.post(
          nativePath,
          (raw) => J(raw, path).m,
          body: body,
          idempotencyKey: 'mobile:$path',
        );
      } on Conflict {
        row = await _read(nativePath.substring(0, nativePath.lastIndexOf('/')));
        if (row['state'] == 'Proposed') rethrow;
        applied = false;
      }
      final status = _proposalStatus(row);
      final proposal = {
        ...before,
        ...row,
        'status': status,
        'decided_by': row['approved_by'],
        'decided_at': row['approved_at'],
        'decision_reason': row['reason'],
      };
      _proposals[proposalPath] = proposal;
      return parse({
        'outcome': applied ? status : 'already_decided',
        'applied': applied,
        'proposal': proposal,
        'offers': row['state'] == 'Sent'
            ? [
                {
                  'offer_id': row['offer_id'],
                  'physician_id': row['physician_id'],
                  'status': 'sent',
                },
              ]
            : <Json>[],
        'skipped': <Json>[],
        'server_now': _now(row),
      });
    }
    if (path.startsWith('/escalations/')) {
      final id = path.split('/')[2];
      Json row;
      var applied = true;
      try {
        row = await super.post(
          '/interventions/$id/authorize',
          (raw) => J(raw, path).m,
        );
      } on Conflict {
        final rows = await _read('/interventions');
        row = _items(rows).firstWhere((e) => e['intervention_id'] == id);
        if (row['state'] != 'AUTHORIZED') rethrow;
        applied = false;
      }
      final me = await _read('/me');
      return parse({
        'outcome': applied ? 'authorized' : 'already_authorized',
        'applied': applied,
        'escalation': _escalation(row),
        'server_now': _now(me),
      });
    }
    return super.post(
      path,
      parse,
      body: body,
      signOutOn401: signOutOn401,
      idempotencyKey: idempotencyKey,
    );
  }

  @override
  Future<T> put<T>(String path, T Function(Object?) parse, {Object? body}) {
    if (path == '/me/preferences') {
      throw const UnsupportedFeature(
        'Preference updates are not available from this backend.',
      );
    }
    return super.put(path, parse, body: body);
  }
}
