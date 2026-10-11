import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import 'data/config.dart';
import 'screens/backend_auth_gate.dart';
import 'screens/theme.dart';
import 'screens/web_mirror.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SevaroApp());
}

class SevaroApp extends StatefulWidget {
  const SevaroApp({super.key, this.home});

  final Widget? home;

  @override
  State<SevaroApp> createState() => _SevaroAppState();
}

class _SevaroAppState extends State<SevaroApp> {
  late final SemanticsHandle _semantics;

  @override
  void initState() {
    super.initState();
    _semantics = SemanticsBinding.instance.ensureSemantics();
  }

  @override
  void dispose() {
    _semantics.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Cerevia Command Center',
    debugShowCheckedModeBanner: false,
    theme: sevaroTheme(),
    builder: (context, child) =>
        ColoredBox(color: OverlapStyle.background, child: child),
    // Dummy mode mirrors the web demo (landing → sign in → role dashboard).
    home:
        widget.home ??
        (AppConfig.apiMode == 'live'
            ? const BackendAuthGate()
            : const WebMirror()),
  );
}
