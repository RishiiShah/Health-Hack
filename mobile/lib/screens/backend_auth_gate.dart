import 'dart:async';

import 'package:flutter/material.dart';

import '../data/api.dart' show ApiException, Poller, Unauthorized;
import '../data/config.dart';
import '../data/live/backend_auth.dart';
import 'data_widgets.dart';
import 'shared.dart';
import 'sign_in_screen.dart';
import 'service_session.dart';
import 'account_page.dart';

class BackendAuthGate extends StatefulWidget {
  const BackendAuthGate({super.key, this.repository});
  final BackendAuthRepository? repository;
  @override
  State<BackendAuthGate> createState() => _BackendAuthGateState();
}

class _BackendAuthGateState extends State<BackendAuthGate>
    with WidgetsBindingObserver {
  late final BackendAuthRepository _auth;
  late final Poller _poller;
  StreamSubscription<void>? _signedOut;
  BackendUser? _user;
  bool _restoring = true;
  bool _checking = false;
  String? _error;
  String? _notice;
  int _revision = 0;

  @override
  void initState() {
    super.initState();
    _auth =
        widget.repository ??
        BackendAuthRepository(Uri.parse(AppConfig.apiBaseUrl));
    WidgetsBinding.instance.addObserver(this);
    _signedOut = _auth.signedOut.listen((_) {
      if (!mounted) return;
      _revision++;
      _poller.stop();
      setState(() {
        _user = null;
        _restoring = false;
        _notice = 'Please sign in again.';
        _error = null;
      });
    });
    _poller = Poller(const Duration(seconds: 60), () => _validate());
    _restore();
  }

  Future<void> _restore() async {
    final revision = ++_revision;
    setState(() {
      _restoring = true;
      _error = null;
    });
    try {
      final user = await _auth.currentUser();
      if (!mounted || revision != _revision) return;
      setState(() => _user = user);
      if (user != null) _poller.start();
    } catch (error) {
      if (mounted && revision == _revision) {
        setState(() => _error = errorText(error));
      }
    } finally {
      if (mounted && revision == _revision) setState(() => _restoring = false);
    }
  }

  Future<String?> _signIn(String email, String password) async {
    final revision = ++_revision;
    try {
      final user = await _auth.signIn(email, password);
      if (!mounted || revision != _revision) return null;
      setState(() {
        _user = user;
        _error = null;
        _notice = null;
      });
      _poller.start();
      return null;
    } on ApiException catch (error) {
      return error is Unauthorized ? error.message : errorText(error);
    } catch (error) {
      return errorText(error);
    }
  }

  Future<void> _validate() async {
    if (_user == null || _checking) return;
    final revision = _revision;
    setState(() => _checking = true);
    try {
      final user = await _auth.currentUser();
      if (mounted && revision == _revision) {
        setState(() {
          _user = user;
          _error = null;
        });
      }
    } catch (error) {
      if (mounted && revision == _revision) {
        setState(() => _error = errorText(error));
      }
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      if (_user != null) _poller.start();
    } else {
      _poller.stop();
    }
  }

  @override
  void dispose() {
    _revision++;
    WidgetsBinding.instance.removeObserver(this);
    _signedOut?.cancel();
    _poller.stop();
    if (widget.repository == null) _auth.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_restoring) {
      return const Scaffold(
        body: Center(
          child: CircularProgressIndicator(semanticsLabel: 'Checking sign-in'),
        ),
      );
    }
    final user = _user;
    if (user == null && _error != null) {
      return Scaffold(
        body: ScreenBody(
          children: [
            Notice(_error!, isError: true),
            FilledButton(
              onPressed: _restore,
              child: const Text('Retry session'),
            ),
            TextButton(
              onPressed: () {
                _auth.signOut();
                setState(() => _error = null);
              },
              child: const Text('Sign in with another account'),
            ),
          ],
        ),
      );
    }
    if (user == null) {
      return SignInScreen(
        onSignIn: _signIn,
        showDemoAccounts: false,
        showRoleSelection: false,
        notice: _notice,
      );
    }
    return ServiceSession(
      key: ValueKey('${user.email}:${user.role}'),
      services: _auth.services,
      me: _auth.workflowIdentity,
      actions: [
        IconButton(
          tooltip: 'Sign out',
          onPressed: _auth.signOut,
          icon: const Icon(Icons.logout),
        ),
      ],
      accountBuilder: (_) => _account(user),
    );
  }

  Widget _account(BackendUser user) => Scaffold(
    appBar: AppBar(
      title: Text(switch (user.role) {
        'physician' => 'Physician account',
        'lead' => 'Clinical lead account',
        _ => 'Operations account',
      }),
    ),
    body: AccountPage(
      services: _auth.services,
      me: _auth.services.auth.me.value ?? _auth.workflowIdentity,
      extraChildren: [
        const Notice('Signed in to the backend'),
        Text(user.email),
        if (user.physicianId != null) Text('Physician ID: ${user.physicianId}'),
        const SizedBox(height: 24),
        const Text(
          'Dashboard tabs use the live API. Some data endpoints are not available on this server yet.',
        ),
        if (_error != null) Notice(_error!, isError: true),
        const SizedBox(height: 16),
        OutlinedButton(
          onPressed: _checking ? null : _validate,
          child: Text(_checking ? 'Checking session…' : 'Check session'),
        ),
      ],
    ),
  );
}
