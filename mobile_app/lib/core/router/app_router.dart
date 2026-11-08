import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/auth_controller.dart';
import '../../features/auth/register_screen.dart';
import '../../features/auth/verify_screen.dart';
import '../../features/auth/welcome_screen.dart';
import '../../features/agenda/agenda_screen.dart';
import '../../features/assistant/assistant_screen.dart';
import '../../features/home/home_screen.dart';
import '../../features/profile/profile_screen.dart';
import '../../features/name_tag/name_tag_screen.dart';
import '../../features/venue/venue_screen.dart';
import '../../features/qna/qna_screen.dart';
import '../../features/resources/resources_screen.dart';
import '../../features/voting/voting_screen.dart';
import '../../features/quick_access/quick_access_screen.dart';
import '../../features/exhibitors/exhibitors_screen.dart';
import '../../features/notifications/notifications_screen.dart';
import '../../features/speakers/speakers_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier<int>(0);
  ref.listen(authControllerProvider, (_, __) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/welcome',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authControllerProvider);
      if (!auth.ready) return null;
      final path = state.matchedLocation;
      const public = {'/welcome', '/register', '/verify-email', '/forgot-password'};
      if (!auth.signedIn && !public.contains(path)) return '/welcome';
      if (auth.signedIn && (path == '/welcome' || path == '/register')) return '/home';
      return null;
    },
    routes: [
      GoRoute(path: '/welcome', builder: (_, __) => const WelcomeScreen()),
      GoRoute(path: '/register', builder: (_, __) => const RegisterScreen()),
      GoRoute(path: '/verify-email', builder: (_, __) => const VerifyEmailScreen()),
      GoRoute(path: '/forgot-password', builder: (_, __) => const ForgotPasswordScreen()),
      GoRoute(path: '/home', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/quick-access', builder: (_, __) => const QuickAccessScreen()),
      GoRoute(path: '/agenda', builder: (_, state) => AgendaScreen(savedOnly: state.uri.queryParameters['saved'] == 'true')),
      GoRoute(path: '/agenda/:sessionId', builder: (_, state) => SessionDetailScreen(sessionId: state.pathParameters['sessionId']!)),
      GoRoute(path: '/speakers', builder: (_, __) => const SpeakersScreen()),
      GoRoute(path: '/speakers/:id', builder: (_, state) => SpeakerDetailScreen(speakerId: state.pathParameters['id']!)),
      GoRoute(path: '/name-tag', builder: (_, __) => const NameTagScreen()),
      GoRoute(path: '/venue', builder: (_, __) => const VenueScreen()),
      GoRoute(path: '/resources', builder: (_, state) => ResourcesScreen(savedOnly: state.uri.queryParameters['saved'] == 'true')),
      GoRoute(path: '/exhibitors', builder: (_, __) => const ExhibitorsScreen()),
      GoRoute(path: '/exhibitors/:id', builder: (_, state) => ExhibitorDetailScreen(exhibitorId: state.pathParameters['id']!)),
      GoRoute(path: '/notifications', builder: (_, __) => const NotificationsScreen()),
      GoRoute(path: '/qna', builder: (_, __) => const QnaScreen()),
      GoRoute(path: '/qna/mine', builder: (_, __) => const MyQuestionsScreen()),
      GoRoute(path: '/voting', builder: (_, __) => const VotingScreen()),
      GoRoute(path: '/voting/history', builder: (_, __) => const PollHistoryScreen()),
      GoRoute(path: '/assistant', builder: (_, __) => const AssistantScreen()),
      GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
      GoRoute(path: '/profile/edit', builder: (_, __) => const EditProfileScreen()),
      GoRoute(path: '/profile/certificates', builder: (_, __) => const CertificatesScreen()),
      GoRoute(path: '/settings', builder: (_, __) => const SettingsScreen()),
      GoRoute(
        path: '/search',
        builder: (_, state) => SearchScreen(query: state.uri.queryParameters['q'] ?? ''),
      ),
      GoRoute(
        path: '/soon',
        builder: (_, state) => SoonScreen(title: state.uri.queryParameters['title'] ?? 'Coming next'),
      ),
    ],
  );
});
