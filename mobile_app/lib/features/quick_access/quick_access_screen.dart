import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';

class QuickAccessScreen extends StatefulWidget {
  const QuickAccessScreen({super.key});

  @override
  State<QuickAccessScreen> createState() => _QuickAccessScreenState();
}

class _Tool {
  const _Tool(this.title, this.description, this.tag, this.route, this.icon);
  final String title;
  final String description;
  final String tag;
  final String route;
  final IconData icon;
}

const _tools = [
  _Tool('Agenda', 'View full congress schedule', 'Event', '/agenda', Icons.calendar_month_outlined),
  _Tool('Speakers', 'Explore global medical experts', 'Event', '/speakers', Icons.groups_outlined),
  _Tool('Name Tag', 'Access your digital badge', 'Tools', '/name-tag', Icons.badge_outlined),
  _Tool('Venue', 'Location, facilities and directions', 'Event', '/venue', Icons.place_outlined),
  _Tool('Voting', 'Join live polls and see results', 'Interactive', '/voting', Icons.how_to_vote_outlined),
  _Tool('Ask Q&A', 'Ask questions and upvote topics', 'Interactive', '/qna', Icons.forum_outlined),
  _Tool('Resources', 'Presentations, documents and media', 'Tools', '/resources', Icons.folder_open_outlined),
  _Tool('Exhibitors', 'Meet congress partners and sponsors', 'Event', '/exhibitors', Icons.storefront_outlined),
  _Tool('AI Assistant', 'Ask about sessions, speakers and the venue', 'Tools', '/assistant', Icons.auto_awesome),
];

class _QuickAccessScreenState extends State<QuickAccessScreen> {
  final _search = TextEditingController();
  String _chip = 'All';
  bool _grid = true;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  List<_Tool> get _visible {
    final query = _search.text.trim().toLowerCase();
    return _tools.where((tool) {
      final tagOk = _chip == 'All' || tool.tag == _chip;
      final textOk = query.isEmpty || tool.title.toLowerCase().contains(query) || tool.description.toLowerCase().contains(query);
      return tagOk && textOk;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final tools = _visible;
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
            children: [
              Row(
                children: [
                  const AppBackButton(),
                  const Expanded(child: Text('Quick Access', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                  IconButton(
                    onPressed: () => setState(() => _grid = !_grid),
                    icon: Icon(_grid ? Icons.view_list : Icons.grid_view, color: AppTokens.accentGold),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Container(
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
                          Text('Explore Congress Tools', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 16)),
                          Text('Everything you need for the full event experience', style: TextStyle(color: Colors.white70, fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              WhiteCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: _search,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(hintText: 'Search quick access', prefixIcon: Icon(Icons.search), filled: true, fillColor: AppTokens.surfaceMuted),
                    ),
                    const SizedBox(height: 12),
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: Row(
                        children: [
                          for (final chip in ['All', 'Event', 'Interactive', 'Tools'])
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: ChoiceChip(
                                label: Text(chip),
                                selected: _chip == chip,
                                onSelected: (_) => setState(() => _chip = chip),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    if (tools.isEmpty)
                      const EmptyPanel(message: 'No tools match your search.')
                    else if (_grid)
                      GridView.count(
                        crossAxisCount: 2,
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        mainAxisSpacing: 10,
                        crossAxisSpacing: 10,
                        childAspectRatio: 1.15,
                        children: [for (final tool in tools) _ToolCard(tool: tool)],
                      )
                    else
                      Column(children: [for (final tool in tools) _ToolCard(tool: tool)]),
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

class _ToolCard extends StatelessWidget {
  const _ToolCard({required this.tool});
  final _Tool tool;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () => context.push(tool.route),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: AppTokens.surfaceMuted, borderRadius: BorderRadius.circular(16)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(tool.icon, color: AppTokens.primary),
            const SizedBox(height: 8),
            Text(tool.title, style: const TextStyle(fontWeight: FontWeight.w800)),
            Text(tool.description, maxLines: 2, style: const TextStyle(color: AppTokens.textMuted, fontSize: 12)),
            const SizedBox(height: 6),
            Text(tool.tag, style: const TextStyle(color: AppTokens.primary, fontSize: 11, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}
