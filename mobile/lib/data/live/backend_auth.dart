import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../clock.dart';
import '../json.dart';
import '../platform/browser.dart';
import '../api.dart';
import '../feeds.dart';
import '../../web_alerts.dart';
import 'client.dart';
import 'backend_client.dart';
import 'live.dart';

/// Account identity supplied by the implemented web-joy auth API. This is
/// deliberately separate from Me, whose workflow metadata is not supplied yet.
class BackendUser {
  const BackendUser({
    required this.email,
    required this.name,
    required this.role,
    required this.roleLabel,
    required this.physicianId,
  });
  final String email;
  final String name;
  final String role;
  final String roleLabel;
  final String? physicianId;

  static BackendUser parse(Object? raw) {
    final j = J(raw, 'User');
    final role = j.str('role');
    if (!['coordinator', 'lead', 'physician'].contains(role)) {
      throw ParseError('User.role: unknown value "$role"');
    }
    if (!j.m.containsKey('physician_id')) {
      throw const ParseError('User.physician_id: required field missing');
    }
    final id = j.strN('physician_id');
    if ((role == 'physician') != (id != null && id.isNotEmpty) ||
        (role != 'physician' && id != null)) {
      throw const ParseError('User.physician_id: incompatible with role');
    }
    final email = j.str('email');
    final name = j.str('name');
    if (email.trim().isEmpty || name.trim().isEmpty) {
      throw const ParseError('User: email and name must not be blank');
    }
    return BackendUser(
      email: email,
      name: name,
      role: role,
      roleLabel: j.str('role_label'),
      physicianId: id,
    );
  }
}

class BackendAuthRepository {
  factory BackendAuthRepository(
    Uri baseUrl, {
    Browser? browser,
    http.Client? httpClient,
  }) {
    if (!['http', 'https'].contains(baseUrl.scheme) || baseUrl.host.isEmpty) {
      throw ArgumentError('API_BASE_URL must be an http or https URL');
    }
    final tokens = SessionTokenStore(browser ?? sharedBrowser);
    final clock = OffsetServerClock();
    late final BackendAuthRepository repository;
    final client = BackendApiClient(
      baseUrl: baseUrl,
      tokens: tokens,
      clock: clock,
      httpClient: httpClient,
      onUnauthorized: () => repository._invalidate(),
    );
    repository = BackendAuthRepository._(client, tokens, clock);
    return repository;
  }
  BackendAuthRepository._(this._client, this._tokens, this._clock);
  final BackendApiClient _client;
  final TokenStore _tokens;
  final OffsetServerClock _clock;
  final _user = ValueNotifier<BackendUser?>(null);
  final _signedOut = StreamController<void>.broadcast();
  int _revision = 0;
  bool _disposed = false;
  AppServices? _services;
  _BackendWorkflowAuth? _workflowAuth;

  AppServices get services {
    if (_services != null) return _services!;
    final auth = _workflowAuth = _BackendWorkflowAuth(this, _client);
    final offers = LiveOfferRepository(_client);
    final lead = LiveLeadRepository(_client);
    return _services = AppServices(
      auth: auth,
      offers: offers,
      shifts: LiveShiftRepository(_client),
      lead: lead,
      physicianFeed: PollingPhysicianFeed(offers),
      leadFeed: PollingLeadFeed(lead),
      clock: _clock,
      alerts: createWebAlerts(),
      isFake: false,
    );
  }

  Me get workflowIdentity => _BackendWorkflowAuth.identity(_user.value!);
  ValueListenable<BackendUser?> get user => _user;
  Stream<void> get signedOut => _signedOut.stream;

  Future<BackendUser?> currentUser() async {
    final token = _tokens.read();
    if (token == null) return null;
    final revision = _revision;
    try {
      final identity = await _client.get('/auth/me', (raw) {
        return BackendUser.parse(J(raw, 'AuthMe').obj('user').m);
      });
      if (!_disposed && revision == _revision && token == _tokens.read()) {
        _user.value = identity;
        return identity;
      }
      return _user.value;
    } on Unauthorized {
      return _disposed ? null : _user.value;
    }
  }

