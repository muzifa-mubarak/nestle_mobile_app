import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';
import '../home/home_screen.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: me.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error is ApiException ? error.message : 'Could not load your profile.', onRetry: () => ref.invalidate(meProvider)),
            data: (user) {
              final counts = user['counts'] as Map? ?? {};
              final name = user['full_name']?.toString() ?? '';
              final initials = name.split(' ').where((part) => part.isNotEmpty).take(2).map((part) => part[0]).join().toUpperCase();
              String pad(Object? value) => (value ?? 0).toString().padLeft(2, '0');
              return ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                children: [
                  Row(
                    children: [
                      const AppBackButton(),
                      const Expanded(child: Text('My Profile', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                      IconButton(onPressed: () => context.push('/settings'), icon: const Icon(Icons.settings, color: Colors.white)),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Center(
                    child: Container(
                      width: 88,
                      height: 88,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: AppTokens.accentGold, width: 4)),
                      child: Text(initials, style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800)),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(name, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w800)),
                  Text(user['attendee_type']?.toString() ?? '', textAlign: TextAlign.center, style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                  const SizedBox(height: 8),
                  Center(child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), border: Border.all(color: AppTokens.accentGold)),
                    child: Text('ID: ${user['badge_code'] ?? ''}', style: const TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w700)),
                  )),
                  const SizedBox(height: 16),
                  WhiteCard(
                    child: Column(
                      children: [
                        _InfoRow(icon: Icons.mail_outline, label: 'Email', value: user['email']?.toString() ?? '', onTap: () => context.push('/profile/edit')),
                        _InfoRow(icon: Icons.phone_outlined, label: 'Phone', value: user['phone_display']?.toString() ?? user['phone']?.toString() ?? 'Add phone', onTap: () => context.push('/profile/edit')),
                        _InfoRow(icon: Icons.place_outlined, label: 'Location', value: user['location']?.toString() ?? 'Add location', onTap: () => context.push('/profile/edit')),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      _Stat(value: pad(counts['sessions']), label: 'Sessions', icon: Icons.calendar_month, onTap: () => context.push('/agenda?saved=true')),
                      _Stat(value: pad(counts['saved']), label: 'Saved', icon: Icons.bookmark, onTap: () => context.push('/resources?saved=true')),
                      _Stat(value: pad(counts['certificates']), label: 'Certificates', icon: Icons.workspace_premium, onTap: () => context.push('/profile/certificates')),
                    ],
                  ),
                ],
              );
            },
          ),
        ),
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppTokens.bgNavy900,
        selectedIndex: 1,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined, color: Colors.white), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.person, color: AppTokens.accentGold), label: 'Profile'),
        ],
        onDestinationSelected: (index) {
          if (index == 0) context.go('/home');
        },
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.label, required this.value, required this.onTap});
  final IconData icon;
  final String label;
  final String value;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: Icon(icon, color: AppTokens.primary),
      title: Text(label, style: const TextStyle(color: AppTokens.textMuted, fontSize: 12)),
      subtitle: Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
      onTap: onTap,
    );
  }
}

