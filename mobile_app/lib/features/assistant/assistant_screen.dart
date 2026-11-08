import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/network/api_exception.dart';
import '../auth/auth_controller.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';

class AssistantScreen extends ConsumerStatefulWidget {
  const AssistantScreen({super.key});

  @override
  ConsumerState<AssistantScreen> createState() => _AssistantScreenState();
}

class _ChatMessage {
  _ChatMessage({
    required this.role,
    required this.text,
    this.references = const [],
    this.followups = const [],
    this.createdAt,
    this.pending = false,
    this.failed = false,
    this.retryText,
  });

  final String role;
  final String text;
  List<Map<String, dynamic>> references;
  List<String> followups;
  final DateTime? createdAt;
  bool pending;
  bool failed;
  String? retryText;
}

class _AssistantScreenState extends ConsumerState<AssistantScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final List<_ChatMessage> _messages = [];
  List<String> _suggestions = [];
  String _firstName = 'there';
  bool _loading = true;
  bool _sending = false;
  bool _offline = false;
  bool _disabled = false;
  String? _loadError;
  int _cooldown = 0;
  Timer? _cooldownTimer;

  @override
  void initState() {
    super.initState();
    _input.addListener(() => setState(() {}));
    _load();
  }

  @override
  void dispose() {
    _cooldownTimer?.cancel();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _loadError = null;
      _offline = false;
    });
    try {
      final api = ref.read(apiClientProvider);
      final results = await Future.wait([
        api.get('/me'),
        api.get('/ai/conversations/current'),
        api.get('/ai/suggestions'),
      ]);
      final name = results[0]['full_name']?.toString().trim() ?? '';
      final history = (results[1]['messages'] as List?) ?? [];
      final suggestions = (results[2]['suggestions'] as List?) ?? [];
      if (!mounted) return;
      setState(() {
        _firstName = name.isEmpty ? 'there' : name.split(' ').first;
        _messages
          ..clear()
          ..addAll(history.whereType<Map>().map(_fromApi));
        _suggestions = [for (final item in suggestions) item.toString()];
        _loading = false;
      });
      _scrollToEnd();
    } catch (error) {
      if (!mounted) return;
      final offline = error is! ApiException;
      setState(() {
        _loading = false;
        _offline = offline;
        _loadError = offline ? null : (error is ApiException ? error.message : 'Something went wrong.');
        if (error is ApiException && error.code == 'AI_DISABLED') _disabled = true;
      });
    }
  }

  _ChatMessage _fromApi(Map raw) {
    final item = Map<String, dynamic>.from(raw);
    return _ChatMessage(
      role: item['role']?.toString() ?? 'assistant',
      text: item['content']?.toString() ?? '',
      references: [for (final ref in (item['references'] as List? ?? [])) if (ref is Map) Map<String, dynamic>.from(ref)],
      followups: [for (final follow in (item['followups'] as List? ?? [])) follow.toString()],
      createdAt: DateTime.tryParse(item['created_at']?.toString() ?? '')?.toLocal(),
    );
  }

  Future<void> _send(String raw, {bool echoUser = true}) async {
    final text = raw.trim();
    if (text.isEmpty || _sending || _cooldown > 0 || _offline || _disabled) return;
    setState(() {
      if (echoUser) {
        _messages.add(_ChatMessage(role: 'user', text: text, createdAt: DateTime.now()));
      }
      _messages.add(_ChatMessage(role: 'assistant', text: '', pending: true));
      _sending = true;
    });
    _input.clear();
    _scrollToEnd();
    final started = DateTime.now();
    try {
      final data = await ref.read(apiClientProvider).post(
        '/ai/chat',
        {'message': text},
        receiveTimeout: const Duration(seconds: 40),
      );
      final elapsed = DateTime.now().difference(started);
      if (elapsed < const Duration(milliseconds: 400)) {
        await Future.delayed(const Duration(milliseconds: 400) - elapsed);
      }
      if (!mounted) return;
      setState(() {
        _messages.removeWhere((message) => message.pending);
        _messages.add(_fromApi({
          'role': 'assistant',
          'content': data['answer'],
          'references': data['references'],
          'followups': data['followups'],
          'created_at': data['created_at'],
        }));
        _sending = false;
      });
    } catch (error) {
      if (!mounted) return;
      final apiError = error is ApiException ? error : null;
      if (apiError?.code == 'AI_DISABLED') {
        setState(() {
          _messages.removeWhere((message) => message.pending);
          _disabled = true;
          _sending = false;
        });
        return;
      }
      if (apiError?.code == 'RATE_LIMITED') {
        _startCooldown(apiError?.retryAfter ?? _secondsIn(apiError?.message ?? ''));
      }
      setState(() {
        _messages.removeWhere((message) => message.pending);
        _offline = apiError == null;
        _messages.add(
          _ChatMessage(
            role: 'assistant',
            text: apiError?.message ?? "I couldn't reach the assistant. Please try again.",
            failed: true,
            retryText: text,
            createdAt: DateTime.now(),
          ),
        );
        _sending = false;
      });
    }
    _scrollToEnd();
  }

  void _retry(_ChatMessage message) {
    final text = message.retryText;
    if (text == null || _cooldown > 0) return;
    setState(() => _messages.remove(message));
    _send(text, echoUser: false);
  }

  int _secondsIn(String message) {
    final match = RegExp(r'(\d+)s').firstMatch(message);
    return int.tryParse(match?.group(1) ?? '') ?? 15;
  }

  void _startCooldown(int seconds) {
    _cooldownTimer?.cancel();
    setState(() => _cooldown = seconds.clamp(1, 3600));
    _cooldownTimer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (!mounted) {
        timer.cancel();
        return;
      }
      setState(() {
        _cooldown -= 1;
        if (_cooldown <= 0) timer.cancel();
      });
    });
  }

  Future<void> _clear() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear conversation?'),
        content: const Text('This removes the current chat from your account.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Clear')),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    try {
      await ref.read(apiClientProvider).delete('/ai/conversations/current');
      if (!mounted) return;
      setState(() => _messages.clear());
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error is ApiException ? error.message : 'Could not clear the chat.')));
    }
  }

  void _openReference(Map<String, dynamic> reference) {
    final id = reference['id']?.toString() ?? '';
    switch (reference['type']) {
      case 'session':
        context.push('/agenda/$id');
      case 'speaker':
        context.push('/speakers/$id');
      case 'venue':
        context.push('/venue');
      case 'resource':
        context.push('/resources');
      case 'exhibitor':
        context.push('/exhibitors/$id');
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
    });
  }

  bool get _hasConversation => _messages.any((message) => !message.pending);

  @override
  Widget build(BuildContext context) {
    final canSend = _input.text.trim().isNotEmpty && !_sending && _cooldown <= 0 && !_offline && !_disabled;
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
                child: Row(
                  children: [
                    const AppBackButton(),
                    const Expanded(child: Text('AI Assistant', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                    IconButton(
                      tooltip: 'Clear conversation',
                      onPressed: _messages.isEmpty ? null : _clear,
                      icon: const Icon(Icons.delete_outline, color: Colors.white),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(gradient: AppTokens.buttonGradient, borderRadius: BorderRadius.circular(20)),
                  child: const Row(
                    children: [
                      Icon(Icons.auto_awesome, color: Colors.white),
                      SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Congress Assistant', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
                            Text('Ask about your event, saved items, and where to find things', style: TextStyle(color: Colors.white70, fontSize: 12)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              Expanded(child: _body()),
              _composer(canSend),
            ],
          ),
        ),
      ),
    );
  }

  Widget _body() {
    if (_loading) {
      return ListView(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        children: const [
          _BubbleSkeleton(),
          _BubbleSkeleton(alignEnd: true),
          _BubbleSkeleton(),
        ],
      );
    }
    if (_disabled && _messages.isEmpty) {
      return const EmptyPanel(message: 'The assistant is not available right now.');
    }
    if (_loadError != null && _messages.isEmpty) {
      return ErrorPanel(message: _loadError!, onRetry: _load);
    }
    return ListView(
      controller: _scroll,
      padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
      children: [
        if (_offline) const _Banner(text: "You're offline"),
        if (!_hasConversation) ...[
          _Bubble(
            message: _ChatMessage(
              role: 'assistant',
              text: 'Hi $_firstName! I can answer from your account and the congress, and I can tell you which screen to open. What would you like to know?',
              createdAt: DateTime.now(),
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final suggestion in _suggestions)
                ActionChip(
                  label: Text(suggestion),
                  onPressed: _sending ? null : () => _send(suggestion),
                ),
            ],
          ),
        ],
        for (var index = 0; index < _messages.length; index++) ...[
          const SizedBox(height: 10),
          _Bubble(
            message: _messages[index],
            onRetry: _messages[index].failed && _cooldown <= 0 ? () => _retry(_messages[index]) : null,
            onOpen: _openReference,
            showFollowups: index == _messages.length - 1 && !_sending,
            onFollowup: _send,
          ),
        ],
      ],
    );
  }

  Widget _composer(bool canSend) {
    final length = _input.text.length;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(14, 4, 6, 4),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24)),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    enabled: !_offline && !_disabled && _cooldown <= 0,
                    minLines: 1,
                    maxLines: 4,
                    maxLength: 500,
                    buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                    decoration: const InputDecoration(
                      hintText: 'Ask about the congress...',
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      filled: false,
                    ),
                    onSubmitted: canSend ? _send : null,
                  ),
                ),
                Semantics(
                  label: 'Send',
                  button: true,
                  child: IconButton(
                    onPressed: canSend ? () => _send(_input.text) : null,
                    icon: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: canSend ? AppTokens.buttonGradient : null,
                        color: canSend ? null : AppTokens.border,
                        shape: BoxShape.circle,
                      ),
                      child: const Padding(
                        padding: EdgeInsets.all(8),
                        child: Icon(Icons.send, color: Colors.white, size: 18),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          if (length >= 450)
            Align(
              alignment: Alignment.centerRight,
              child: Text('$length/500', style: const TextStyle(color: AppTokens.textOnDarkMuted, fontSize: 11)),
            ),
          if (_cooldown > 0)
            Text("You're asking quickly. Try again in ${_cooldown}s.", style: const TextStyle(color: Colors.white70, fontSize: 12)),
          const Padding(
            padding: EdgeInsets.only(top: 4),
            child: Text('AI can make mistakes. Check the Agenda for final details.', style: TextStyle(color: AppTokens.textOnDarkMuted, fontSize: 11)),
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message, this.onRetry, this.onOpen, this.onFollowup, this.showFollowups = false});

  final _ChatMessage message;
  final VoidCallback? onRetry;
  final ValueChanged<Map<String, dynamic>>? onOpen;
  final ValueChanged<String>? onFollowup;
  final bool showFollowups;

  @override
  Widget build(BuildContext context) {
    final mine = message.role == 'user';
    final time = message.createdAt == null ? '' : DateFormat('hh:mm a').format(message.createdAt!);
    return Column(
      crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: mine ? MainAxisAlignment.end : MainAxisAlignment.start,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (!mine) ...[
              const CircleAvatar(radius: 14, backgroundColor: AppTokens.primary, child: Icon(Icons.auto_awesome, size: 14, color: Colors.white)),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: GestureDetector(
                onLongPress: message.pending || message.text.isEmpty
                    ? null
                    : () {
                        Clipboard.setData(ClipboardData(text: message.text));
                        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copied')));
                      },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    gradient: mine ? AppTokens.buttonGradient : null,
                    color: mine ? null : (message.failed ? const Color(0xFFFFF1F1) : AppTokens.surfaceMuted),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18),
                      topRight: const Radius.circular(18),
                      bottomLeft: Radius.circular(mine ? 18 : 4),
                      bottomRight: Radius.circular(mine ? 4 : 18),
                    ),
                    border: message.failed ? Border.all(color: AppTokens.danger) : null,
                  ),
                  child: message.pending
                      ? const _TypingDots()
                      : Text(message.text, style: TextStyle(color: mine ? Colors.white : AppTokens.textPrimary, fontSize: 13)),
                ),
              ),
            ),
          ],
        ),
        if (time.isNotEmpty && !message.pending)
          Padding(
            padding: EdgeInsets.only(top: 4, left: mine ? 0 : 36),
            child: Text(time, style: const TextStyle(color: AppTokens.textOnDarkMuted, fontSize: 11)),
          ),
        if (onRetry != null)
          TextButton(onPressed: onRetry, child: const Text('Retry')),
        if (!mine && message.references.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Column(
              children: [
                for (final reference in message.references.take(3))
                  Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Material(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(14),
                      child: ListTile(
                        dense: true,
                        leading: Icon(_icon(reference['type']?.toString()), color: AppTokens.primary),
                        title: Text(reference['label']?.toString() ?? 'Open', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
                        subtitle: Text(_label(reference['type']?.toString()), style: const TextStyle(fontSize: 11)),
                        onTap: () => onOpen?.call(reference),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        if (showFollowups && message.followups.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final follow in message.followups.take(2))
                  ActionChip(label: Text(follow), onPressed: () => onFollowup?.call(follow)),
              ],
            ),
          ),
      ],
    );
  }

  IconData _icon(String? type) {
    switch (type) {
      case 'speaker':
        return Icons.person_outline;
      case 'venue':
        return Icons.place_outlined;
      case 'resource':
        return Icons.folder_open_outlined;
      case 'exhibitor':
        return Icons.storefront_outlined;
      default:
        return Icons.calendar_month_outlined;
    }
  }

  String _label(String? type) {
    switch (type) {
      case 'speaker':
        return 'Speaker';
      case 'venue':
        return 'Venue';
      case 'resource':
        return 'Resource';
      case 'exhibitor':
        return 'Exhibitor';
      default:
        return 'Session';
    }
  }
}

class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final step = (_controller.value * 3).floor() % 3;
        return Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var index = 0; index < 3; index++)
              Container(
                width: 7,
                height: 7,
                margin: const EdgeInsets.symmetric(horizontal: 2),
                decoration: BoxDecoration(color: AppTokens.textMuted.withValues(alpha: index == step ? 1 : 0.35), shape: BoxShape.circle),
              ),
          ],
        );
      },
    );
  }
}

class _BubbleSkeleton extends StatelessWidget {
  const _BubbleSkeleton({this.alignEnd = false});
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: alignEnd ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        width: 180,
        height: 42,
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(18)),
      ),
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: AppTokens.warning, borderRadius: BorderRadius.circular(12)),
      child: Text(text, style: const TextStyle(fontWeight: FontWeight.w700)),
    );
  }
}
