import 'package:flutter_test/flutter_test.dart';
import 'package:nmc_congress/features/auth/validators.dart';

void main() {
  test('password rules match the congress policy', () {
    expect(PasswordRules('short').valid, isFalse);
    expect(PasswordRules('alllowercase1').valid, isFalse);
    expect(PasswordRules('Passw0rd!').valid, isTrue);
  });

  test('email check rejects blanks and accepts a normal address', () {
    expect(isEmail(''), isFalse);
    expect(isEmail('huda@example.com'), isTrue);
  });
}
