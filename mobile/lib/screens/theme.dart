import 'package:flutter/material.dart';

/// Cerevia tokens shared with web/src/styles/tokens.css.
abstract final class OverlapStyle {
  static const background = Color(0xFFEDF1F4);
  static const surface = Color(0xFFFBFCFD);
  static const surface2 = Color(0xFFF2F5F8);
  static const accent = Color(0xFFB8D8EB);
  static const text2 = Color(0xFF364658);
  static const lineStrong = Color(0xFFB4C1CD);
  static const ink = Color(0xFF0F1A27);
  static const muted = Color(0xFF586777);
  static const line = Color(0xFFD3DCE4);
  static const teal = Color(0xFF275A7B);
  static const tealDark = Color(0xFF275A7B);
  static const tealSoft = Color(0xFFDFEBF3);
  static const red = Color(0xFFB4372A);
  static const redSoft = Color(0xFFFBE9E6);
  static const amber = Color(0xFF855700);
  static const amberSoft = Color(0xFFFAF0DA);
  static const green = Color(0xFF22704E);
  static const greenSoft = Color(0xFFE1F1E8);
  static const mono = 'IBM Plex Mono';
  static const heading = 'Bricolage Grotesque';

  static BoxDecoration panel({Color color = surface, double radius = 10}) =>
      BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: line),
      );
}

ThemeData sevaroTheme() {
  const colors = ColorScheme.light(
    primary: OverlapStyle.tealDark,
    onPrimary: Colors.white,
    primaryContainer: OverlapStyle.tealSoft,
    onPrimaryContainer: OverlapStyle.tealDark,
    secondary: OverlapStyle.ink,
    onSecondary: Colors.white,
    secondaryContainer: OverlapStyle.tealSoft,
    onSecondaryContainer: OverlapStyle.tealDark,
    surface: OverlapStyle.surface,
    onSurface: OverlapStyle.ink,
    onSurfaceVariant: OverlapStyle.muted,
    outline: OverlapStyle.line,
    outlineVariant: OverlapStyle.line,
    error: OverlapStyle.red,
    errorContainer: OverlapStyle.redSoft,
    onErrorContainer: OverlapStyle.red,
  );
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: colors,
    fontFamily: 'IBM Plex Sans',
  );
  TextStyle head(TextStyle? style, double size, FontWeight weight) =>
      (style ?? const TextStyle()).copyWith(
        fontFamily: OverlapStyle.heading,
        fontSize: size,
        fontWeight: weight,
        letterSpacing: -0.4,
        color: OverlapStyle.ink,
      );
  const fieldBorder = OutlineInputBorder(
    borderRadius: BorderRadius.all(Radius.circular(6)),
    borderSide: BorderSide(color: OverlapStyle.line),
  );
  final buttonShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(6),
  );
  return base.copyWith(
    scaffoldBackgroundColor: Colors.transparent,
    textTheme: base.textTheme.copyWith(
      displaySmall: head(base.textTheme.displaySmall, 38, FontWeight.w800),
      headlineLarge: head(base.textTheme.headlineLarge, 32, FontWeight.w800),
      headlineMedium: head(base.textTheme.headlineMedium, 28, FontWeight.w700),
      headlineSmall: head(base.textTheme.headlineSmall, 23, FontWeight.w700),
      titleLarge: head(base.textTheme.titleLarge, 19, FontWeight.w700),
      titleMedium: head(base.textTheme.titleMedium, 16, FontWeight.w600),
      bodyLarge: base.textTheme.bodyLarge?.copyWith(fontSize: 15, height: 1.5),
      bodyMedium: base.textTheme.bodyMedium?.copyWith(
        fontSize: 14,
        height: 1.5,
      ),
      bodySmall: base.textTheme.bodySmall?.copyWith(color: OverlapStyle.muted),
    ),
    appBarTheme: const AppBarTheme(
      centerTitle: false,
      backgroundColor: OverlapStyle.background,
      foregroundColor: OverlapStyle.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      titleTextStyle: TextStyle(
        fontFamily: OverlapStyle.heading,
        fontSize: 23,
        fontWeight: FontWeight.w700,
        color: OverlapStyle.ink,
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: OverlapStyle.line,
      thickness: 1,
    ),
    inputDecorationTheme: const InputDecorationTheme(
      border: fieldBorder,
      enabledBorder: fieldBorder,
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.all(Radius.circular(6)),
        borderSide: BorderSide(color: OverlapStyle.teal, width: 2),
      ),
      filled: true,
      fillColor: OverlapStyle.surface,
      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: OverlapStyle.accent,
        foregroundColor: OverlapStyle.ink,
        side: const BorderSide(color: OverlapStyle.ink),
        minimumSize: const Size(48, 48),
        shape: buttonShape,
        textStyle: const TextStyle(
          fontFamily: OverlapStyle.mono,
          fontSize: 12,
          letterSpacing: 1.1,
          fontWeight: FontWeight.w500,
        ),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: OverlapStyle.ink,
        side: const BorderSide(color: OverlapStyle.line),
        minimumSize: const Size(48, 48),
        shape: buttonShape,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: OverlapStyle.tealDark,
        minimumSize: const Size(48, 48),
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: const Color(0xFFF8FAFC),
      selectedColor: OverlapStyle.tealSoft,
      side: const BorderSide(color: OverlapStyle.line),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      labelStyle: const TextStyle(
        fontFamily: 'IBM Plex Sans',
        color: OverlapStyle.ink,
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: OverlapStyle.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: OverlapStyle.surface,
    ),
  );
}
