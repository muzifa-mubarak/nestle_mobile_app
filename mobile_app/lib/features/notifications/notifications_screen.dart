import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../home/home_screen.dart';

class NotificationsScreen extends ConsumerStatefulWidget {
  const NotificationsScreen({super.key});

  @override
  ConsumerState<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends ConsumerState<NotificationsScreen> {
  bool _loading = true;
  Object? _error;
  List<Map<String, dynamic>> _items = [];

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
      final data = await ref.read(apiClientProvider).get('/notifications');
      if (!mounted) return;
      setState(() {
        _items = [for (final item in (data['notifications'] as List? ?? [])) if (item is Map) Map<String, dynamic>.from(item)];
        _loading = false;
      });
      ref.invalidate(unreadProvider);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = error;
        _loading = false;
      });
    }
  }

  Future<void> _markAll() async {
    await ref.read(apiClientProvider).post('/notifications/read-all', {});
    await _load();
  }

  Future<void> _open(Map<String, dynamic> item) async {
    if (item['is_read'] != true) {
      await ref.read(apiClientProvider).patch('/notifications/${item['id']}', {});
    }
    if (!mounted) return;
    openDeepLink(context, item['deep_link']?.toString());
    await _load();
  }

  @override
  Widget build(BuildContext context) {
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
                    const Expanded(child: Text('Notifications', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                    TextButton(onPressed: _items.any((item) => item['is_read'] != true) ? _markAll : null, child: const Text('Mark all read', style: TextStyle(color: Colors.white))),
                  ],
                ),
              ),
              Expanded(
                child: _loading
                    ? const Center(child: CircularProgressIndicator(color: Colors.white))
                    : _error != null
                        ? ErrorPanel(message: _error is ApiException ? (_error! as ApiException).message : 'Could not load notifications.', onRetry: _load)
                        : _items.isEmpty
                            ? const EmptyPanel(message: "You're all caught up.")
                            : ListView(
                                padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                                children: [
                                  for (final item in _items)
                                    Card(
                                      color: item['is_read'] == true ? Colors.white : const Color(0xFFFFF8E8),
                                      margin: const EdgeInsets.only(bottom: 10),
                                      child: ListTile(
                                        leading: Icon(_icon(item['type']?.toString()), color: const Color(0xFF2F6BFF)),
                                        title: Text(item['title']?.toString() ?? '', style: TextStyle(fontWeight: item['is_read'] == true ? FontWeight.w500 : FontWeight.w800)),
                                        subtitle: Text(item['body']?.toString() ?? '', maxLines: 2, overflow: TextOverflow.ellipsis),
                                        trailing: Text(_when(item['created_at']?.toString()), style: const TextStyle(fontSize: 12)),
                                        onTap: () => _open(item),
                                      ),
                                    ),
                                ],
                              ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData _icon(String? type) {
    switch (type) {
      case 'qna':
        return Icons.forum_outlined;
      case 'resource':
        return Icons.folder_open_outlined;
      case 'poll':
        return Icons.how_to_vote_outlined;
      default:
        return Icons.campaign_outlined;
    }
  }

  String _when(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    final then = DateTime.tryParse(iso)?.toLocal();
    if (then == null) return '';
    final diff = DateTime.now().difference(then);
    if (diff.inMinutes < 1) return 'Now';
    if (diff.inHours < 1) return '${diff.inMinutes}m';
    if (diff.inDays < 1) return '${diff.inHours}h';
    if (diff.inDays < 7) return '${diff.inDays}d';
    return '${then.day}/${then.month}';
  }
}

void openDeepLink(BuildContext context, String? link) {
  if (link == null || link.isEmpty) return;
  final uri = Uri.tryParse(link);
  if (uri == null) return;
  final id = uri.pathSegments.isEmpty ? '' : uri.pathSegments.first;
  switch (uri.host) {
    case 'session':
      context.push(id.isEmpty ? '/agenda' : '/agenda/$id');
    case 'poll':
      context.push('/voting');
    case 'question':
      context.push('/qna');
    case 'qna':
      context.push('/qna/mine');
    case 'resource':
      context.push('/resources');
    case 'exhibitor':
      context.push(id.isEmpty ? '/exhibitors' : '/exhibitors/$id');
    case 'notifications':
      context.push('/notifications');
    case 'home':
      context.go('/home');
  }
}
