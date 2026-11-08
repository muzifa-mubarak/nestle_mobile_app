import 'package:flutter/material.dart';

import '../../core/theme/app_theme.dart';
import '../../core/theme/app_tokens.dart';

class NavyBackground extends StatelessWidget {
  const NavyBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(gradient: AppTokens.screenGradient),
      child: child,
    );
  }
}

class AppBackButton extends StatelessWidget {
  const AppBackButton({super.key, this.onPressed});

  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white.withValues(alpha: 0.08),
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        onTap: onPressed ?? () => Navigator.of(context).maybePop(),
        borderRadius: BorderRadius.circular(14),
        child: const SizedBox(
          width: 40,
          height: 40,
          child: Icon(Icons.chevron_left, color: AppTokens.textOnDark),
        ),
      ),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.label,
    required this.onPressed,
    this.loading = false,
    this.icon,
    this.showArrow = true,
  });

  final String label;
  final VoidCallback? onPressed;
  final bool loading;
  final IconData? icon;
  final bool showArrow;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: onPressed == null ? null : AppTokens.buttonGradient,
        color: onPressed == null ? AppTokens.border : null,
        borderRadius: BorderRadius.circular(AppTokens.radiusButton),
      ),
      child: SizedBox(
        height: 52,
        width: double.infinity,
        child: TextButton(
          onPressed: loading ? null : onPressed,
          child: loading
              ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
              : Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    if (icon != null) ...[Icon(icon, color: Colors.white, size: 18), const SizedBox(width: 8)],
                    Text(label, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 16)),
                    if (showArrow) ...[
                      const SizedBox(width: 8),
                      const Icon(Icons.arrow_forward, color: Colors.white, size: 18),
                    ],
                  ],
                ),
        ),
      ),
    );
  }
}

class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    required this.controller,
    required this.hint,
    required this.icon,
    this.obscure = false,
    this.onToggleObscure,
    this.keyboardType,
    this.textInputAction,
    this.onSubmitted,
    this.errorText,
  });

  final TextEditingController controller;
  final String hint;
  final IconData icon;
  final bool obscure;
  final VoidCallback? onToggleObscure;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;
  final String? errorText;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: controller,
          obscureText: obscure,
          keyboardType: keyboardType,
          textInputAction: textInputAction,
          onSubmitted: onSubmitted,
          style: const TextStyle(color: AppTokens.textPrimary, fontSize: 14, fontWeight: FontWeight.w500),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: const TextStyle(color: AppTokens.textMuted, fontSize: 13),
            filled: true,
            fillColor: AppTokens.surfaceMuted,
            prefixIcon: Icon(icon, color: AppTokens.primary, size: 20),
            suffixIcon: onToggleObscure == null
                ? null
                : IconButton(
                    onPressed: onToggleObscure,
                    icon: Icon(obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined, color: AppTokens.textMuted),
                  ),
            contentPadding: const EdgeInsets.symmetric(vertical: 16),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppTokens.radiusInput),
              borderSide: const BorderSide(color: AppTokens.border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppTokens.radiusInput),
              borderSide: const BorderSide(color: AppTokens.primary, width: 1.4),
            ),
            errorBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(AppTokens.radiusInput),
              borderSide: const BorderSide(color: AppTokens.danger),
            ),
          ),
        ),
        if (errorText != null) ...[
          const SizedBox(height: 6),
          Text(errorText!, style: const TextStyle(color: AppTokens.danger, fontSize: 12)),
        ],
      ],
    );
  }
}

class WhiteCard extends StatelessWidget {
  const WhiteCard({super.key, required this.child, this.padding = const EdgeInsets.all(20)});

  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: AppTokens.surface,
        borderRadius: BorderRadius.circular(AppTokens.radiusSheet),
        boxShadow: AppTokens.cardShadow,
      ),
      child: child,
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.action, this.onAction});

  final String title;
  final String? action;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(color: AppTokens.textOnDark)),
        ),
        if (action != null)
          TextButton(
            onPressed: onAction,
            child: Text(action!, style: const TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w700)),
          ),
      ],
    );
  }
}

class SessionTile extends StatelessWidget {
  const SessionTile({super.key, required this.session, this.onTap, this.onBookmark});

  final Map<String, dynamic> session;
  final VoidCallback? onTap;
  final VoidCallback? onBookmark;

  @override
  Widget build(BuildContext context) {
    final category = (session['category'] as Map?)?.cast<String, dynamic>() ?? {};
    final name = (category['name'] ?? '').toString();
    final slug = (category['slug'] ?? '').toString();
    final color = slug == 'keynote'
        ? AppTokens.accentGold
        : slug == 'research'
            ? const Color(0xFF7C5CFF)
            : AppTokens.primary;
    final place = (session['speaker_name'] ?? session['room'] ?? '').toString();
    final cancelled = session['status'] == 'cancelled';
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(16),
      child: Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTokens.surface,
        borderRadius: BorderRadius.circular(16),
        border: session['is_live'] == true || session['is_next'] == true ? Border.all(color: AppTokens.accentGold, width: 1.4) : null,
        boxShadow: AppTokens.cardShadow,
      ),
      child: Row(
        children: [
          SizedBox(
            width: 56,
            child: Column(
              children: [
                Text(session['start_local']?.toString() ?? '', softWrap: false, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13)),
                Text(session['meridiem']?.toString() ?? '', softWrap: false, style: const TextStyle(color: AppTokens.textMuted, fontSize: 11)),
              ],
            ),
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
            child: Icon(Icons.event_note, color: color, size: 18),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(name.toUpperCase(), style: AppTheme.overline(color: color)),
                const SizedBox(height: 2),
                Text(
                  session['title']?.toString() ?? '',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                    decoration: cancelled ? TextDecoration.lineThrough : null,
                  ),
                ),
                if (session['status'] == 'changed') const Text('Updated', style: TextStyle(color: AppTokens.warning, fontSize: 11, fontWeight: FontWeight.w700)),
                if (cancelled) const Text('Cancelled', style: TextStyle(color: AppTokens.danger, fontSize: 11, fontWeight: FontWeight.w700)),
                if (session['is_live'] == true) const Text('LIVE', style: TextStyle(color: AppTokens.danger, fontSize: 11, fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Row(
                  children: [
                    const Icon(Icons.place_outlined, size: 13, color: AppTokens.textMuted),
                    const SizedBox(width: 4),
                    Expanded(child: Text(place, style: const TextStyle(color: AppTokens.textMuted, fontSize: 12), overflow: TextOverflow.ellipsis)),
                  ],
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onBookmark,
            icon: Icon(session['is_bookmarked'] == true ? Icons.bookmark : Icons.bookmark_border, color: session['is_bookmarked'] == true ? AppTokens.primary : AppTokens.textMuted),
          ),
        ],
      ),
    ),
    );
  }
}

class EmptyPanel extends StatelessWidget {
  const EmptyPanel({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(color: AppTokens.surface, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          const Icon(Icons.event_busy, color: AppTokens.primary),
          const SizedBox(height: 8),
          Text(message, textAlign: TextAlign.center, style: const TextStyle(color: AppTokens.textMuted)),
        ],
      ),
    );
  }
}

class ErrorPanel extends StatelessWidget {
  const ErrorPanel({super.key, required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: AppTokens.surface, borderRadius: BorderRadius.circular(16)),
      child: Column(
        children: [
          Text(message, textAlign: TextAlign.center),
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        ],
      ),
    );
  }
}
