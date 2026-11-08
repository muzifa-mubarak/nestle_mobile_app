import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/network/api_client.dart';
import '../../core/network/api_exception.dart';
import '../../core/storage/token_store.dart';

class AuthState {
  const AuthState({
    this.ready = false,
    this.busy = false,
    this.user,
    this.formError,
    this.fieldErrors = const {},
    this.pendingEmail,
    this.devOtp,
    this.info,
  });

  final bool ready;
  final bool busy;
  final Map<String, dynamic>? user;
  final String? formError;
  final Map<String, String> fieldErrors;
  final String? pendingEmail;
  final String? devOtp;
  final String? info;

  bool get signedIn => user != null;

  AuthState copyWith({
    bool? ready,
    bool? busy,
    Map<String, dynamic>? user,
    String? formError,
    Map<String, String>? fieldErrors,
    String? pendingEmail,
    String? devOtp,
    String? info,
    bool clearError = false,
    bool clearUser = false,
    bool clearOtp = false,
  }) {
    return AuthState(
      ready: ready ?? this.ready,
      busy: busy ?? this.busy,
      user: clearUser ? null : (user ?? this.user),
      formError: clearError ? null : (formError ?? this.formError),
      fieldErrors: fieldErrors ?? this.fieldErrors,
      pendingEmail: pendingEmail ?? this.pendingEmail,
      devOtp: clearOtp ? null : (devOtp ?? this.devOtp),
      info: info,
    );
  }
}

final tokenStoreProvider = Provider<TokenStore>((ref) => TokenStore());
final apiClientProvider = Provider<ApiClient>((ref) => ApiClient(ref.watch(tokenStoreProvider)));

class AuthController extends Notifier<AuthState> {
  @override
  AuthState build() {
    Future.microtask(restore);
    return const AuthState();
  }

  ApiClient get _api => ref.read(apiClientProvider);
  TokenStore get _store => ref.read(tokenStoreProvider);

  Future<void> restore() async {
    final refresh = await _store.readRefresh();
    if (refresh == null) {
      state = state.copyWith(ready: true, clearUser: true);
      return;
    }
    try {
      final data = await _api.post('/auth/refresh', {'refresh_token': refresh});
      await _persist(data);
      state = state.copyWith(ready: true, user: Map<String, dynamic>.from(data['user'] as Map), clearError: true);
    } catch (_) {
      await _store.clear();
      state = state.copyWith(ready: true, clearUser: true);
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(busy: true, clearError: true, fieldErrors: {});
    try {
      final data = await _api.post('/auth/login', {
        'email': email.trim(),
        'password': password,
        'device_info': 'Flutter',
      });
      await _persist(data);
      state = state.copyWith(busy: false, user: Map<String, dynamic>.from(data['user'] as Map));
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(
        busy: false,
        formError: error.message,
        fieldErrors: error.fieldErrors,
        pendingEmail: error.code == 'EMAIL_NOT_VERIFIED' ? email.trim() : state.pendingEmail,
      );
      return false;
    }
  }

  Future<bool> register({
    required String fullName,
    required String email,
    required String organization,
    required String password,
    required bool acceptedTerms,
  }) async {
    state = state.copyWith(busy: true, clearError: true, fieldErrors: {}, clearOtp: true);
    try {
      final data = await _api.post('/auth/register', {
        'full_name': fullName.trim(),
        'email': email.trim(),
        'organization': organization.trim(),
        'password': password,
        'accepted_terms': acceptedTerms,
      });
      state = state.copyWith(
        busy: false,
        pendingEmail: data['email'] as String?,
        devOtp: data['dev_otp'] as String?,
      );
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(busy: false, formError: error.message, fieldErrors: error.fieldErrors);
      return false;
    }
  }

  Future<String?> social({required String provider, required String fullName, required String email}) async {
    state = state.copyWith(busy: true, clearError: true, fieldErrors: {});
    try {
      final data = await _api.post('/auth/social', {
        'provider': provider,
        'full_name': fullName.trim(),
        'email': email.trim(),
        'accepted_terms': true,
        'device_info': 'Flutter',
      });
      await _persist(data);
      state = state.copyWith(busy: false, user: Map<String, dynamic>.from(data['user'] as Map));
      return null;
    } on ApiException catch (error) {
      state = state.copyWith(busy: false, formError: error.message, fieldErrors: error.fieldErrors);
      return error.message;
    }
  }

  Future<bool> verify(String code) async {
    final email = state.pendingEmail;
    if (email == null) return false;
    state = state.copyWith(busy: true, clearError: true);
    try {
      final data = await _api.post('/auth/verify-email', {'email': email, 'code': code, 'device_info': 'Flutter'});
      await _persist(data);
      state = state.copyWith(busy: false, user: Map<String, dynamic>.from(data['user'] as Map), clearOtp: true);
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(busy: false, formError: error.message);
      return false;
    }
  }

  Future<void> resend() async {
    final email = state.pendingEmail;
    if (email == null) return;
    try {
      final data = await _api.post('/auth/resend-verification', {'email': email});
      state = state.copyWith(devOtp: data['dev_otp'] as String?, info: 'A new code has been sent.', clearError: true);
    } on ApiException catch (error) {
      state = state.copyWith(formError: error.message);
    }
  }

  Future<bool> forgot(String email) async {
    state = state.copyWith(busy: true, clearError: true, clearOtp: true);
    try {
      final data = await _api.post('/auth/forgot-password', {'email': email.trim()});
      state = state.copyWith(
        busy: false,
        pendingEmail: email.trim(),
        devOtp: data['dev_otp'] as String?,
        info: data['message'] as String? ?? 'If this email exists, a code has been sent.',
      );
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(busy: false, formError: error.message);
      return false;
    }
  }

  Future<bool> resetPassword(String code, String password) async {
    final email = state.pendingEmail;
    if (email == null) return false;
    state = state.copyWith(busy: true, clearError: true);
    try {
      await _api.post('/auth/reset-password', {'email': email, 'code': code, 'new_password': password});
      state = state.copyWith(busy: false, info: 'Password updated. Sign in with your new password.', clearOtp: true);
      return true;
    } on ApiException catch (error) {
      state = state.copyWith(busy: false, formError: error.message);
      return false;
    }
  }

  Future<void> logout() async {
    final refresh = await _store.readRefresh();
    try {
      await _api.post('/auth/logout', {'refresh_token': refresh});
    } catch (_) {}
    await _store.clear();
    state = state.copyWith(clearUser: true, clearError: true, clearOtp: true);
  }

  void clearMessages() {
    state = state.copyWith(clearError: true, fieldErrors: {}, info: null);
  }

  Future<void> _persist(Map<String, dynamic> data) {
    return _store.save(access: data['access_token'] as String, refresh: data['refresh_token'] as String);
  }
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(AuthController.new);
