import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import 'auth_controller.dart';

class VerifyEmailScreen extends ConsumerStatefulWidget {
  const VerifyEmailScreen({super.key});

  @override
  ConsumerState<VerifyEmailScreen> createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends ConsumerState<VerifyEmailScreen> {
  final _boxes = List.generate(6, (_) => TextEditingController());
  final _nodes = List.generate(6, (_) => FocusNode());
  int _seconds = 60;

  @override
  void initState() {
    super.initState();
    _tick();
  }

  Future<void> _tick() async {
    while (mounted && _seconds > 0) {
      await Future<void>.delayed(const Duration(seconds: 1));
      if (!mounted) return;
      setState(() => _seconds -= 1);
    }
  }

  @override
  void dispose() {
    for (final box in _boxes) {
      box.dispose();
    }
    for (final node in _nodes) {
      node.dispose();
    }
    super.dispose();
  }

  String get _code => _boxes.map((box) => box.text).join();

  Future<void> _submit() async {
    if (_code.length < 6) return;
    final ok = await ref.read(authControllerProvider.notifier).verify(_code);
    if (ok && mounted) context.go('/home');
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    final email = auth.pendingEmail ?? '';
    final masked = email.isEmpty ? 'your email' : '${email.substring(0, 1)}***@${email.split('@').last}';
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              const Align(alignment: Alignment.centerLeft, child: AppBackButton()),
              const SizedBox(height: 24),
              Text('Verify email', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white)),
              const SizedBox(height: 8),
              Text('Enter the 6-digit code sent to $masked', style: const TextStyle(color: AppTokens.textOnDarkMuted)),
              if (auth.devOtp != null) ...[
                const SizedBox(height: 8),
                Text('Local dev code: ${auth.devOtp}', style: const TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w700)),
              ],
              const SizedBox(height: 20),
              WhiteCard(
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: List.generate(6, (index) {
                        return SizedBox(
                          width: 44,
                          child: TextField(
                            controller: _boxes[index],
                            focusNode: _nodes[index],
                            textAlign: TextAlign.center,
                            keyboardType: TextInputType.number,
                            maxLength: 1,
                            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                            decoration: const InputDecoration(counterText: '', filled: true, fillColor: AppTokens.surfaceMuted),
                            onChanged: (value) {
                              if (value.length > 1) {
                                final chars = value.replaceAll(RegExp(r'\D'), '').split('');
                                for (var i = 0; i < chars.length && index + i < 6; i++) {
                                  _boxes[index + i].text = chars[i];
                                }
                                _nodes[(index + chars.length - 1).clamp(0, 5)].requestFocus();
                              } else if (value.isNotEmpty && index < 5) {
                                _nodes[index + 1].requestFocus();
                              }
                              if (_code.length == 6) _submit();
                            },
                          ),
                        );
                      }),
                    ),
                    if (auth.formError != null) ...[
                      const SizedBox(height: 12),
                      Text(auth.formError!, style: const TextStyle(color: AppTokens.danger)),
                    ],
                    const SizedBox(height: 16),
                    PrimaryButton(label: 'Verify', loading: auth.busy, onPressed: _submit),
                    const SizedBox(height: 8),
                    TextButton(
                      onPressed: _seconds > 0
                          ? null
                          : () async {
                              await ref.read(authControllerProvider.notifier).resend();
                              setState(() => _seconds = 60);
                              _tick();
                            },
                      child: Text(_seconds > 0 ? 'Resend code in ${_seconds}s' : 'Resend code'),
                    ),
                    TextButton(onPressed: () => context.go('/register'), child: const Text('Change email')),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class ForgotPasswordScreen extends ConsumerStatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  ConsumerState<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends ConsumerState<ForgotPasswordScreen> {
  final _email = TextEditingController();
  final _code = TextEditingController();
  final _password = TextEditingController();
  bool _sent = false;

  @override
  void dispose() {
    _email.dispose();
    _code.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authControllerProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              const Align(alignment: Alignment.centerLeft, child: AppBackButton()),
              const SizedBox(height: 20),
              Text(_sent ? 'Reset password' : 'Forgot password', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white)),
              const SizedBox(height: 16),
              WhiteCard(
                child: Column(
                  children: [
                    if (!_sent)
                      AppTextField(controller: _email, hint: 'Email address', icon: Icons.mail_outline, keyboardType: TextInputType.emailAddress)
                    else ...[
                      AppTextField(controller: _code, hint: '6-digit code', icon: Icons.pin_outlined, keyboardType: TextInputType.number),
                      const SizedBox(height: 12),
                      AppTextField(controller: _password, hint: 'New password', icon: Icons.lock_outline, obscure: true),
                      if (auth.devOtp != null)
                        Padding(
                          padding: const EdgeInsets.only(top: 8),
                          child: Text('Local dev code: ${auth.devOtp}', style: const TextStyle(color: AppTokens.accentGold)),
                        ),
                    ],
                    if (auth.formError != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(auth.formError!, style: const TextStyle(color: AppTokens.danger)),
                      ),
                    if (auth.info != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(auth.info!, style: const TextStyle(color: AppTokens.success)),
                      ),
                    const SizedBox(height: 16),
                    PrimaryButton(
                      label: _sent ? 'Update password' : 'Send code',
                      loading: auth.busy,
                      onPressed: () async {
                        if (!_sent) {
                          final ok = await ref.read(authControllerProvider.notifier).forgot(_email.text);
                          if (ok) setState(() => _sent = true);
                        } else {
                          final ok = await ref.read(authControllerProvider.notifier).resetPassword(_code.text, _password.text);
                          if (ok && context.mounted) context.go('/welcome');
                        }
                      },
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
