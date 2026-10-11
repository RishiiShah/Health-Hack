import 'package:flutter/material.dart';

import '../data/api.dart';
import 'data_widgets.dart';
import 'service_session.dart';
import 'sign_in_screen.dart';

/// Login owns the identity; dashboards depend only on repository interfaces.
class RepositoryAuthGate extends StatefulWidget {
  const RepositoryAuthGate({
    super.key,
    required this.services,
    this.onPreviewRoleChanged,
  });
  final AppServices services;
  final ValueChanged<bool>? onPreviewRoleChanged;

  @override
  State<RepositoryAuthGate> createState() => _RepositoryAuthGateState();
}

class _RepositoryAuthGateState extends State<RepositoryAuthGate> {
  Me? _me;

  Future<String?> _signIn(String email, String password) async {
    try {
      final me = await widget.services.auth.signIn(email, password);
      if (mounted) setState(() => _me = me);
      return null;
    } catch (error) {
      return error is Unauthorized ? error.message : errorText(error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final me = _me;
    if (me == null) {
      return SignInScreen(
        onSignIn: _signIn,
        showRoleSelection: widget.onPreviewRoleChanged != null,
        onPreviewRoleChanged: widget.onPreviewRoleChanged,
        showDemoAccounts: false,
        notice: widget.services.isFake
            ? 'Dummy data: use any email and password to compare the dashboards.'
            : null,
      );
    }
    return ServiceSession(
      key: ValueKey(me.userId),
      services: widget.services,
      me: me,
      onEnded: () {
        widget.onPreviewRoleChanged?.call(true);
        if (mounted) setState(() => _me = null);
      },
    );
  }
}
