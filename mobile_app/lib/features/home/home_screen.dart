import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/theme/app_theme.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';

final eventProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/events/current');
});

final meProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) {
  return ref.watch(apiClientProvider).get('/me');
});

final unreadProvider = FutureProvider.autoDispose<int>((ref) async {
  final data = await ref.watch(apiClientProvider).get('/notifications/unread-count');
  return (data['count'] as num?)?.toInt() ?? 0;
});

final upcomingProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final event = await ref.watch(eventProvider.future);
  return ref.watch(apiClientProvider).get('/events/${event['id']}/sessions/upcoming', query: {'limit': 5});
});

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final event = ref.watch(eventProvider);
    final me = ref.watch(meProvider);
    final unread = ref.watch(unreadProvider);
    final upcoming = ref.watch(upcomingProvider);
    final name = me.maybeWhen(data: (user) => user['full_name']?.toString() ?? 'there', orElse: () => '...');

    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: RefreshIndicator(
            onRefresh: () async {
              ref.invalidate(eventProvider);
              ref.invalidate(meProvider);
              ref.invalidate(unreadProvider);
              ref.invalidate(upcomingProvider);
              await ref.read(upcomingProvider.future);
            },
            child: ListView(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 88),
              children: [
                Row(
                  children: [
                    Expanded(child: Text('NESTLÉ MEDICAL CONGRESS', style: AppTheme.overline(color: AppTokens.textOnDarkMuted))),
                    _Bell(count: unread.maybeWhen(data: (value) => value, orElse: () => 0)),
                  ],
                ),
                const SizedBox(height: 16),
                const Text('Welcome Back,', style: TextStyle(color: AppTokens.textOnDarkMuted, fontSize: 14)),
                Text('$name 👋', style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white)),
                const SizedBox(height: 16),
                _SearchBar(onSubmit: (query) => context.push('/search?q=${Uri.encodeQueryComponent(query)}')),
                const SizedBox(height: 16),
                event.when(
                  loading: () => const _Skeleton(height: 120),
                  error: (error, _) => ErrorPanel(message: _message(error), onRetry: () => ref.invalidate(eventProvider)),
                  data: (data) => _FeaturedEvent(event: data),
                ),
                SectionHeader(title: 'Quick Access', action: 'View All ›', onAction: () => context.push('/quick-access')),
                const _QuickGrid(),
                SectionHeader(title: 'Upcoming Sessions', action: 'View All ›', onAction: () => context.push('/agenda')),
                upcoming.when(
                  loading: () => const _Skeleton(height: 88),
                  error: (error, _) => ErrorPanel(message: _message(error), onRetry: () => ref.invalidate(upcomingProvider)),
                  data: (data) {
                    final sessions = (data['sessions'] as List?) ?? [];
                    if (sessions.isEmpty) {
                      return EmptyPanel(message: data['message']?.toString() ?? 'No upcoming sessions.');
                    }
                    return Column(
                      children: [
                        for (final item in sessions) SessionTile(session: Map<String, dynamic>.from(item as Map)),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/assistant'),
        backgroundColor: AppTokens.primary,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.auto_awesome),
        label: const Text('Ask AI'),
      ),
      bottomNavigationBar: NavigationBar(
        backgroundColor: AppTokens.bgNavy900,
        indicatorColor: AppTokens.primary.withValues(alpha: 0.25),
        selectedIndex: 0,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined, color: Colors.white), selectedIcon: Icon(Icons.home, color: AppTokens.accentGold), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.person_outline, color: Colors.white), label: 'Profile'),
        ],
        onDestinationSelected: (index) {
          if (index == 1) context.go('/profile');
        },
      ),
    );
  }
}

String _message(Object error) => error is ApiException ? error.message : 'Something went wrong.';

class _Bell extends StatelessWidget {
  const _Bell({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(14)),
          child: IconButton(
            onPressed: () => context.push('/notifications'),
            icon: const Icon(Icons.notifications_none, color: Colors.white, size: 20),
          ),
        ),
        if (count > 0)
          const Positioned(right: 8, top: 8, child: CircleAvatar(radius: 4, backgroundColor: AppTokens.danger)),
      ],
    );
  }
}

class _SearchBar extends StatefulWidget {
  const _SearchBar({required this.onSubmit});
  final ValueChanged<String> onSubmit;

  @override
  State<_SearchBar> createState() => _SearchBarState();
}

class _SearchBarState extends State<_SearchBar> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: _controller,
      style: const TextStyle(color: AppTokens.textPrimary),
      textInputAction: TextInputAction.search,
      onSubmitted: widget.onSubmit,
      decoration: InputDecoration(
        hintText: 'Search sessions, speakers, topics...',
        hintStyle: const TextStyle(color: AppTokens.textMuted, fontSize: 13),
        filled: true,
        fillColor: Colors.white,
        prefixIcon: const Icon(Icons.search, color: AppTokens.textMuted),
        suffixIcon: Padding(
          padding: const EdgeInsets.all(6),
          child: InkWell(
            onTap: () => widget.onSubmit(_controller.text),
            child: const CircleAvatar(backgroundColor: AppTokens.primaryCyan, child: Icon(Icons.arrow_forward, color: Colors.white, size: 18)),
          ),
        ),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: BorderSide.none),
      ),
    );
  }
}

