import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_tokens.dart';

class AppTheme {
  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: AppTokens.bgNavy900,
      colorScheme: const ColorScheme.light(
        primary: AppTokens.primary,
        surface: AppTokens.surface,
        error: AppTokens.danger,
      ),
    );
    final text = GoogleFonts.interTextTheme(base.textTheme).apply(
      bodyColor: AppTokens.textPrimary,
      displayColor: AppTokens.textPrimary,
    );
    return base.copyWith(
      textTheme: text.copyWith(
        displaySmall: text.displaySmall?.copyWith(fontSize: 28, fontWeight: FontWeight.w800, height: 1.05),
        headlineSmall: text.headlineSmall?.copyWith(fontSize: 22, fontWeight: FontWeight.w700),
        titleLarge: text.titleLarge?.copyWith(fontSize: 18, fontWeight: FontWeight.w700),
        titleMedium: text.titleMedium?.copyWith(fontSize: 15, fontWeight: FontWeight.w700),
        bodyMedium: text.bodyMedium?.copyWith(fontSize: 13, fontWeight: FontWeight.w400, color: AppTokens.textMuted),
        labelSmall: text.labelSmall?.copyWith(fontSize: 11, fontWeight: FontWeight.w500),
      ),
    );
  }

  static TextStyle overline({Color color = AppTokens.accentGold}) {
    return GoogleFonts.inter(
      fontSize: 10,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.8,
      color: color,
    );
  }
}
