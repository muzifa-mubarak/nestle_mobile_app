import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_exception.dart';
import '../../core/network/realtime_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';
import '../home/home_screen.dart';

class QnaScreen extends ConsumerStatefulWidget {
  const QnaScreen({super.key});

  @override
  ConsumerState<QnaScreen> createState() => _QnaScreenState();
}

class _QnaScreenState extends ConsumerState<QnaScreen> {
  final _text = TextEditingController();
  String _tab = 'recent';
  String? _categoryId;
  String? _sessionId;
  String? _sessionTitle;
  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _questions = [];
  bool _loading = true;
  bool _busy = false;
  String? _error;
  String? _info;
  Timer? _refresh;
  RealtimeClient? _live;

  @override
  void initState() {
    super.initState();
    _load();
    _live = RealtimeClient(ref.read(apiClientProvider));
    _live!.connect((event) {
      final type = event['type']?.toString() ?? '';
      if (type.startsWith('question.')) _load(quiet: true);
    });
    _refresh = Timer.periodic(const Duration(seconds: 10), (_) {
      if (_live?.connected != true) _load(quiet: true);
    });
  }

  @override
  void dispose() {
    _refresh?.cancel();
    _live?.close();
    _text.dispose();
    super.dispose();
  }

  Future<void> _load({bool quiet = false}) async {
    if (!quiet) setState(() { _loading = true; _error = null; });
    try {
      final event = await ref.read(eventProvider.future);
      final api = ref.read(apiClientProvider);
      final categories = await api.get('/events/${event['id']}/categories', query: {'type': 'question'});
      final data = await api.get('/questions', query: {'tab': _tab});
      if (!mounted) return;
      setState(() {
        _categories = [for (final item in (categories['categories'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _categoryId ??= _categories.isEmpty ? null : _categories.first['id']?.toString();
        _questions = [for (final item in (data['questions'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _loading = false;
      });
    } catch (error) {
      if (!mounted || quiet) return;
      setState(() { _error = error is ApiException ? error.message : 'Could not load questions.'; _loading = false; });
    }
  }

  Future<void> _submit() async {
    if (_text.text.trim().length < 10 || _categoryId == null) return;
    setState(() => _busy = true);
    try {
      final data = await ref.read(apiClientProvider).post('/questions', {
        'text': _text.text.trim(),
        'category_id': _categoryId,
        'session_id': _sessionId,
      });
      _text.clear();
      setState(() { _sessionId = null; _sessionTitle = null; _info = data['message']?.toString(); _busy = false; });
      await _load(quiet: true);
    } catch (error) {
      if (!mounted) return;
      setState(() { _busy = false; _error = error is ApiException ? error.message : 'Could not submit.'; });
    }
  }

  Future<void> _upvote(Map<String, dynamic> item) async {
    final id = item['id'].toString();
    final was = item['has_upvoted'] == true;
    setState(() {
      item['has_upvoted'] = !was;
      item['upvote_count'] = (item['upvote_count'] as int? ?? 0) + (was ? -1 : 1);
    });
    try {
      final data = was
          ? await ref.read(apiClientProvider).delete('/questions/$id/upvote')
          : await ref.read(apiClientProvider).put('/questions/$id/upvote');
      if (!mounted) return;
      setState(() {
        item['has_upvoted'] = data['upvoted'] == true;
        item['upvote_count'] = data['upvote_count'];
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        item['has_upvoted'] = was;
        item['upvote_count'] = (item['upvote_count'] as int? ?? 0) + (was ? 1 : -1);
        _error = error is ApiException ? error.message : 'Could not update the vote.';
      });
    }
  }

  Future<void> _pickSession() async {
    final data = await ref.read(apiClientProvider).get('/questions/sessions-today');
    final sessions = [for (final item in (data['sessions'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
    if (!mounted) return;
    final selected = await showModalBottomSheet<Map<String, dynamic>?>(
      context: context,
      backgroundColor: Colors.white,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          children: [
            const ListTile(title: Text('Link to session', style: TextStyle(fontWeight: FontWeight.w800))),
            ListTile(title: const Text('No session'), onTap: () => Navigator.pop(context, {})),
            if (sessions.isEmpty) const ListTile(title: Text('No sessions today.')),
            for (final session in sessions)
              ListTile(title: Text(session['title']?.toString() ?? ''), onTap: () => Navigator.pop(context, session)),
          ],
        ),
      ),
    );
    if (selected == null) return;
    setState(() {
      _sessionId = selected['id']?.toString();
      _sessionTitle = selected['title']?.toString();
    });
  }

  void _reply(Map<String, dynamic> item) {
    final answer = item['answer'];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      showDragHandle: true,
      builder: (context) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(item['text']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
            const SizedBox(height: 8),
            if (answer is Map) ...[
              Text('${answer['author_name'] ?? ''} · ${answer['author_role'] ?? ''}', style: const TextStyle(color: AppTokens.textMuted)),
              const SizedBox(height: 6),
              Text(answer['text']?.toString() ?? ''),
            ] else
              const Text('No answer yet.', style: TextStyle(color: AppTokens.textMuted)),
          ],
        ),
      ),
    );
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
                  const Expanded(child: Text('Ask Q&A', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  IconButton(onPressed: () => context.push('/qna/mine'), icon: const Icon(Icons.chat_bubble_outline, color: AppTokens.accentGold)),
                ],
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(22)),
                child: const Row(children: [
                  CircleAvatar(backgroundColor: AppTokens.primary, child: Icon(Icons.chat_bubble_outline, color: Colors.white)),
                  SizedBox(width: 12),
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('Ask the Experts', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
                    Text('Submit your questions and vote for top discussions', style: TextStyle(color: Color(0xFFC5D0EA))),
                  ])),
                ]),
              ),
              const SizedBox(height: 14),
              WhiteCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Write your question', style: TextStyle(fontWeight: FontWeight.w800)),
                    const SizedBox(height: 8),
                    TextField(
                      controller: _text,
                      minLines: 3,
                      maxLines: 3,
                      maxLength: 500,
                      decoration: const InputDecoration(hintText: 'Type your question for the speaker...', counterText: ''),
                      onChanged: (_) => setState(() {}),
                    ),
                    Align(alignment: Alignment.centerRight, child: Text('${_text.text.trim().length}/500', style: const TextStyle(color: AppTokens.textMuted, fontSize: 12))),
                    SizedBox(
                      height: 36,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          for (final category in _categories)
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(category['name']?.toString() ?? ''),
                                selected: _categoryId == category['id'],
                                onSelected: (_) => setState(() => _categoryId = category['id']?.toString()),
                              ),
                            ),
                        ],
                      ),
                    ),
                    TextButton(onPressed: _pickSession, child: Text(_sessionTitle == null ? 'Link to session' : 'Linked: $_sessionTitle')),
                    if (_error != null) Text(_error!, style: const TextStyle(color: AppTokens.danger)),
                    if (_info != null) Text(_info!, style: const TextStyle(color: AppTokens.success)),
                    PrimaryButton(label: 'Submit Question', icon: Icons.send, showArrow: false, loading: _busy, onPressed: _text.text.trim().length < 10 ? null : _submit),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  for (final tab in ['popular', 'recent', 'answered'])
                    Expanded(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: ChoiceChip(
                          label: Text(tab[0].toUpperCase() + tab.substring(1)),
                          selected: _tab == tab,
                          selectedColor: AppTokens.accentGold,
                          onSelected: (_) { setState(() => _tab = tab); _load(); },
                        ),
                      ),
                    ),
                ],
              ),
              if (_loading) const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
              if (!_loading && _questions.isEmpty) EmptyPanel(message: _tab == 'answered' ? 'No answered questions yet.' : 'No questions yet.'),
              for (final item in _questions)
                _QuestionTile(item: item, onUpvote: () => _upvote(item), onReply: () => _reply(item)),
            ],
          ),
        ),
      ),
    );
  }
}

