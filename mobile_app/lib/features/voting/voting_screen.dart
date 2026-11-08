import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_exception.dart';
import '../../core/network/realtime_client.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';

class VotingScreen extends ConsumerStatefulWidget {
  const VotingScreen({super.key});

  @override
  ConsumerState<VotingScreen> createState() => _VotingScreenState();
}

class _VotingScreenState extends ConsumerState<VotingScreen> {
  final _page = PageController();
  List<Map<String, dynamic>> _polls = [];
  final Map<String, String> _choices = {};
  int _index = 0;
  bool _loading = true;
  bool _busy = false;
  Object? _error;
  String? _info;
  Timer? _pollTimer;
  RealtimeClient? _live;

  @override
  void initState() {
    super.initState();
    _load();
    _live = RealtimeClient(ref.read(apiClientProvider));
    _live!.connect((event) {
      if (event['type'] == 'poll.results_updated' || event['type'] == 'poll.activated' || event['type'] == 'poll.closed') {
        _load(quiet: true);
      }
    });
    _pollTimer = Timer.periodic(const Duration(seconds: 5), (_) {
      if (_live?.connected != true) _load(quiet: true);
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    _live?.close();
    _page.dispose();
    super.dispose();
  }

  Future<void> _load({bool quiet = false}) async {
    if (!quiet) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final data = await ref.read(apiClientProvider).get('/polls/active');
      final raw = data['value'];
      if (!mounted) return;
      setState(() {
        _polls = [for (final item in (raw as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _loading = false;
        _error = null;
      });
    } catch (error) {
      if (!mounted || quiet) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _submit(Map<String, dynamic> poll) async {
    final choice = _choices[poll['id']];
    if (choice == null) return;
    setState(() => _busy = true);
    try {
      final data = await ref.read(apiClientProvider).post(
        '/polls/${poll['id']}/votes',
        {'option_ids': [choice]},
        headers: {'Idempotency-Key': DateTime.now().microsecondsSinceEpoch.toString()},
      );
      final updated = data['poll'];
      if (!mounted) return;
      setState(() {
        if (updated is Map) _polls[_index] = Map<String, dynamic>.from(updated);
        _choices.remove(poll['id']);
        _info = 'Vote submitted';
        _busy = false;
      });
    } catch (error) {
      final code = error is ApiException ? error.code : null;
      if (code == 'ALREADY_VOTED' || code == 'POLL_CLOSED' || code == 'POLL_NOT_ACTIVE') await _load(quiet: true);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _info = null;
        _error = error;
      });
    }
  }

  void _move(int delta) {
    if (_polls.isEmpty) return;
    final next = (_index + delta + _polls.length) % _polls.length;
    setState(() => _index = next);
    _page.animateToPage(next, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: _loading
              ? const Center(child: CircularProgressIndicator())
              : _error != null && _polls.isEmpty
                  ? Padding(
                      padding: const EdgeInsets.all(20),
                      child: ErrorPanel(message: _error is ApiException ? (_error as ApiException).message : 'Could not load polls.', onRetry: _load),
                    )
                  : ListView(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                      children: [
                        Row(
                          children: [
                            const AppBackButton(),
                            const Expanded(child: Text('Live Voting', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                            IconButton(onPressed: () => context.push('/voting/history'), icon: const Icon(Icons.ballot_outlined, color: AppTokens.accentGold)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Container(
                          padding: const EdgeInsets.all(16),
                          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(22)),
                          child: const Row(
                            children: [
                              CircleAvatar(backgroundColor: AppTokens.accentGold, child: Icon(Icons.bar_chart, color: Colors.white)),
                              SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text('Audience Interaction', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w800)),
                                Text('Swipe polls, choose answers, and submit your vote', style: TextStyle(color: Color(0xFFC5D0EA))),
                              ])),
                            ],
                          ),
                        ),
                        if (_polls.isEmpty)
                          const Padding(padding: EdgeInsets.only(top: 16), child: EmptyPanel(message: 'No active polls right now. Polls will appear here during sessions.')),
                        if (_polls.isNotEmpty) ...[
                          const SizedBox(height: 12),
                          SizedBox(
                            height: 420,
                            child: PageView.builder(
                              controller: _page,
                              itemCount: _polls.length,
                              onPageChanged: (value) => setState(() => _index = value),
                              itemBuilder: (context, index) => _PollCard(
                                poll: _polls[index],
                                choice: _choices[_polls[index]['id']],
                                info: index == _index ? _info : null,
                                onSelect: (optionId) => setState(() => _choices[_polls[index]['id'].toString()] = optionId),
                              ),
                            ),
                          ),
                          Row(
                            children: [
                              _Arrow(icon: Icons.chevron_left, onPressed: () => _move(-1)),
                              const SizedBox(width: 8),
                              Expanded(child: _actionButton()),
                              const SizedBox(width: 8),
                              _Arrow(icon: Icons.chevron_right, onPressed: () => _move(1)),
                            ],
                          ),
                        ],
                      ],
                    ),
        ),
      ),
    );
  }

  Widget _actionButton() {
    final poll = _polls[_index];
    final voted = poll['has_voted'] == true;
    final choice = _choices[poll['id']];
    final canSubmit = poll['status'] == 'active' && !voted && choice != null;
    final label = canSubmit ? 'Submit Vote' : (!voted || _index < _polls.length - 1 ? 'Next Poll' : 'Voted ✓');
    return PrimaryButton(label: label, showArrow: false, loading: _busy, onPressed: label == 'Voted ✓' ? null : () => canSubmit ? _submit(poll) : _move(1));
  }
}

class PollHistoryScreen extends ConsumerWidget {
  const PollHistoryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final history = ref.watch(_historyProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: history.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(_historyProvider)),
            data: (data) {
              final polls = data['value'] as List? ?? [];
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Row(children: [AppBackButton(), Expanded(child: Text('Poll History', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)))]),
                  if (polls.isEmpty) const Padding(padding: EdgeInsets.only(top: 16), child: EmptyPanel(message: 'No closed polls yet.')),
                  for (final poll in polls)
                    if (poll is Map)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: WhiteCard(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(poll['question']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w800)),
                              Text('${poll['total_votes'] ?? 0} total votes', style: const TextStyle(color: AppTokens.textMuted)),
                              for (final option in (poll['options'] as List? ?? []))
                                if (option is Map)
                                  Padding(
                                    padding: const EdgeInsets.only(top: 6),
                                    child: Row(children: [Expanded(child: Text(option['label']?.toString() ?? '')), Text(option['percent'] == null ? '' : '${option['percent']}%')]),
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

final _historyProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/polls/history');
});

class _PollCard extends StatelessWidget {
  const _PollCard({required this.poll, required this.choice, required this.onSelect, this.info});
  final Map<String, dynamic> poll;
  final String? choice;
  final ValueChanged<String> onSelect;
  final String? info;

  @override
  Widget build(BuildContext context) {
    final voted = poll['has_voted'] == true;
    final mine = ((poll['my_option_ids'] as List?) ?? []).map((item) => item.toString()).toSet();
    final status = poll['status']?.toString() ?? '';
    final chip = voted ? 'VOTED' : status == 'paused' ? 'PAUSED' : status == 'closed' ? 'CLOSED' : 'VOTING';
    final options = poll['options'] as List? ?? [];
    return WhiteCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('● $chip', style: TextStyle(color: voted ? AppTokens.success : status == 'closed' ? AppTokens.danger : AppTokens.accentGold, fontWeight: FontWeight.w800)),
            const SizedBox(width: 8),
            Text(poll['label']?.toString() ?? '', style: const TextStyle(color: AppTokens.textMuted)),
          ]),
          const SizedBox(height: 8),
          Text(poll['question']?.toString() ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(poll['total_votes'] != null ? '${poll['total_votes']} total votes' : (poll['results_message']?.toString() ?? ''), style: const TextStyle(color: AppTokens.textMuted)),
          if (info != null) Text(info!, style: const TextStyle(color: AppTokens.success)),
          for (final option in options)
            if (option is Map)
              _OptionTile(
                option: Map<String, dynamic>.from(option),
                selected: mine.contains(option['id'].toString()) || choice == option['id'].toString(),
                enabled: status == 'active' && !voted,
                onTap: () => onSelect(option['id'].toString()),
              ),
        ],
      ),
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({required this.option, required this.selected, required this.enabled, required this.onTap});
  final Map<String, dynamic> option;
  final bool selected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final percent = option['percent'];
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: InkWell(
        onTap: enabled ? onTap : null,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: selected ? AppTokens.primary : AppTokens.border),
            color: selected ? const Color(0xFFF4F8FF) : Colors.white,
          ),
          child: Column(
            children: [
              Row(children: [
                Icon(selected ? Icons.check_circle : Icons.circle_outlined, color: selected ? AppTokens.primary : AppTokens.textMuted, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text(option['label']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w700))),
                if (percent != null) Text('$percent%', style: const TextStyle(fontWeight: FontWeight.w800)),
              ]),
              if (percent != null) ...[
                const SizedBox(height: 6),
                LinearProgressIndicator(value: (percent as num) / 100, minHeight: 6, color: AppTokens.primary, backgroundColor: AppTokens.border),
                Align(alignment: Alignment.centerRight, child: Text('${option['votes']} votes', style: const TextStyle(color: AppTokens.textMuted, fontSize: 12))),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _Arrow extends StatelessWidget {
  const _Arrow({required this.icon, required this.onPressed});
  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(onTap: onPressed, borderRadius: BorderRadius.circular(14), child: SizedBox(width: 44, height: 44, child: Icon(icon, color: AppTokens.primary))),
    );
  }
}