class _FeaturedEvent extends StatelessWidget {
  const _FeaturedEvent({required this.event});
  final Map<String, dynamic> event;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
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
                Text(event['title']?.toString() ?? '', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                Text(event['description']?.toString() ?? event['tagline']?.toString() ?? ''),
              ],
            ),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(colors: [Color(0xFF1D4ED8), Color(0xFF38BDF8)]),
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('FEATURED EVENT', style: AppTheme.overline()),
                  const SizedBox(height: 6),
                  Text(event['name']?.toString() ?? '', maxLines: 2, style: const TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 6),
                  Text(
                    '${event['dates_label'] ?? ''} • ${event['city'] ?? ''}, ${event['country'] ?? ''}',
                    style: const TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                ],
              ),
            ),
            const CircleAvatar(backgroundColor: Colors.white24, child: Icon(Icons.spa_outlined, color: Colors.white)),
          ],
        ),
      ),
    );
  }
}

class _QuickGrid extends StatelessWidget {
  const _QuickGrid();

  static const tiles = [
    ('Agenda', Icons.calendar_month_outlined),
    ('Speakers', Icons.groups_outlined),
    ('Name Tag', Icons.badge_outlined),
    ('Venue', Icons.place_outlined),
    ('Voting', Icons.how_to_vote_outlined),
    ('Ask Q&A', Icons.forum_outlined),
    ('Resources', Icons.folder_open_outlined),
    ('Exhibitors', Icons.storefront_outlined),
  ];

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 4,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 8,
      crossAxisSpacing: 8,
      childAspectRatio: 0.78,
      children: [
        for (final tile in tiles)
          InkWell(
            onTap: () {
              const routes = {'Agenda': '/agenda', 'Speakers': '/speakers', 'Name Tag': '/name-tag', 'Venue': '/venue', 'Voting': '/voting', 'Ask Q&A': '/qna', 'Resources': '/resources', 'Exhibitors': '/exhibitors'};
              context.push(routes[tile.$1] ?? '/soon?title=${Uri.encodeQueryComponent(tile.$1)}');
            },
            child: Column(
              children: [
                Container(
                  width: 52,
                  height: 52,
                  decoration: BoxDecoration(
                    gradient: AppTokens.buttonGradient,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(tile.$2, color: Colors.white, size: 22),
                ),
                const SizedBox(height: 6),
                Text(tile.$1, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 11)),
              ],
            ),
          ),
      ],
    );
  }
}

class _Skeleton extends StatelessWidget {
  const _Skeleton({required this.height});
  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(16)),
    );
  }
}

class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key, required this.query});

  final String query;

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  late final TextEditingController _controller = TextEditingController(text: widget.query);
  late Future<Map<String, dynamic>> _future;

  @override
  void initState() {
    super.initState();
    _future = _run(widget.query);
  }

  Future<Map<String, dynamic>> _run(String query) {
    if (query.trim().isEmpty) return Future.value({'sessions': []});
    return ref.read(apiClientProvider).get('/search', query: {'q': query.trim()});
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    const AppBackButton(),
                    const SizedBox(width: 12),
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: const TextStyle(color: AppTokens.textPrimary),
                        decoration: const InputDecoration(filled: true, fillColor: Colors.white, hintText: 'Search sessions'),
                        onSubmitted: (value) => setState(() => _future = _run(value)),
                      ),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: FutureBuilder<Map<String, dynamic>>(
                  future: _future,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState == ConnectionState.waiting) return const Center(child: CircularProgressIndicator());
                    if (snapshot.hasError) {
                      return ErrorPanel(message: _message(snapshot.error!), onRetry: () => setState(() => _future = _run(_controller.text)));
                    }
                    final sessions = (snapshot.data?['sessions'] as List?) ?? [];
                    final exhibitors = (snapshot.data?['exhibitors'] as List?) ?? [];
                    if (sessions.isEmpty && exhibitors.isEmpty) return const EmptyPanel(message: 'No results match your search.');
                    return ListView(
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      children: [
                        for (final item in sessions) SessionTile(session: Map<String, dynamic>.from(item as Map)),
                        for (final item in exhibitors)
                          if (item is Map)
                            ListTile(
                              leading: const Icon(Icons.storefront_outlined, color: Colors.white),
                              title: Text(item['name']?.toString() ?? '', style: const TextStyle(color: Colors.white)),
                              subtitle: Text(item['booth'] == null ? 'Exhibitor' : 'Booth ${item['booth']}', style: const TextStyle(color: Colors.white70)),
                              onTap: () => context.push('/exhibitors/${item['id']}'),
                            ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class SoonScreen extends StatelessWidget {
  const SoonScreen({super.key, required this.title});
  final String title;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const AppBackButton(),
                const SizedBox(height: 24),
                Text(title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(color: Colors.white)),
                const SizedBox(height: 12),
                const EmptyPanel(message: 'This section is next. Login, registration, and Home are the screens in this build.'),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

