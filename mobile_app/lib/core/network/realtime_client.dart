import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'api_client.dart';

/// Live updates for polls and questions. Falls back to screen polling after three failed connects.
class RealtimeClient {
  RealtimeClient(this.api);

  final ApiClient api;
  WebSocket? _socket;
  StreamSubscription? _subscription;
  Timer? _ping;
  Timer? _retry;
  int _failures = 0;
  bool _closed = false;

  bool get connected => _socket != null;

  Future<void> connect(void Function(Map<String, dynamic> event) onEvent) async {
    if (_closed) return;
    final token = await api.store.readAccess();
    if (token == null || token.isEmpty) return;
    final base = api.baseUrl.replaceFirst(RegExp(r'/+$'), '');
    final wsBase = base.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    try {
      final socket = await WebSocket.connect('$wsBase/ws?token=${Uri.encodeQueryComponent(token)}');
      if (_closed) {
        await socket.close();
        return;
      }
      _failures = 0;
      _socket = socket;
      socket.add(jsonEncode({'type': 'subscribe', 'topics': ['polls', 'questions', 'schedule']}));
      _ping?.cancel();
      _ping = Timer.periodic(const Duration(seconds: 25), (_) {
        if (_socket == socket) socket.add(jsonEncode({'type': 'ping'}));
      });
      _subscription = socket.listen(
        (data) {
          final decoded = jsonDecode(data.toString());
          if (decoded is Map) onEvent(Map<String, dynamic>.from(decoded));
        },
        onError: (_) => _scheduleRetry(onEvent),
        onDone: () => _scheduleRetry(onEvent),
        cancelOnError: true,
      );
    } catch (_) {
      _scheduleRetry(onEvent);
    }
  }

  void _scheduleRetry(void Function(Map<String, dynamic> event) onEvent) {
    _socket = null;
    _ping?.cancel();
    if (_closed || _failures >= 3) return;
    _failures += 1;
    _retry?.cancel();
    _retry = Timer(Duration(seconds: 1 << (_failures - 1)), () => connect(onEvent));
  }

  Future<void> close() async {
    _closed = true;
    _retry?.cancel();
    _ping?.cancel();
    await _subscription?.cancel();
    await _socket?.close();
    _socket = null;
  }
}
