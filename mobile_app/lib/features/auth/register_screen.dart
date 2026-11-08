import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import 'auth_controller.dart';
import 'social_sheet.dart';
import 'validators.dart';

class RegisterScreen extends ConsumerStatefulWidget {
  const RegisterScreen({super.key});

  @override
  ConsumerState<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends ConsumerState<RegisterScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _org = TextEditingController();
  final _password = TextEditingController();
  bool _obscure = true;
  bool _terms = false;
  String? _localError;

  @override
  void initState() {
    super.initState();
    _password.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _org.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _openPage(String key, String title) async {
    try {
      final page = await ref.read(apiClientProvider).get('/cms/$key');
      if (!mounted) return;
      await showModalBottomSheet<void>(
        context: context,
        backgroundColor: Colors.white,
        showDragHandle: true,
        builder: (context) => Padding(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(page['title']?.toString() ?? title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(page['body_markdown']?.toString() ?? '', style: const TextStyle(color: AppTokens.textMuted, height: 1.4)),
            ],
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open that page.')));
    }
  }

  Future<void> _social(String provider) async {
    if (!_terms) {
      setState(() => _localError = 'Please agree to the terms to continue.');
      return;
    }
    await continueWithAccount(context, ref, provider);
  }

  Future<void> _submit() async {
    final rules = PasswordRules(_password.text);
    if (!_terms) {
      setState(() => _localError = 'Please agree to the terms to continue.');
      return;
    }
    if (_name.text.trim().length < 2 || !isEmail(_email.text) || _org.text.trim().length < 2 || !rules.valid) {
      setState(() => _localError = 'Check your name, email, organization, and password.');
      return;
    }
    setState(() => _localError = null);
    final ok = await ref.read(authControllerProvider.notifier).register(
          fullName: _name.text,
          email: _email.text,
          organization: _org.text,
          password: _password.text,
          acceptedTerms: _terms,
        );
    if (ok && mounted) context.go('/verify-email');
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 28, 20, 24),
            children: [
              const Text('Join the', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w700, height: 1.1)),
              const Text('NESTLÉ', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.w800, height: 1.0)),
              const Text('CONGRESS', textAlign: TextAlign.center, style: TextStyle(color: AppTokens.accentGold, fontSize: 36, fontWeight: FontWeight.w800, height: 1.0)),
              const SizedBox(height: 12),
              const Text(
                'Create your attendee profile and access sessions, resources, voting and Q&A.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Color(0xFFC5D0EA), fontSize: 14, height: 1.45),
              ),
              const SizedBox(height: 16),
              WhiteCard(
                child: Column(
                  children: [
                    AppTextField(controller: _name, hint: 'Full name', icon: Icons.person_outline),
                    const SizedBox(height: 12),
                    AppTextField(
                      controller: _email,
                      hint: 'Email address',
                      icon: Icons.mail_outline,
                      keyboardType: TextInputType.emailAddress,
                      errorText: auth.fieldErrors['email'],
                    ),
                    const SizedBox(height: 12),
                    AppTextField(controller: _org, hint: 'Hospital / Organization', icon: Icons.apartment_outlined),
                    const SizedBox(height: 12),
                    AppTextField(
                      controller: _password,
                      hint: 'Create password',
                      icon: Icons.lock_outline,
                      obscure: _obscure,
                      onToggleObscure: () => setState(() => _obscure = !_obscure),
                      onSubmitted: (_) => setState(() {}),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Checkbox(value: _terms, onChanged: (value) => setState(() => _terms = value ?? false)),
                        Expanded(
                          child: Padding(
                            padding: const EdgeInsets.only(top: 10),
                            child: Wrap(
                              children: [
                                const Text('I agree to the congress '),
                                _Link('terms', () => _openPage('terms', 'Terms')),
                                const Text(', '),
                                _Link('privacy policy', () => _openPage('privacy', 'Privacy')),
                                const Text(' and '),
                                _Link('attendee guidelines', () => _openPage('guidelines', 'Guidelines')),
                                const Text('.'),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (_localError != null || auth.formError != null)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Text(_localError ?? auth.formError!, style: const TextStyle(color: AppTokens.danger, fontSize: 12)),
                      ),
                    PrimaryButton(
                      label: 'Create Account',
                      icon: Icons.person_add_alt_1,
                      showArrow: false,
                      loading: auth.busy,
                      onPressed: _submit,
                    ),
                    const SizedBox(height: 16),
                    const Text('OR SIGN UP WITH', textAlign: TextAlign.center, style: TextStyle(color: Color(0xFF98A4C0), fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(child: _SocialButton(label: 'G', onTap: () => _social('google'))),
                        const SizedBox(width: 12),
                        Expanded(child: _SocialButton(label: '', apple: true, onTap: () => _social('apple'))),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('Already have an account? ', style: TextStyle(color: AppTokens.textOnDarkMuted)),
                  GestureDetector(
                    onTap: () => context.go('/welcome'),
                    child: const Text('Sign In', style: TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w800)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SocialButton extends StatelessWidget {
  const _SocialButton({required this.label, required this.onTap, this.apple = false});
  final String label;
  final VoidCallback onTap;
  final bool apple;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onTap,
      style: OutlinedButton.styleFrom(
        minimumSize: const Size.fromHeight(50),
        side: const BorderSide(color: AppTokens.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        backgroundColor: Colors.white,
      ),
      child: apple ? const Icon(Icons.apple, color: Colors.black, size: 26) : Text(label, style: const TextStyle(color: Color(0xFF4285F4), fontWeight: FontWeight.w800, fontSize: 20)),
    );
  }
}

class _Link extends StatelessWidget {
  const _Link(this.label, this.onTap);
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Text(label, style: const TextStyle(color: AppTokens.primary, fontWeight: FontWeight.w700)),
    );
  }
}
