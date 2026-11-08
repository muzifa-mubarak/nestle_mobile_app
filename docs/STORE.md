# Store release

The phone build is produced from `mobile_app` after the API is on public HTTPS.

```bash
cd mobile_app
flutter pub get
flutter build apk --release --dart-define=API_BASE_URL=https://YOUR_HOST/api/v1
flutter build appbundle --release --dart-define=API_BASE_URL=https://YOUR_HOST/api/v1
```

- Copy the universal APK to `nmc-congress-v1.0.0.apk`.
- Minimum Android SDK is 26. The release manifest must include `INTERNET` and must not allow cleartext HTTP.
- The App Bundle is the Play Store upload. The APK is the assessment file.
- Do not put `GROQ_API_KEY`, `FCM_SERVER_KEY`, or SMTP passwords in the app. Those stay on the server.
