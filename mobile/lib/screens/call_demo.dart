import 'package:flutter/material.dart';

import '../data/api.dart';
import '../data/fake/fakes.dart';
import 'service_session.dart';
import 'shared.dart';

/// Dummy mode: opens the physician app on the fake backend, where the sample
/// `sent` offer rings as a coverage call. Call from a tap so sound is allowed.
void openCallDemo(BuildContext context) {
  final fake = FakeServices(autoAnswer: false);
  fake.services.alerts.enableSound();
  Navigator.of(
    context,
  ).push(MaterialPageRoute<void>(builder: (_) => _CallDemo(fake: fake)));
}

class _CallDemo extends StatefulWidget {
  const _CallDemo({required this.fake});
  final FakeServices fake;
  @override
  State<_CallDemo> createState() => _CallDemoState();
}

class _CallDemoState extends State<_CallDemo> {
  Me? _me;

  @override
  void initState() {
    super.initState();
    widget.fake.signInAs('okafor').then((me) {
      if (mounted) setState(() => _me = me);
    });
  }

  @override
  void dispose() {
    widget.fake.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final me = _me;
    if (me == null) return const LoadingScreen();
    return ServiceSession(
      services: widget.fake.services,
      me: me,
      onEnded: () => Navigator.of(context).pop(),
    );
  }
}
