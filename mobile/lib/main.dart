import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import 'screens/preview/preview_menu.dart';
import 'screens/sign_in_screen.dart';
import 'screens/theme.dart';

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
          builder: (context) => SignInScreen(
            onPreview:
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
                : null,
          ),
        ),
  );
}
