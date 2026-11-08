import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';

class NameTagScreen extends ConsumerWidget {
  const NameTagScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final badge = ref.watch(_badgeProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: badge.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  const Align(alignment: Alignment.centerLeft, child: AppBackButton()),
                  const SizedBox(height: 24),
                  ErrorPanel(
                    message: error is ApiException ? error.message : 'Could not load your badge.',
                    onRetry: () => ref.invalidate(_badgeProvider),
                  ),
                ],
              ),
            ),
            data: (data) {
              final revoked = data['status'] == 'revoked';
              final subtitle = [data['designation'], data['attendee_type']].whereType<String>().where((item) => item.isNotEmpty).join(' • ');
              return ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                children: [
                  Row(
                    children: [
                      const AppBackButton(),
                      const Expanded(child: Text('My Name Tag', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                      IconButton(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Use the system share sheet to print this badge.')));
                        },
                        icon: const Icon(Icons.print, color: AppTokens.accentGold),
                      ),
                    ],
                  ),
                  if (revoked)
                    const Padding(
                      padding: EdgeInsets.only(top: 12),
                      child: Text('Badge not active, contact registration desk', style: TextStyle(color: AppTokens.danger)),
                    ),
                  if (data['checked_in_at'] != null)
                    const Padding(padding: EdgeInsets.only(top: 8), child: Text('Checked in', style: TextStyle(color: AppTokens.success, fontWeight: FontWeight.w700))),
                  const SizedBox(height: 12),
                  Container(
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24)),
                    clipBehavior: Clip.antiAlias,
                    child: Column(
                      children: [
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
                          decoration: const BoxDecoration(gradient: AppTokens.buttonGradient),
                          child: const Column(
                            children: [
                              Text('NESTLÉ MEDICAL', style: TextStyle(color: Colors.white, letterSpacing: 1.4, fontSize: 11, fontWeight: FontWeight.w700)),
                              SizedBox(height: 2),
                              Text('CONGRESS 2026', style: TextStyle(color: Colors.white, letterSpacing: 1, fontSize: 16, fontWeight: FontWeight.w800)),
                            ],
                          ),
                        ),
                        Transform.translate(
                          offset: const Offset(0, -22),
                          child: Padding(
                            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
                            child: Column(
                              children: [
                                Container(
                                  width: 80,
                                  height: 80,
                                  alignment: Alignment.center,
                                  decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: AppTokens.accentGold, width: 3)),
                                  child: Text(data['initials']?.toString() ?? '', style: const TextStyle(color: AppTokens.primary, fontSize: 26, fontWeight: FontWeight.w800)),
                                ),
                                const SizedBox(height: 8),
                                Text(data['full_name']?.toString() ?? '', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                                const SizedBox(height: 4),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.center,
                                  children: [
                                    Text(subtitle, style: const TextStyle(color: AppTokens.textMuted)),
                                    const SizedBox(width: 4),
                                    const Icon(Icons.military_tech, color: AppTokens.accentGold, size: 16),
                                  ],
                                ),
                                const SizedBox(height: 10),
                                _InfoRow(icon: Icons.badge_outlined, label: 'Badge ID', value: data['badge_code']?.toString() ?? ''),
                                _InfoRow(icon: Icons.place_outlined, label: 'Location', value: data['location']?.toString() ?? ''),
                                _InfoRow(icon: Icons.calendar_month_outlined, label: 'Congress Date', value: data['event_dates_label']?.toString() ?? ''),
                                const SizedBox(height: 12),
                                if (revoked)
                                  ImageFiltered(
                                    imageFilter: ImageFilter.blur(sigmaX: 6, sigmaY: 6),
                                    child: _QrGrid(modules: data['qr_modules'] as List? ?? const []),
                                  )
                                else
                                  _QrGrid(modules: data['qr_modules'] as List? ?? const []),
                                const SizedBox(height: 6),
                                const Text('Show this QR code at check-in', style: TextStyle(color: AppTokens.textMuted, fontSize: 12)),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

final _badgeProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/me/badge');
});

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: const Color(0xFFF4F7FB), borderRadius: BorderRadius.circular(16)),
      child: Row(
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: AppTokens.primary, size: 18),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(color: AppTokens.textMuted, fontSize: 11)),
              Text(value, style: const TextStyle(fontWeight: FontWeight.w800)),
            ],
          ),
        ],
      ),
    );
  }
}

class _QrGrid extends StatelessWidget {
  const _QrGrid({required this.modules});
  final List modules;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(size: const Size(220, 220), painter: _QrPainter(modules));
  }
}

class _QrPainter extends CustomPainter {
  _QrPainter(this.modules);
  final List modules;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = const Color(0xFF111111);
    canvas.drawRect(Offset.zero & size, Paint()..color = Colors.white);
    if (modules.isEmpty) return;
    final rows = modules.length;
    final cell = size.width / rows;
    for (var y = 0; y < rows; y++) {
      final row = modules[y].toString();
      for (var x = 0; x < row.length && x < rows; x++) {
        if (row[x] == '1') {
          canvas.drawRect(Rect.fromLTWH(x * cell - 0.4, y * cell - 0.4, cell + 0.8, cell + 0.8), paint);
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant _QrPainter oldDelegate) => oldDelegate.modules != modules;
}
