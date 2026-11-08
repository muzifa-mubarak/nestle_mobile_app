import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../home/home_screen.dart';

class ExhibitorsScreen extends ConsumerStatefulWidget {
  const ExhibitorsScreen({super.key});

  @override
  ConsumerState<ExhibitorsScreen> createState() => _ExhibitorsScreenState();
}

class _ExhibitorsScreenState extends ConsumerState<ExhibitorsScreen> {
  final _search = TextEditingController();
  Timer? _debounce;
  String? _categoryId;
  bool _loading = true;
  Object? _error;
  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _exhibitors = [];

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
      final categories = await api.get('/events/${event['id']}/categories', query: {'type': 'exhibitor'});
      final data = await api.get('/events/${event['id']}/exhibitors', query: {
        if (_search.text.trim().isNotEmpty) 'q': _search.text.trim(),
        if (_categoryId != null) 'category_id': _categoryId,
      });
      if (!mounted) return;
      setState(() {
        _categories = [for (final item in (categories['categories'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _exhibitors = [for (final item in (data['exhibitors'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              const Row(
                children: [
                  AppBackButton(),
                  Expanded(child: Text('Exhibitors', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _search,
                style: const TextStyle(color: AppTokens.textPrimary),
                decoration: const InputDecoration(filled: true, fillColor: Colors.white, hintText: 'Search exhibitors', prefixIcon: Icon(Icons.search)),
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
                    _chip('All', null),
                    for (final category in _categories) _chip(category['name']?.toString() ?? '', category['id']?.toString()),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              if (_loading) const Center(child: Padding(padding: EdgeInsets.all(24), child: CircularProgressIndicator(color: Colors.white))),
              if (_error != null) ErrorPanel(message: _error is ApiException ? _error!.message : 'Could not load exhibitors.', onRetry: _load),
              if (!_loading && _error == null && _exhibitors.isEmpty) const EmptyPanel(message: 'No exhibitors match your search.'),
              for (final item in _exhibitors)
                Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    leading: const CircleAvatar(child: Icon(Icons.storefront_outlined)),
                    title: Text(item['name']?.toString() ?? ''),
                    subtitle: Text([
                      if ((item['booth'] ?? '').toString().isNotEmpty) 'Booth ${item['booth']}',
                      if (item['category'] is Map) (item['category'] as Map)['name']?.toString() ?? '',
                    ].where((part) => part.isNotEmpty).join(' · ')),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => context.push('/exhibitors/${item['id']}'),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _chip(String label, String? id) {
    final selected = _categoryId == id;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: ChoiceChip(
        label: Text(label),
        selected: selected,
        onSelected: (_) {
          setState(() => _categoryId = id);
          _load();
        },
      ),
    );
  }
}

class ExhibitorDetailScreen extends ConsumerStatefulWidget {
  const ExhibitorDetailScreen({super.key, required this.exhibitorId});
  final String exhibitorId;

  @override
  ConsumerState<ExhibitorDetailScreen> createState() => _ExhibitorDetailScreenState();
}

class _ExhibitorDetailScreenState extends ConsumerState<ExhibitorDetailScreen> {
  Map<String, dynamic>? _item;
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = await ref.read(apiClientProvider).get('/exhibitors/${widget.exhibitorId}');
      if (!mounted) return;
      setState(() {
        _item = data;
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

  Future<void> _open(String? value, {bool mail = false}) async {
    if (value == null || value.isEmpty) return;
    final uri = Uri.parse(mail ? 'mailto:$value' : value);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not open that link.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = _item;
    final category = item?['category'] is Map ? (item!['category'] as Map)['name']?.toString() : null;
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              const Row(
                children: [
                  AppBackButton(),
                  Expanded(child: Text('Exhibitor', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  SizedBox(width: 48),
                ],
              ),
              const SizedBox(height: 16),
              if (_loading) const Center(child: CircularProgressIndicator(color: Colors.white)),
              if (_error != null) ErrorPanel(message: _error is ApiException ? (_error! as ApiException).message : 'Exhibitor not found.', onRetry: _load),
              if (item != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item['name']?.toString() ?? '', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                        if ((item['booth'] ?? '').toString().isNotEmpty) Text('Booth ${item['booth']}', style: const TextStyle(color: AppTokens.primary, fontWeight: FontWeight.w700)),
                        if (category != null) Text(category),
                        const SizedBox(height: 12),
                        Text(item['description']?.toString() ?? ''),
                        const SizedBox(height: 16),
                        if ((item['website'] ?? '').toString().isNotEmpty)
                          FilledButton(onPressed: () => _open(item['website']?.toString()), child: const Text('Website')),
                        if ((item['contact_email'] ?? '').toString().isNotEmpty)
                          TextButton(onPressed: () => _open(item['contact_email']?.toString(), mail: true), child: Text(item['contact_email'].toString())),
                      ],
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
