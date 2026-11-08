import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import 'auth_controller.dart';

Future<void> continueWithAccount(BuildContext context, WidgetRef ref, String provider) async {
  final name = TextEditingController();
  final email = TextEditingController();
  String? error;
  final gmail = provider == 'google';
  final title = gmail ? 'Continue with Gmail' : 'Continue with Apple';
  final hint = gmail ? 'name@gmail.com' : 'name@icloud.com';

  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.white,
    showDragHandle: true,
    builder: (sheetContext) {
      return StatefulBuilder(
        builder: (context, setSheetState) {
          return Padding(
            padding: EdgeInsets.fromLTRB(20, 0, 20, 24 + MediaQuery.viewInsetsOf(context).bottom),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(
                  gmail ? 'Use the Gmail address on your Google account.' : 'Use the email on your Apple account.',
                  style: const TextStyle(color: AppTokens.textMuted),
                ),
                const SizedBox(height: 12),
                TextField(controller: name, decoration: const InputDecoration(hintText: 'Full name')),
                const SizedBox(height: 8),
                TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: InputDecoration(hintText: hint)),
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Text(error!, style: const TextStyle(color: AppTokens.danger, fontSize: 12)),
                ],
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton(
                    onPressed: () async {
                      if (name.text.trim().length < 2) {
                        setSheetState(() => error = 'Enter your full name.');
                        return;
                      }
                      final message = await ref.read(authControllerProvider.notifier).social(
                            provider: provider,
                            fullName: name.text,
                            email: email.text,
                          );
                      if (message != null) {
                        setSheetState(() => error = message);
                        return;
                      }
                      if (sheetContext.mounted) Navigator.of(sheetContext).pop();
                      if (context.mounted) context.go('/home');
                    },
                    child: const Text('Continue'),
                  ),
                ),
              ],
            ),
          );
        },
      );
    },
  );
  name.dispose();
  email.dispose();
}
