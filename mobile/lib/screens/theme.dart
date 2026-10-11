import 'package:flutter/material.dart';

/// Cerevia tokens shared with web/src/styles/tokens.css: warm newsprint, black ink, one red for what is urgent.
abstract final class OverlapStyle {
  static const background = Color(0xFFECE7DC);
  static const surface = Color(0xFFFCFBF7);
  static const surface2 = Color(0xFFF5F2EA);
  static const accent = Color(0xFF1A1712);
  static const text2 = Color(0xFF3A352C);
  static const lineStrong = Color(0xFF1A1712);
  static const ink = Color(0xFF1A1712);
  static const muted = Color(0xFF6B6457);
  static const line = Color(0xFFCFC7B6);
  static const teal = Color(0xFFA93A24);
  static const tealDark = Color(0xFFA93A24);
  static const tealSoft = Color(0xFFF3E3DC);
  static const red = Color(0xFFA93A24);
  static const redSoft = Color(0xFFF6E2DB);
  static const amber = Color(0xFF7D5300);
  static const amberSoft = Color(0xFFF4EAD2);
  static const green = Color(0xFF2F6B45);
  static const greenSoft = Color(0xFFE2EEDF);
  static const mono = 'IBM Plex Mono';
  // Newsreader as on the web; Georgia and Noto Serif stand in until the font file is bundled.
  static const heading = 'Newsreader';
  static const body = 'Newsreader';
  static const serifFallback = ['Georgia', 'Noto Serif', 'serif'];

  /// A black frame on the newsprint with a hard offset shadow.
  static BoxDecoration panel({Color color = surface, double radius = 0}) =>
      BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(color: ink, width: 1.5),
        boxShadow: const [BoxShadow(color: ink, offset: Offset(4, 4))],
      );
}

ThemeData sevaroTheme() {
  const colors = ColorScheme.light(
    primary: OverlapStyle.ink,
    onPrimary: OverlapStyle.surface,
    primaryContainer: OverlapStyle.tealSoft,
    onPrimaryContainer: OverlapStyle.red,
    secondary: OverlapStyle.red,
    onSecondary: OverlapStyle.surface,
    secondaryContainer: OverlapStyle.tealSoft,
    onSecondaryContainer: OverlapStyle.red,
    surface: OverlapStyle.surface,
    onSurface: OverlapStyle.ink,
    onSurfaceVariant: OverlapStyle.muted,
    outline: OverlapStyle.ink,
    outlineVariant: OverlapStyle.line,
    error: OverlapStyle.red,
    errorContainer: OverlapStyle.redSoft,
    onErrorContainer: OverlapStyle.red,
  );
  final base = ThemeData(
    useMaterial3: true,
    colorScheme: colors,
    fontFamily: OverlapStyle.body,
    fontFamilyFallback: OverlapStyle.serifFallback,
  );
  TextStyle head(TextStyle? style, double size, FontWeight weight) =>
      (style ?? const TextStyle()).copyWith(
        fontFamily: OverlapStyle.heading,
        fontFamilyFallback: OverlapStyle.serifFallback,
        fontSize: size,
        fontWeight: weight,
        letterSpacing: -0.4,
        color: OverlapStyle.ink,
      );
  const label = TextStyle(
    fontFamily: OverlapStyle.mono,
    fontSize: 12,
    letterSpacing: 1.8,
    fontWeight: FontWeight.w500,
  );
  const square = RoundedRectangleBorder(borderRadius: BorderRadius.zero);
  const fieldBorder = OutlineInputBorder(
    borderRadius: BorderRadius.zero,
    borderSide: BorderSide(color: OverlapStyle.ink, width: 1.5),
  );
  return base.copyWith(
    scaffoldBackgroundColor: Colors.transparent,
    textTheme: base.textTheme.copyWith(
      displaySmall: head(base.textTheme.displaySmall, 38, FontWeight.w500),
      headlineLarge: head(base.textTheme.headlineLarge, 32, FontWeight.w500),
      headlineMedium: head(base.textTheme.headlineMedium, 28, FontWeight.w500),
      headlineSmall: head(base.textTheme.headlineSmall, 23, FontWeight.w500),
      titleLarge: head(base.textTheme.titleLarge, 19, FontWeight.w600),
      titleMedium: head(base.textTheme.titleMedium, 16, FontWeight.w600),
      bodyLarge: base.textTheme.bodyLarge?.copyWith(fontSize: 16, height: 1.5),
      bodyMedium: base.textTheme.bodyMedium?.copyWith(
        fontSize: 15,
        height: 1.5,
      ),
      bodySmall: base.textTheme.bodySmall?.copyWith(color: OverlapStyle.muted),
      labelLarge: label,
      labelMedium: label.copyWith(fontSize: 11),
      labelSmall: label.copyWith(fontSize: 10, color: OverlapStyle.muted),
    ),
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: OverlapStyle.red,
      selectionColor: OverlapStyle.redSoft,
      selectionHandleColor: OverlapStyle.red,
    ),
    appBarTheme: const AppBarTheme(
      centerTitle: false,
      backgroundColor: OverlapStyle.background,
      foregroundColor: OverlapStyle.ink,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: Border(bottom: BorderSide(color: OverlapStyle.ink, width: 1.5)),
      titleTextStyle: TextStyle(
        fontFamily: OverlapStyle.heading,
        fontFamilyFallback: OverlapStyle.serifFallback,
        fontSize: 23,
        fontWeight: FontWeight.w500,
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
        borderRadius: BorderRadius.zero,
        borderSide: BorderSide(color: OverlapStyle.ink, width: 2.5),
      ),
      filled: true,
      fillColor: OverlapStyle.surface,
      contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: OverlapStyle.ink,
        foregroundColor: OverlapStyle.surface,
        side: const BorderSide(color: OverlapStyle.ink, width: 1.5),
        minimumSize: const Size(48, 48),
        shape: square,
        textStyle: label,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: OverlapStyle.ink,
        backgroundColor: OverlapStyle.surface,
        side: const BorderSide(color: OverlapStyle.ink, width: 1.5),
        minimumSize: const Size(48, 48),
        shape: square,
        textStyle: label,
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: OverlapStyle.red,
        minimumSize: const Size(48, 48),
        shape: square,
        textStyle: label,
      ),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: OverlapStyle.surface,
      selectedColor: OverlapStyle.ink,
      secondarySelectedColor: OverlapStyle.ink,
      side: const BorderSide(color: OverlapStyle.ink),
      shape: square,
      labelStyle: label.copyWith(fontSize: 11, color: OverlapStyle.ink),
      secondaryLabelStyle: label.copyWith(fontSize: 11, color: OverlapStyle.surface),
    ),
    cardTheme: const CardThemeData(
      color: OverlapStyle.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.zero,
        side: BorderSide(color: OverlapStyle.ink, width: 1.5),
      ),
    ),
    dialogTheme: const DialogThemeData(
      backgroundColor: OverlapStyle.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.zero,
        side: BorderSide(color: OverlapStyle.ink, width: 1.5),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: OverlapStyle.surface,
      shape: Border(top: BorderSide(color: OverlapStyle.ink, width: 1.5)),
    ),
  );
}
