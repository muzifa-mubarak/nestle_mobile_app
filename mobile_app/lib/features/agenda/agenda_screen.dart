import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../home/home_screen.dart';

class AgendaScreen extends ConsumerStatefulWidget {
  const AgendaScreen({super.key, this.savedOnly = false});
  final bool savedOnly;

  @override
  ConsumerState<AgendaScreen> createState() => _AgendaScreenState();
}

class _AgendaScreenState extends ConsumerState<AgendaScreen> {
  String? _date;
  String? _categoryId;
  String _query = '';
  bool _searching = false;
  bool _mine = false;
  bool _canFilterMine = false;
  Map<String, dynamic>? _agenda;
  List<Map<String, dynamic>> _categories = [];
  Object? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final event = await ref.read(eventProvider.future);
      final categories = await ref.read(apiClientProvider).get('/events/${event['id']}/categories', query: {'type': 'session'});
      final categoryRows = (categories['categories'] as List?) ?? [];
      final data = await ref.read(apiClientProvider).get(
        '/events/${event['id']}/agenda',
        query: {
          if (_date != null) 'date': _date,
          if (_categoryId != null) 'category_id': _categoryId,
          if (_query.isNotEmpty) 'q': _query,
          if (widget.savedOnly) 'saved': true,
          if (_mine) 'mine': true,
        },
      );
      final days = (event['days'] as List?) ?? [];
      setState(() {
        _categories = [for (final item in categoryRows) if (item is Map) Map<String, dynamic>.from(item)],
        _agenda = data;
        _canFilterMine = data['can_filter_mine'] == true;
        _date ??= data['date']?.toString() ?? (days.isNotEmpty ? (days.first as Map)['date']?.toString() : null);
        _loading = false;
      });
    } catch (error) {
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _toggle(String id, bool saved) async {
    final sessions = (_agenda?['sessions'] as List?) ?? [];
    final index = sessions.indexWhere((item) => item is Map && item['id'] == id);
    if (index < 0) return;
    setState(() => sessions[index]['is_bookmarked'] = !saved);
    try {
      final api = ref.read(apiClientProvider);
      if (saved) {
        await api.dio.delete('/me/bookmarks/session/$id');
      } else {
        await api.dio.put('/me/bookmarks/session/$id');
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => sessions[index]['is_bookmarked'] = saved);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Could not update the bookmark.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final event = ref.watch(eventProvider);
    final days = event.maybeWhen(data: (data) => (data['days'] as List?) ?? [], orElse: () => []);
    final sessions = (_agenda?['sessions'] as List?) ?? [];
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
              children: [
                Row(
                  children: [
                    const AppBackButton(),
                    const Expanded(child: Text('Congress Agenda', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                    IconButton(onPressed: () => setState(() => _searching = !_searching), icon: const Icon(Icons.search, color: AppTokens.accentGold)),
                  ],
                ),
                if (_searching)
                  TextField(
                    style: const TextStyle(color: AppTokens.textPrimary),
                    decoration: const InputDecoration(filled: true, fillColor: Colors.white, hintText: 'Search sessions'),
                    onSubmitted: (value) {
                      _query = value.trim();
                      _load();
                    },
                  ),
                const SizedBox(height: 12),
                Text(_agenda == null ? 'Schedule' : '${_dayLabel(days)} Schedule', style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w800)),
                Text(_agenda?['weekday'] == null ? '' : '${_agenda!['weekday']}, ${_agenda!['date_label']}', style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                const SizedBox(height: 12),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final day in days)
                        if (day is Map)
                          Padding(
                            padding: const EdgeInsets.only(right: 8),
                            child: ChoiceChip(
                              label: Text('${day['label']}\n${day['short']}'),
                              selected: _date == day['date'],
                              onSelected: (_) {
                                _date = day['date']?.toString();
                                _load();
                              },
                            ),
                          ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                WhiteCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(child: Text(_agenda?['heading']?.toString() ?? 'Sessions', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800))),
                          TextButton.icon(
                            onPressed: () {
                              _categoryId = null;
                              _query = '';
                              _load();
                            },
                            icon: const Icon(Icons.refresh),
                            label: const Text('Reset'),
                          ),
                        ],
                      ),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            ChoiceChip(label: const Text('All'), selected: _categoryId == null && !_mine, onSelected: (_) { _categoryId = null; _mine = false; _load(); }),
                            if (_canFilterMine)
                              Padding(
                                padding: const EdgeInsets.only(left: 8),
                                child: ChoiceChip(label: const Text('My Sessions'), selected: _mine, onSelected: (_) { _mine = !_mine; _categoryId = null; _load(); }),
                              ),
                            for (final category in _categories)
                              Padding(
                                padding: const EdgeInsets.only(left: 8),
                                child: ChoiceChip(
                                  label: Text(category['name']?.toString() ?? ''),
                                  selected: _categoryId == category['id'],
                                  onSelected: (_) { _categoryId = category['id']?.toString(); _load(); },
                                ),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                if (_loading) const _AgendaSkeleton(),
                if (_error != null) ErrorPanel(message: _error is ApiException ? _error.toString() : 'Could not load the agenda.', onRetry: _load),
                if (!_loading && _error == null && sessions.isEmpty)
                  EmptyPanel(message: _mine ? 'You have no sessions on this day.' : 'No sessions match these filters.'),
                for (final item in sessions)
                  if (item is Map)
                    SessionTile(
                      session: Map<String, dynamic>.from(item),
                      onTap: () => context.push('/agenda/${item['id']}'),
                      onBookmark: () => _toggle(item['id'].toString(), item['is_bookmarked'] == true),
                    ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _dayLabel(List days) {
    for (final day in days) {
      if (day is Map && day['date'] == _date) return day['label']?.toString() ?? 'Day';
    }
    return 'Day';
  }
}

class _AgendaSkeleton extends StatelessWidget {
  const _AgendaSkeleton();

  @override
  Widget build(BuildContext context) {
    return Container(height: 88, decoration: BoxDecoration(color: Colors.white24, borderRadius: BorderRadius.circular(16)));
  }
}

class SessionDetailScreen extends ConsumerWidget {
  const SessionDetailScreen({super.key, required this.sessionId});
  final String sessionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final detail = ref.watch(_detailProvider(sessionId));
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: detail.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(_detailProvider(sessionId))),
            data: (session) => ListView(
              padding: const EdgeInsets.all(20),
              children: [
                const AppBackButton(),
                const SizedBox(height: 16),
                Text((session['category'] as Map?)?['name']?.toString().toUpperCase() ?? '', style: const TextStyle(color: AppTokens.accentGold, fontWeight: FontWeight.w800)),
                Text(session['title']?.toString() ?? '', style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Text('${session['start_local']} ${session['meridiem']} – ${session['end_local']} ${session['end_meridiem']}', style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                Text(session['room']?.toString() ?? '', style: const TextStyle(color: Colors.white)),
                if (session['status'] == 'changed' || session['status'] == 'cancelled')
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text('${session['status']} ${session['status_note'] ?? ''}', style: const TextStyle(color: AppTokens.warning)),
                  ),
                const SizedBox(height: 16),
                WhiteCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('About this session', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                      const SizedBox(height: 8),
                      Text(session['description']?.toString() ?? ''),
                      if (session['speakers'] is List && (session['speakers'] as List).isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Text('Speakers', style: TextStyle(fontWeight: FontWeight.w800)),
                        for (final person in session['speakers'] as List)
                          if (person is Map)
                            TextButton(
                              onPressed: () => context.push('/speakers/${person['id']}'),
                              child: Align(alignment: Alignment.centerLeft, child: Text(person['name']?.toString() ?? '')),
                            ),
                      ] else if ((session['speaker_name'] ?? '').toString().isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text(session['speaker_name'].toString(), style: const TextStyle(fontWeight: FontWeight.w700)),
                      ],
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

final _detailProvider = FutureProvider.autoDispose.family<Map<String, dynamic>, String>((ref, id) {
  return ref.watch(apiClientProvider).get('/sessions/$id');
});
