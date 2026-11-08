import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';
import '../home/home_screen.dart';

class SpeakersScreen extends ConsumerStatefulWidget {
  const SpeakersScreen({super.key});

  @override
  ConsumerState<SpeakersScreen> createState() => _SpeakersScreenState();
}

class _SpeakersScreenState extends ConsumerState<SpeakersScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  String? _categoryId;
  String? _country;
  bool _featured = false;
  bool _loading = true;
  Object? _error;
  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _speakers = [];
  List<String> _countries = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final event = await ref.read(eventProvider.future);
      final api = ref.read(apiClientProvider);
      final categories = await api.get('/events/${event['id']}/categories', query: {'type': 'speaker'});
      final data = await api.get('/events/${event['id']}/speakers', query: {
        if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
        if (_categoryId != null && _categoryId!.isNotEmpty) 'category_id': _categoryId,
        if (_featured) 'featured': true,
        if (_country != null && _country!.isNotEmpty) 'country': _country,
      });
      if (!mounted) return;
      setState(() {
        _categories = [
          for (final item in (categories['categories'] as List? ?? []))
            if (item is Map) Map<String, dynamic>.from(item),
        ];
        _speakers = [
          for (final item in (data['speakers'] as List? ?? []))
            if (item is Map) Map<String, dynamic>.from(item),
        ];
        _countries = [for (final item in (data['countries'] as List? ?? [])) item.toString()];
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _pickCountry() async {
    final selected = await showModalBottomSheet<String>(
      context: context,
      backgroundColor: Colors.white,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(title: Text('Country', style: TextStyle(fontWeight: FontWeight.w800))),
            ListTile(title: const Text('All countries'), onTap: () => Navigator.pop(context, '')),
            for (final country in _countries)
              ListTile(title: Text(country), onTap: () => Navigator.pop(context, country)),
          ],
        ),
      ),
    );
    if (selected == null) return;
    setState(() => _country = selected.isEmpty ? null : selected);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              Row(
                children: [
                  const AppBackButton(),
                  const Expanded(child: Text('Speakers', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  IconButton(
                    onPressed: () {
                      setState(() => _featured = !_featured);
                      _load();
                    },
                    icon: Icon(_featured ? Icons.star : Icons.star_border, color: _featured ? AppTokens.accentGold : Colors.white),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(22)),
                child: const Row(
                  children: [
                    _PeopleIcon(),
                    SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Global Medical Experts', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
                          SizedBox(height: 4),
                          Text('Meet speakers from nutrition, research and healthcare', style: TextStyle(color: Color(0xFFC5D0EA), fontSize: 13)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              WhiteCard(
                child: Column(
                  children: [
                    TextField(
                      controller: _search,
                      decoration: InputDecoration(
                        hintText: 'Search speakers',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: IconButton(onPressed: _pickCountry, icon: const Icon(Icons.tune, color: AppTokens.primary)),
                      ),
                      onChanged: (_) {
                        _debounce?.cancel();
                        _debounce = Timer(const Duration(milliseconds: 300), _load);
                      },
                    ),
                    const SizedBox(height: 12),
                    SizedBox(
                      height: 36,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          _Chip(label: 'All', selected: _categoryId == null, onTap: () { setState(() => _categoryId = null); _load(); }),
                          for (final category in _categories)
                            _Chip(
                              label: category['name']?.toString() ?? '',
                              selected: _categoryId == category['id'],
                              onTap: () { setState(() => _categoryId = category['id']?.toString()); _load(); },
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 8),
                    if (_loading) const Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator()),
                    if (!_loading && _error != null)
                      ErrorPanel(message: _error is ApiException ? (_error as ApiException).message : 'Could not load speakers.', onRetry: _load),
                    if (!_loading && _error == null && _speakers.isEmpty) const EmptyPanel(message: 'No speakers match your search.'),
                    for (final person in _speakers)
                      _SpeakerCard(person: person, onTap: () => context.push('/speakers/${person['id']}')),
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

class SpeakerDetailScreen extends ConsumerWidget {
  const SpeakerDetailScreen({super.key, required this.speakerId});
  final String speakerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(_speakerProvider(speakerId));
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: detail.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(_speakerProvider(speakerId))),
            data: (person) {
              final tags = person['specializations'] as List? ?? [];
              final sessions = person['sessions'] as List? ?? [];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const AppBackButton(),
                  const SizedBox(height: 16),
                  Center(child: _Initials(text: person['initials']?.toString() ?? '', featured: true, size: 80)),
                  const SizedBox(height: 8),
                  Text(person['name']?.toString() ?? '', textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800)),
                  Text(person['designation']?.toString() ?? '', textAlign: TextAlign.center, style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                  Text('${person['organization'] ?? ''} · ${person['country'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                  const SizedBox(height: 8),
                  Wrap(alignment: WrapAlignment.center, spacing: 6, children: [for (final tag in tags) if (tag is Map) Chip(label: Text(tag['name']?.toString() ?? ''))]),
                  const SizedBox(height: 12),
                  WhiteCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Biography', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                        const SizedBox(height: 8),
                        Text(person['biography']?.toString() ?? ''),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Sessions', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                  for (final session in sessions)
                    if (session is Map)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: SessionTile(session: Map<String, dynamic>.from(session), onTap: () => context.push('/agenda/${session['id']}')),
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

final _speakerProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) {
  return ref.watch(apiClientProvider).get('/speakers/$id');
});

class _PeopleIcon extends StatelessWidget {
  const _PeopleIcon();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 54,
      height: 54,
      decoration: BoxDecoration(gradient: AppTokens.buttonGradient, borderRadius: BorderRadius.circular(16)),
      child: const Icon(Icons.groups, color: Colors.white),
    );
  }
}

class _Chip extends StatelessWidget {
  const _Chip({required this.label, required this.selected, required this.onTap});
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) => onTap(),
        selectedColor: AppTokens.primary,
        labelStyle: TextStyle(color: selected ? Colors.white : AppTokens.textPrimary, fontWeight: FontWeight.w700),
      ),
    );
  }
}

class _SpeakerCard extends StatelessWidget {
  const _SpeakerCard({required this.person, required this.onTap});
  final Map<String, dynamic> person;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final featured = person['is_featured'] == true;
    final session = person['session'];
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Material(
        color: featured ? const Color(0xFFFFFBF3) : Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: featured ? const Color(0xFFF5D48A) : AppTokens.border),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(18),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                _Initials(text: person['initials']?.toString() ?? '', featured: featured, size: 52),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(featured ? 'FEATURED SPEAKER' : 'SPEAKER', style: TextStyle(color: featured ? AppTokens.accentGold : AppTokens.textMuted, fontSize: 10, fontWeight: FontWeight.w800, letterSpacing: 0.6)),
                      Text(person['name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
                      Text(person['designation']?.toString() ?? '', style: const TextStyle(color: AppTokens.textMuted, fontSize: 12)),
                      Text('📍 ${person['country'] ?? ''}', style: const TextStyle(color: AppTokens.textMuted, fontSize: 12)),
                      if (session is Map)
                        Container(
                          margin: const EdgeInsets.only(top: 6),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(color: const Color(0xFFE8F1FF), borderRadius: BorderRadius.circular(999)),
                          child: Text(session['title']?.toString() ?? '', style: const TextStyle(color: AppTokens.primary, fontSize: 11, fontWeight: FontWeight.w700)),
                        ),
                    ],
                  ),
                ),
                Icon(featured ? Icons.star : Icons.star_border, color: featured ? AppTokens.accentGold : const Color(0xFFC5D0EA)),
                const Icon(Icons.chevron_right, color: AppTokens.textMuted),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Initials extends StatelessWidget {
  const _Initials({required this.text, required this.featured, required this.size});
  final String text;
  final bool featured;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: Colors.white,
        border: Border.all(color: featured ? AppTokens.accentGold : const Color(0xFFD5E2FF), width: 2),
      ),
      child: Text(text, style: TextStyle(color: AppTokens.primary, fontWeight: FontWeight.w800, fontSize: size * 0.32)),
    );
  }
}