  Future<BackendUser> signIn(String email, String password) async {
    final revision = ++_revision;
    final result = await _client.post(
      '/auth/login',
      (raw) {
        final j = J(raw, 'AuthLogin');
        final token = j.str('token');
        final expires = j.integer('expires_at');
        if (token.isEmpty || expires <= 0) {
          throw const ParseError('AuthLogin: invalid token or expiry');
        }
        return (token, BackendUser.parse(j.obj('user').m));
      },
      body: {'email': email, 'password': password},
      signOutOn401: false,
    );
    if (_disposed || revision != _revision) {
      throw const Unauthorized('Sign-in was cancelled. Please try again.');
    }
    _tokens.write(result.$1);
    _client.clearWorkflowCache();
    _user.value = result.$2;
    return result.$2;
  }

  void _invalidate() {
    if (_disposed) return;
    _revision++;
    _client.clearWorkflowCache();
    _user.value = null;
    _signedOut.add(null);
  }

  void signOut() {
    _tokens.clear();
    _invalidate();
  }

  void dispose() {
    if (_disposed) return;
    _disposed = true;
    _revision++;
    _services?.physicianFeed.stop();
    _services?.leadFeed.stop();
    _workflowAuth?.dispose();
    _client.close();
    _clock.dispose();
    _user.dispose();
    _signedOut.close();
  }
}

/// Bridges account auth and the implemented backend workflow metadata.
class _BackendWorkflowAuth implements AuthRepository {
  _BackendWorkflowAuth(this.owner, this.client) {
    owner.user.addListener(_identityChanged);
    _identityChanged();
  }
  final BackendAuthRepository owner;
  final ApiClient client;
  final _me = ValueNotifier<Me?>(null);

  static Me identity(BackendUser user) => Me(
    userId: user.email,
    role: switch (user.role) {
      'physician' => Role.physician,
      'lead' => Role.clinicalLead,
      _ => Role.coordinator,
    },
    displayName: user.name,
    physicianId: user.physicianId,
    permissions: const [],
    splitShiftOptIn: null,
    offersReceived7d: null,
    weeklyOfferLimit: null,
    onShift: null,
    shiftEnd: null,
    // This identity placeholder is never observed by the server clock.
    serverNow: DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
  );

  void _identityChanged() {
    final user = owner.user.value;
    final current = _me.value;
    if (user == null) {
      _me.value = null;
    } else if (current == null ||
        current.userId != user.email ||
        current.role != identity(user).role ||
        current.physicianId != user.physicianId ||
        current.displayName != user.name) {
      _me.value = identity(user);
    }
  }

  Me _validate(Me me) {
    final user = owner.user.value;
    if (user == null) throw const Unauthorized('Please sign in again.');
    if (me.role != identity(user).role || me.physicianId != user.physicianId) {
      throw const Forbidden('Workflow identity does not match your account.');
    }
    return me;
  }

  @override
  Future<Me> refreshMe() async {
    final account = owner.user.value;
    if (account == null) throw const Unauthorized('Please sign in again.');
    try {
      final result = await client.get('/me', Me.parse);
      if (owner.user.value?.email != account.email ||
          owner.user.value?.role != account.role ||
          owner.user.value?.physicianId != account.physicianId) {
        throw const Unauthorized('Account changed. Please try again.');
      }
      _me.value = _validate(result);
    } on NotFound {
      // Older auth-only deployments keep workflow metadata unknown.
    }
    if (owner.user.value == null) {
      throw const Unauthorized('Please sign in again.');
    }
    return _me.value ?? identity(account);
  }

  @override
  Future<Me?> currentUser() async =>
      await owner.currentUser() == null ? null : refreshMe();
  @override
  Future<Me> signIn(String email, String password) async =>
      identity(await owner.signIn(email, password));
  @override
  Future<void> signOut() async => owner.signOut();
  @override
  Future<PreferencesResult> setOptIn(
    bool optIn, {
    bool declineOpenOffer = false,
  }) async {
    final result = await client.put(
      '/me/preferences',
      PreferencesResult.parse,
      body: {
        'split_shift_opt_in': optIn,
        'decline_open_offer': declineOpenOffer,
      },
    );
    _me.value = _validate(result.me);
    return result;
  }

  @override
  String? takeInitialOfferId() => null;
  @override
  Stream<void> get signedOut => owner.signedOut;
  @override
  ValueListenable<Me?> get me => _me;
  void dispose() {
    owner.user.removeListener(_identityChanged);
    _me.dispose();
  }
}