class _Stat extends StatelessWidget {
  const _Stat({required this.value, required this.label, required this.icon, required this.onTap});
  final String value;
  final String label;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Material(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(18),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 14),
              child: Column(
                children: [
                  Icon(icon, color: AppTokens.primary, size: 18),
                  Text(value, style: const TextStyle(color: AppTokens.primary, fontSize: 22, fontWeight: FontWeight.w800)),
                  Text(label, style: const TextStyle(fontSize: 12)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _name = TextEditingController();
  final _org = TextEditingController();
  final _role = TextEditingController();
  final _phone = TextEditingController();
  final _location = TextEditingController();
  bool _ready = false;
  bool _busy = false;
  String? _error;
  String _email = '';
  String _badge = '';

  @override
  void dispose() {
    _name.dispose();
    _org.dispose();
    _role.dispose();
    _phone.dispose();
    _location.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() { _busy = true; _error = null; });
    try {
      await ref.read(apiClientProvider).patch('/me', {
        'full_name': _name.text.trim(),
        'organization': _org.text.trim(),
        'designation': _role.text.trim(),
        'phone': _phone.text.trim(),
        'location': _location.text.trim(),
      });
      ref.invalidate(meProvider);
      if (mounted) context.pop();
    } catch (error) {
      setState(() { _error = error is ApiException ? error.message : 'Could not save.'; _busy = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final me = ref.watch(meProvider);
    me.whenData((user) {
      if (_ready) return;
      _name.text = user['full_name']?.toString() ?? '';
      _org.text = user['organization']?.toString() ?? '';
      _role.text = user['designation']?.toString() ?? '';
      _phone.text = user['phone']?.toString() ?? '';
      _location.text = user['location']?.toString() ?? '';
      _email = user['email']?.toString() ?? '';
      _badge = user['badge_code']?.toString() ?? '';
      _ready = true;
    });
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Row(children: [AppBackButton(), Expanded(child: Text('Edit Profile', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)))]),
              const SizedBox(height: 12),
              WhiteCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(controller: _name, decoration: const InputDecoration(labelText: 'Full name')),
                    TextField(controller: _org, decoration: const InputDecoration(labelText: 'Organization')),
                    TextField(controller: _role, decoration: const InputDecoration(labelText: 'Designation')),
                    TextField(controller: _phone, decoration: const InputDecoration(labelText: 'Phone', hintText: '+971562834212')),
                    TextField(controller: _location, decoration: const InputDecoration(labelText: 'Location')),
                    const SizedBox(height: 8),
                    Text('Email $_email and ID $_badge stay the same.', style: const TextStyle(color: AppTokens.textMuted)),
                    if (_error != null) Text(_error!, style: const TextStyle(color: AppTokens.danger)),
                    PrimaryButton(label: 'Save', showArrow: false, loading: _busy, onPressed: _save),
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

class CertificatesScreen extends ConsumerWidget {
  const CertificatesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final certs = ref.watch(_certificatesProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: certs.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(_certificatesProvider)),
            data: (data) {
              final rows = data['certificates'] as List? ?? [];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Row(children: [AppBackButton(), Expanded(child: Text('Certificates', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)))]),
                  if (rows.isEmpty) const Padding(padding: EdgeInsets.only(top: 16), child: EmptyPanel(message: 'No certificates yet.')),
                  for (final item in rows)
                    if (item is Map)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: WhiteCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(item['event_name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
                              Text(item['certificate_number']?.toString() ?? ''),
                              Text((item['issued_at']?.toString() ?? '').split('T').first, style: const TextStyle(color: AppTokens.textMuted)),
                              PrimaryButton(
                                label: 'Download PDF',
                                showArrow: false,
                                onPressed: () async {
                                  final access = await ref.read(apiClientProvider).get('/me/certificates/${item['id']}/access');
                                  if (context.mounted) {
                                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(access['url']?.toString() ?? 'Download ready')));
                                  }
                                },
                              ),
                            ],
                          ),
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

final _certificatesProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/me/certificates');
});

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final me = ref.watch(meProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: me.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(meProvider)),
            data: (user) {
              final prefs = Map<String, dynamic>.from(user['notification_preferences'] as Map? ?? {});
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Row(children: [AppBackButton(), Expanded(child: Text('Settings', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)))]),
                  const SizedBox(height: 12),
                  WhiteCard(
                    child: Column(
                      children: [
                        for (final entry in [('event_updates', 'Event updates'), ('session_reminders', 'Session reminders'), ('qna', 'Q&A responses'), ('resources', 'New resources')])
                          SwitchListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(entry.$2),
                            value: prefs[entry.$1] != false,
                            onChanged: (enabled) async {
                              await ref.read(apiClientProvider).patch('/me', {'notification_preferences': {entry.$1: enabled}});
                              ref.invalidate(meProvider);
                            },
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('App version 1.0.0', style: TextStyle(color: Colors.white70)),
                  PrimaryButton(
                    label: 'Log out',
                    showArrow: false,
                    onPressed: () async {
                      await ref.read(authControllerProvider.notifier).logout();
                      if (context.mounted) context.go('/welcome');
                    },
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
