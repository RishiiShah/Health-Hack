import 'package:flutter/material.dart';

/// Shared visual tokens from origin/anish's Overlap web UI.
abstract final class OverlapStyle {
  static const background = Color(0xFFFBF9F5);
  static const ink = Color(0xFF161E2E);
  static const muted = Color(0xFF64748B);
  static const line = Color(0xFFE2DFD8);
  static const teal = Color(0xFF0D9488);
  static const tealDark = Color(0xFF0F766E);
  static const tealSoft = Color(0xFFD9F7EF);
  static const red = Color(0xFFB42318);
  static const redSoft = Color(0xFFFEE2E2);
  static const amber = Color(0xFF8A5A00);
  static const amberSoft = Color(0xFFF8E9C9);
  static const green = Color(0xFF2F6B4F);
  static const greenSoft = Color(0xFFD9F3E4);
  static const mono = 'IBM Plex Mono';
  static const heading = 'Bricolage Grotesque';

  static BoxDecoration panel({
    Color color = Colors.white,
    double radius = 16,
  }) => BoxDecoration(
    color: color,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: line),
    boxShadow: const [
      BoxShadow(color: Color(0x0A1E2530), blurRadius: 12, offset: Offset(0, 3)),
    ],
  );
}

ThemeData sevaroTheme() {
  const colors = ColorScheme.light(
    primary: OverlapStyle.teal,
    onPrimary: Colors.white,
    primaryContainer: OverlapStyle.tealSoft,
    onPrimaryContainer: OverlapStyle.tealDark,
    secondary: OverlapStyle.ink,
    onSecondary: Colors.white,
    secondaryContainer: OverlapStyle.tealSoft,
    onSecondaryContainer: OverlapStyle.tealDark,
    surface: Colors.white,
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
    borderRadius: BorderRadius.all(Radius.circular(12)),
    borderSide: BorderSide(color: OverlapStyle.line),
  );
  final buttonShape = RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(12),
  );
  return base.copyWith(
    scaffoldBackgroundColor: OverlapStyle.background,
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
        borderRadius: BorderRadius.all(Radius.circular(12)),
        borderSide: BorderSide(color: OverlapStyle.teal, width: 2),
      ),
      filled: true,
      fillColor: Colors.white,
      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: OverlapStyle.tealDark,
        foregroundColor: Colors.white,
        minimumSize: const Size(48, 48),
        shape: buttonShape,
        textStyle: const TextStyle(
          fontFamily: 'IBM Plex Sans',
          fontWeight: FontWeight.w600,
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
      backgroundColor: Colors.white,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
    ),
    bottomSheetTheme: const BottomSheetThemeData(backgroundColor: Colors.white),
  );
}
