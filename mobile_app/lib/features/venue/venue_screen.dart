import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_exception.dart';
import '../../core/theme/app_tokens.dart';
import '../../shared/widgets/congress_widgets.dart';
import '../auth/auth_controller.dart';
import '../home/home_screen.dart';

class VenueScreen extends ConsumerWidget {
  const VenueScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final venue = ref.watch(_venueProvider);
    return Scaffold(
      body: NavyBackground(
        child: SafeArea(
          child: venue.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                children: [
                  const Align(alignment: Alignment.centerLeft, child: AppBackButton()),
                  const SizedBox(height: 16),
                  ErrorPanel(message: error is ApiException ? error.message : 'Could not load the venue.', onRetry: () => ref.invalidate(_venueProvider)),
                ],
              ),
            ),
            data: (place) {
              final facilities = place['facilities'] as List? ?? [];
              final notices = place['notices'] as List? ?? [];
              return ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                children: [
                  Row(
                    children: [
                      const AppBackButton(),
                      const Expanded(child: Text('Venue', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700))),
                      IconButton(
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(place['directions_url']?.toString() ?? 'Directions unavailable')));
                        },
                        icon: const Icon(Icons.navigation, color: AppTokens.accentGold),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(place['name']?.toString() ?? '', style: const TextStyle(color: Colors.white, fontSize: 26, fontWeight: FontWeight.w800)),
                  const SizedBox(height: 6),
                  Text('📅 ${place['dates_label'] ?? ''}', style: const TextStyle(color: AppTokens.textOnDarkMuted)),
                  const SizedBox(height: 14),
                  WhiteCard(
                    child: Row(
                      children: [
                        const Icon(Icons.place, color: AppTokens.primary),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('VENUE ADDRESS', style: TextStyle(color: AppTokens.accentGold, fontSize: 11, fontWeight: FontWeight.w800)),
                              Text(place['address']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (place['map_available'] == true)
                    Container(
                      height: 180,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(color: const Color(0xFFDBE7F5), borderRadius: BorderRadius.circular(22)),
                      child: const Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Text('Map Preview', style: TextStyle(fontWeight: FontWeight.w800)),
                          SizedBox(height: 8),
                          CircleAvatar(backgroundColor: AppTokens.accentGold, child: Icon(Icons.place, color: Colors.white)),
                        ],
                      ),
                    )
                  else
                    const EmptyPanel(message: 'Map unavailable'),
                  const SizedBox(height: 12),
                  WhiteCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Venue Facilities', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                        const SizedBox(height: 12),
                        GridView.count(
                          crossAxisCount: 2,
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          childAspectRatio: 3.2,
                          mainAxisSpacing: 8,
                          crossAxisSpacing: 8,
                          children: [
                            for (final item in facilities)
                              if (item is Map)
                                Container(
                                  alignment: Alignment.centerLeft,
                                  padding: const EdgeInsets.symmetric(horizontal: 10),
                                  decoration: BoxDecoration(color: const Color(0xFFF4F7FB), borderRadius: BorderRadius.circular(14)),
                                  child: Text(item['label']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w700)),
                                ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  for (final note in notices)
                    Padding(
                      padding: const EdgeInsets.only(top: 10),
                      child: WhiteCard(child: Text(note is Map ? (note['title']?.toString() ?? '') : note.toString())),
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

final _venueProvider = FutureProvider.autoDispose<Map<String, dynamic>>((ref) async {
  final event = await ref.watch(eventProvider.future);
  return ref.watch(apiClientProvider).get('/events/${event['id']}/venue');
});
