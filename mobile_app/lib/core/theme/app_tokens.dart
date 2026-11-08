import 'package:flutter/material.dart';

/// Design tokens from PRD section 7. Widgets must use these instead of raw colors.
class AppTokens {
  static const bgNavy900 = Color(0xFF071A4A);
  static const bgNavy700 = Color(0xFF0B2C78);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceMuted = Color(0xFFF3F6FC);
  static const primary = Color(0xFF2F6BFF);
  static const primaryCyan = Color(0xFF4FC3F7);
  static const accentGold = Color(0xFFF5B942);
  static const textOnDark = Color(0xFFFFFFFF);
  static const textOnDarkMuted = Color(0xFFA9B8DC);
  static const textPrimary = Color(0xFF0B1B45);
  static const textMuted = Color(0xFF6B7A99);
  static const success = Color(0xFF22A06B);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFE5484D);
  static const border = Color(0xFFE3E8F4);

  static const screenPadding = 20.0;
  static const radiusCard = 20.0;
  static const radiusInput = 14.0;
  static const radiusButton = 14.0;
  static const radiusSheet = 28.0;

  static const buttonGradient = LinearGradient(colors: [primary, primaryCyan]);
  static const screenGradient = LinearGradient(
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
    colors: [bgNavy900, bgNavy700],
  );
  static const cardShadow = [
    BoxShadow(color: Color(0x1F071A4A), blurRadius: 24, offset: Offset(0, 8)),
  ];
}
