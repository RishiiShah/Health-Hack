import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import 'screens/preview/preview_menu.dart';
import 'screens/demo_workspace.dart';
import 'screens/sign_in_screen.dart';
import 'screens/theme.dart';
import 'data/config.dart';
import 'screens/backend_auth_gate.dart';

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
    title: 'Sevaro Command Center',
    debugShowCheckedModeBanner: false,
    theme: sevaroTheme(),
    home:
        widget.home ??
        Builder(
          builder: (context) {
            final onDemo = kDebugMode
                ? () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const DemoWorkspace(),
                    ),
                  )
                : null;
            final onPreview =
                kDebugMode &&
                    const bool.fromEnvironment(
                      'SCREEN_PREVIEW',
                      defaultValue: true,
                    )
                ? () => Navigator.of(context).push(
                    MaterialPageRoute<void>(
                      builder: (_) => const PreviewMenu(),
                    ),
                  )
                : null;
            if (AppConfig.apiMode == 'live') {
              return const BackendAuthGate();
            }
            return SignInScreen(onDemo: onDemo, onPreview: onPreview);
          },
        ),
  );
}
