import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';

class ResourcesScreen extends ConsumerStatefulWidget {
  const ResourcesScreen({super.key, this.savedOnly = false});
  final bool savedOnly;

  @override
  ConsumerState<ResourcesScreen> createState() => _ResourcesScreenState();
}

class _ResourcesScreenState extends ConsumerState<ResourcesScreen> {
  final _search = TextEditingController();
  String _chip = 'all';
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _error;
  String? _info;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    if (widget.savedOnly) _chip = 'saved';
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() { _loading = _items.isEmpty; _error = null; });
    try {
      final query = <String, dynamic>{};
      if (_chip == 'saved') query['saved'] = true;
      if (_chip != 'all' && _chip != 'saved') query['type'] = _chip;
      if (_search.text.trim().isNotEmpty) query['q'] = _search.text.trim();
      final data = await ref.read(apiClientProvider).get('/resources', query: query);
      if (!mounted) return;
      setState(() {
        _items = [for (final item in (data['resources'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _loading = false;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() { _error = error is ApiException ? error.message : 'Could not load resources.'; _loading = false; });
    }
  }

  Future<void> _bookmark(Map<String, dynamic> item) async {
    final id = item['id'].toString();
    final was = item['is_bookmarked'] == true;
    setState(() => item['is_bookmarked'] = !was);
    try {
      final data = was
          ? await ref.read(apiClientProvider).delete('/me/bookmarks/resource/$id')
          : await ref.read(apiClientProvider).put('/me/bookmarks/resource/$id');
      if (!mounted) return;
      setState(() {
        item['is_bookmarked'] = data['bookmarked'] == true;
        if (_chip == 'saved' && item['is_bookmarked'] != true) _items.remove(item);
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        item['is_bookmarked'] = was;
        _error = error is ApiException ? error.message : 'Could not update the bookmark.';
      });
    }
  }

  Future<void> _open(Map<String, dynamic> item) async {
    try {
      final data = await ref.read(apiClientProvider).get('/resources/${item['id']}/access');
      final url = data['url']?.toString() ?? '';
      await Clipboard.setData(ClipboardData(text: url));
      if (!mounted) return;
      setState(() => _info = data['kind'] == 'external' ? 'Link copied' : 'Download link copied');
    } catch (error) {
      if (!mounted) return;
      setState(() => _error = error is ApiException ? error.message : 'Could not open this resource.');
    }
  }

  @override
  Widget build(BuildContext context) {
    const chips = [('all', 'All'), ('pdf', 'PDF'), ('slides', 'Slides'), ('video', 'Videos'), ('saved', 'Saved')];
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              Row(
                children: [
                  const AppBackButton(),
                  const Expanded(child: Text('Resources', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  IconButton(
                    onPressed: () { setState(() => _chip = _chip == 'saved' ? 'all' : 'saved'); _load(); },
                    icon: Icon(Icons.folder_outlined, color: _chip == 'saved' ? AppTokens.accentGold : AppTokens.accentGold),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(22)),
                child: const Row(children: [
                  CircleAvatar(backgroundColor: AppTokens.primary, child: Icon(Icons.cloud_download_outlined, color: Colors.white)),
                  SizedBox(width: 12),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Congress Library', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
                    Text('Access presentations, documents and media files', style: TextStyle(color: Color(0xFFC5D0EA))),
                  ])),
                ]),
              ),
              const SizedBox(height: 14),
              WhiteCard(
                child: Column(
                  children: [
                    TextField(
                      controller: _search,
                      decoration: const InputDecoration(hintText: 'Search resources', prefixIcon: Icon(Icons.search)),
                      onChanged: (_) {
                        _debounce?.cancel();
                        _debounce = Timer(const Duration(milliseconds: 300), _load);
                      },
                    ),
                    const SizedBox(height: 10),
                    SizedBox(
                      height: 36,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          for (final chip in chips)
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(chip.$2),
                                selected: _chip == chip.$1,
                                onSelected: (_) { setState(() => _chip = chip.$1); _load(); },
                              ),
                            ),
                        ],
                      ),
                    ),
                    if (_error != null) Text(_error!, style: const TextStyle(color: AppTokens.danger)),
                    if (_info != null) Text(_info!, style: const TextStyle(color: AppTokens.success)),
                    if (_loading) const Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator()),
                    if (!_loading && _items.isEmpty) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_chip == 'saved' ? 'No saved resources.' : 'No resources found.')),
                    for (final item in _items) _ResourceTile(item: item, onSave: () => _bookmark(item), onOpen: () => _open(item)),
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

class _ResourceTile extends StatelessWidget {
  const _ResourceTile({required this.item, required this.onSave, required this.onOpen});
  final Map<String, dynamic> item;
  final VoidCallback onSave;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final type = item['type']?.toString() ?? 'document';
    final tone = switch (type) {
      'pdf' => (const Color(0xFFFDECEC), const Color(0xFFE5484D), 'PDF'),
      'slides' => (const Color(0xFFFFF4E0), const Color(0xFFE59A12), 'SLIDES'),
      'video' => (const Color(0xFFF3EEFF), const Color(0xFF7C5CFF), 'VIDEO'),
      _ => (const Color(0xFFE8F0FF), AppTokens.primary, type.toUpperCase()),
    };
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Row(
        children: [
          Container(
            width: 46,
            height: 46,
            alignment: Alignment.center,
            decoration: BoxDecoration(color: tone.$1, borderRadius: BorderRadius.circular(14)),
            child: Text(tone.$3 == 'PDF' ? 'PDF' : '▶', style: TextStyle(color: tone.$2, fontWeight: FontWeight.w800, fontSize: 11)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(tone.$3, style: TextStyle(color: tone.$2, fontSize: 11, fontWeight: FontWeight.w800)),
                Text(item['title']?.toString() ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(item['description']?.toString() ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: AppTokens.textMuted)),
                if ((item['file_size_label'] ?? '').toString().isNotEmpty)
                  Text(item['file_size_label'].toString(), style: const TextStyle(color: AppTokens.textMuted, fontSize: 12)),
              ],
            ),
          ),
          Column(
            children: [
              IconButton(onPressed: onSave, icon: Icon(item['is_bookmarked'] == true ? Icons.bookmark : Icons.bookmark_border, color: AppTokens.primary)),
              IconButton(onPressed: onOpen, icon: const Icon(Icons.download_outlined, color: AppTokens.textMuted)),
            ],
          ),
        ],
      ),
    );
  }
}
