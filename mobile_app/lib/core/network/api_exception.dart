class ApiException implements Exception {
  ApiException({required this.message, this.code, this.fieldErrors = const {}, this.retryAfter});

  final String message;
  final String? code;
  final Map<String, String> fieldErrors;
  final int? retryAfter;

  @override
  String toString() => message;
}
