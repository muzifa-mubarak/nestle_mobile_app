bool isEmail(String value) {
  return RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$').hasMatch(value.trim());
}

class PasswordRules {
  PasswordRules(this.value);

  final String value;
  bool get length => value.length >= 8 && value.length <= 72;
  bool get upper => RegExp(r'[A-Z]').hasMatch(value);
  bool get lower => RegExp(r'[a-z]').hasMatch(value);
  bool get digit => RegExp(r'\d').hasMatch(value);
  bool get valid => length && upper && lower && digit;
}