class MyQuestionsScreen extends ConsumerWidget {
  const MyQuestionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mine = ref.watch(_mineProvider);
    const labels = {'pending': 'Pending', 'published': 'Published', 'answered': 'Answered', 'rejected': 'Rejected', 'hidden': 'Hidden'};
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: mine.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(_mineProvider)),
            data: (data) {
              final questions = data['questions'] as List? ?? [];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Row(children: [AppBackButton(), Expanded(child: Text('My Questions', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)))]),
                  if (questions.isEmpty) const Padding(padding: EdgeInsets.only(top: 16), child: EmptyPanel(message: 'You have not asked a question yet.')),
                  for (final item in questions)
                    if (item is Map)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: WhiteCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(labels[item['status']] ?? item['status'].toString(), style: const TextStyle(color: AppTokens.primary, fontWeight: FontWeight.w800)),
                              const SizedBox(height: 6),
                              Text(item['text']?.toString() ?? ''),
                              if ((item['reject_reason'] ?? '').toString().isNotEmpty)
                                Text(item['reject_reason'].toString(), style: const TextStyle(color: AppTokens.danger)),
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

final _mineProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/questions/mine');
});

class _QuestionTile extends StatelessWidget {
  const _QuestionTile({required this.item, required this.onUpvote, required this.onReply});
  final Map<String, dynamic> item;
  final VoidCallback onUpvote;
  final VoidCallback onReply;

  @override
  Widget build(BuildContext context) {
    final answered = item['status'] == 'answered';
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: answered ? const Color(0xFFFFFDF6) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: answered ? const Color(0xFFF5D48A) : AppTokens.border),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onUpvote,
            child: Column(children: [
              Icon(Icons.keyboard_arrow_up, color: item['has_upvoted'] == true ? AppTokens.primary : AppTokens.textMuted),
              Text('${item['upvote_count'] ?? 0}', style: const TextStyle(fontWeight: FontWeight.w800, color: AppTokens.primary)),
            ]),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(spacing: 6, children: [
                  Text((item['category'] as Map?)?['name']?.toString() ?? '', style: const TextStyle(color: AppTokens.primary, fontWeight: FontWeight.w800)),
                  if (answered) const Text('Answered', style: TextStyle(color: AppTokens.success, fontWeight: FontWeight.w800)),
                ]),
                const SizedBox(height: 4),
                Text(item['text']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
                Row(children: [
                  Expanded(child: Text(item['footer_name']?.toString() ?? '', style: const TextStyle(color: AppTokens.textMuted))),
                  TextButton(onPressed: onReply, child: const Text('↩ Reply')),
                ]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
