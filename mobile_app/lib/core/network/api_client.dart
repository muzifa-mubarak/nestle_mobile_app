import 'package:dio/dio.dart';

import '../storage/token_store.dart';
import 'api_exception.dart';

class ApiClient {
  ApiClient(this.store) {
    dio = Dio(
      BaseOptions(
        baseUrl: const String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8000/api/v1'),
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 20),
        headers: {'Content-Type': 'application/json'},
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await store.readAccess();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (error, handler) async {
          final code = _codeOf(error);
          final alreadyRetried = error.requestOptions.extra['retried'] == true;
          if (error.response?.statusCode == 401 && code == 'TOKEN_EXPIRED' && !alreadyRetried) {
            final refreshed = await _refresh();
            if (refreshed) {
              final request = error.requestOptions;
              request.extra['retried'] = true;
              request.headers['Authorization'] = 'Bearer ${await store.readAccess()}';
              try {
                final response = await dio.fetch(request);
                handler.resolve(response);
                return;
              } catch (retryError) {
                if (retryError is DioException) {
                  handler.next(retryError);
                  return;
                }
              }
            } else {
              await store.clear();
            }
          }
          handler.next(error);
        },
      ),
    );
  }

  final TokenStore store;
  late final Dio dio;

  String get baseUrl => dio.options.baseUrl;
  Future<void>? _refreshing;

  Future<Map<String, dynamic>> post(String path, Map<String, dynamic> body, {Map<String, dynamic>? headers, Duration? receiveTimeout}) async {
    try {
      final response = await dio.post(
        path,
        data: body,
        options: Options(headers: headers, receiveTimeout: receiveTimeout),
      );
      return _data(response);
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Future<Map<String, dynamic>> patch(String path, Map<String, dynamic> body) async {
    try {
      final response = await dio.patch(path, data: body);
      return _data(response);
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Future<Map<String, dynamic>> put(String path) async {
    try {
      final response = await dio.put(path);
      return _data(response);
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Future<Map<String, dynamic>> delete(String path) async {
    try {
      final response = await dio.delete(path);
      if (response.statusCode == 204 || response.data == null || response.data == '') return {};
      return _data(response);
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Future<Map<String, dynamic>> get(String path, {Map<String, dynamic>? query}) async {
    try {
      final response = await dio.get(path, queryParameters: query);
      return _data(response);
    } on DioException catch (error) {
      throw _wrap(error);
    }
  }

  Map<String, dynamic> _data(Response response) {
    final body = response.data;
    if (body is Map<String, dynamic> && body['success'] == true) {
      final data = body['data'];
      if (data is Map<String, dynamic>) return data;
      return {'value': data};
    }
    return {};
  }

  ApiException _wrap(DioException error) {
    final payload = error.response?.data;
    if (payload is Map && payload['error'] is Map) {
      final err = payload['error'] as Map;
      final fields = <String, String>{};
      final raw = err['field_errors'];
      if (raw is List) {
        for (final item in raw) {
          if (item is Map && item['field'] != null) {
            fields[item['field'].toString()] = item['message']?.toString() ?? 'Check this field.';
          }
        }
      }
      return ApiException(
        message: err['message']?.toString() ?? 'Something went wrong.',
        code: err['code']?.toString(),
        fieldErrors: fields,
        retryAfter: (err['retry_after'] as num?)?.toInt() ?? int.tryParse(error.response?.headers.value('retry-after') ?? ''),
      );
    }
    return ApiException(message: 'We could not reach the server. Check your connection and try again.');
  }

  String? _codeOf(DioException error) {
    final payload = error.response?.data;
    if (payload is Map && payload['error'] is Map) {
      return payload['error']['code']?.toString();
    }
    return null;
  }

  Future<bool> _refresh() async {
    if (_refreshing != null) {
      try {
        await _refreshing;
        return (await store.readAccess()) != null;
      } catch (_) {
        return false;
      }
    }
    final refreshToken = await store.readRefresh();
    if (refreshToken == null || refreshToken.isEmpty) return false;
    final future = () async {
      final bare = Dio(dio.options);
      final response = await bare.post('${dio.options.baseUrl}/auth/refresh', data: {'refresh_token': refreshToken});
      final data = response.data['data'] as Map<String, dynamic>;
      await store.save(access: data['access_token'] as String, refresh: data['refresh_token'] as String);
    }();
    _refreshing = future;
    try {
      await future;
      return true;
    } catch (_) {
      await store.clear();
      return false;
    } finally {
      _refreshing = null;
    }
  }
}
