import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import 'auth_controller.dart';
import 'social_sheet.dart';
import 'validators.dart';

class WelcomeScreen extends ConsumerStatefulWidget {
  const WelcomeScreen({super.key});

  @override
  ConsumerState<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends ConsumerState<WelcomeScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;
  String? _localError;
  bool _google = false;
  bool _apple = false;

  @override
  void initState() {
    super.initState();
    _loadFlags();
  }

  Future<void> _loadFlags() async {
    try {
      final config = await ref.read(apiClientProvider).get('/app/config');
      if (!mounted) return;
      setState(() {
        _google = config['google_signin_enabled'] == true;
        _apple = config['apple_signin_enabled'] == true;
      });
    } catch (_) {}
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final email = _email.text.trim();
    if (!isEmail(email) || _password.text.isEmpty) {
      setState(() => _localError = 'Enter a valid email and your password.');
      return;
    }
    setState(() => _localError = null);
    final ok = await ref.read(authControllerProvider.notifier).login(email, _password.text);
    if (!mounted) return;
    final auth = ref.read(authControllerProvider);
    if (ok) {
      context.go('/home');
    } else if (auth.formError != null && auth.pendingEmail != null && auth.formError!.toLowerCase().contains('verify')) {
      context.go('/verify-email');
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    final error = _localError ?? auth.formError;
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 28, 20, 24),
            children: [
              Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: AppTokens.accentGold),
                  ),
                  child: Text('NESTLÉ MEDICAL CONGRESS', style: AppTheme.overline()),
                ),
              ),
              const SizedBox(height: 18),
              Text('NESTLÉ', textAlign: TextAlign.center, style: Theme.of(context).textTheme.displaySmall?.copyWith(color: Colors.white)),
              Text('CONGRESS', textAlign: TextAlign.center, style: Theme.of(context).textTheme.displaySmall?.copyWith(color: AppTokens.accentGold)),
              const SizedBox(height: 8),
              Center(child: Container(width: 48, height: 2, color: AppTokens.accentGold)),
              const SizedBox(height: 10),
              const Text(
                'The Next Era of Nutrition & Health',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppTokens.textOnDarkMuted, fontSize: 13),
              ),
              const SizedBox(height: 22),
              WhiteCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Welcome Back', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: AppTokens.textPrimary)),
                              SizedBox(height: 4),
                              Text('Sign in to continue your congress experience', style: TextStyle(color: AppTokens.textMuted, fontSize: 12)),
                            ],
                          ),
                        ),
                        Container(
                          width: 44,
                          height: 44,
                          decoration: BoxDecoration(color: AppTokens.primary, borderRadius: BorderRadius.circular(14)),
                          child: const Icon(Icons.shield_outlined, color: Colors.white),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    AppTextField(
                      controller: _email,
                      hint: 'Enter your email',
                      icon: Icons.mail_outline,
                      keyboardType: TextInputType.emailAddress,
                      textInputAction: TextInputAction.next,
                    ),
                    const SizedBox(height: 12),
                    AppTextField(
                      controller: _password,
                      hint: 'Enter your password',
                      icon: Icons.lock_outline,
                      obscure: _obscure,
                      onToggleObscure: () => setState(() => _obscure = !_obscure),
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _submit(),
                    ),
                    if (error != null) ...[
                      const SizedBox(height: 10),
                      Text(error, style: const TextStyle(color: AppTokens.danger, fontSize: 12)),
                    ],
                    const SizedBox(height: 16),
                    PrimaryButton(label: 'Sign In', loading: auth.busy, onPressed: _submit),
                    if (_google || _apple) ...[
                      const SizedBox(height: 16),
                      const Center(child: Text('OR CONTINUE WITH', style: TextStyle(fontSize: 11, color: AppTokens.textMuted, letterSpacing: 0.6))),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          if (_google) Expanded(child: OutlinedButton(onPressed: () => continueWithAccount(context, ref, 'google'), child: const Text('Gmail'))),
                          if (_google && _apple) const SizedBox(width: 12),
                          if (_apple) Expanded(child: OutlinedButton(onPressed: () => continueWithAccount(context, ref, 'apple'), child: const Text('Apple'))),
                        ],
                      ),
                    ],
                    const SizedBox(height: 8),
                    Center(
                      child: TextButton.icon(
                        onPressed: () => context.push('/forgot-password'),
                        icon: const Icon(Icons.lock_outline, size: 16),
                        label: const Text('Forgot password?'),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text("Don't have an account? ", style: TextStyle(color: AppTokens.textOnDarkMuted)),
                  GestureDetector(
                    onTap: () => context.push('/register'),
                    child: const Text('Create Account →', style: TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w800)),
                  ),
                ],
              ),
              const SizedBox(height: 22),
              const Row(
                children: [
                  Expanded(child: _FeatureChip(icon: Icons.public, label: 'Global\nExperts')),
                  SizedBox(width: 8),
                  Expanded(child: _FeatureChip(icon: Icons.menu_book_outlined, label: 'Knowledge\nSessions')),
                  SizedBox(width: 8),
                  Expanded(child: _FeatureChip(icon: Icons.groups_outlined, label: 'Networking &\nOpportunities')),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureChip extends StatelessWidget {
  const _FeatureChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Icon(icon, color: AppTokens.accentGold, size: 18),
          const SizedBox(height: 6),
          Text(label, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 11, height: 1.2)),
        ],
      ),
    );
  }
}
