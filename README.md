# Nestlé Medical Congress 2026

This is the attendee app for a two-day medical congress in Dubai, **22–23 May 2026**, at the Dubai International Convention & Exhibition Center.

Attendees use it to sign in, follow the agenda, save sessions, meet speakers, show a name tag, vote, ask questions, download resources, browse exhibitors, and ask the Congress Assistant about the event. Organizers use a separate admin site to manage the same congress. Staff use a check-in desk to scan name tags.

One local server runs the API, the attendee screens, the admin portal, and the check-in desk. The phone app is Flutter source in `mobile_app/`. On this computer you can review everything in the browser without installing Flutter.

## What is in this repository

| Folder | What it is |
|---|---|
| `preview/` | Attendee screens you open in a browser |
| `admin_portal/` | Organizer admin site |
| `checkin/` | Registration-desk scanner |
| `backend/` | FastAPI API and the SQLite database |
| `mobile_app/` | Flutter app for Android and iOS |
| `docs/` | Store-release and submission notes |

The local database file is `backend/nmc.db`. It is created and filled with the congress the first time the server starts. Do not commit `backend/.env`, `backend/.venv`, or API keys.

## Run it

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

| Who | Address |
|---|---|
| Attendee | http://127.0.0.1:8000/ |
| Admin | http://127.0.0.1:8000/admin/ |
| Check-in desk | http://127.0.0.1:8000/checkin/ |
| API | http://127.0.0.1:8000/api/v1 |

Leave that terminal running. Reload the browser after the log says `Application startup complete`.

## How an attendee uses it

1. Open http://127.0.0.1:8000/.
2. Sign in with a test account from the table below, or tap **Create Account**.
3. A new account must accept the terms. The password needs at least 8 characters, one uppercase letter, one lowercase letter, and one digit. `Passw0rd!` meets that rule.
4. After Create Account, the app opens **Verify email**. No email is sent on this computer. The 6-digit code is shown on that screen. Type it and tap **Verify**.
5. Home shows the congress, search, shortcuts, and upcoming sessions. The gold **Ask AI** button opens the assistant.
6. Profile holds the name tag counts, certificates, settings, and log out.

Google and Apple on Create Account are a local sign-up. Check the terms, tap the button, and enter a name plus a `@gmail.com` address or an Apple address (`@icloud.com`, `@me.com`, or `@mac.com`). Those accounts skip the email code and go to Home.

## Features

- **Sign in, register, verify email, forgot password.** New local accounts see the verification code on the next screen.
- **Home.** Congress card for 22–23 May 2026, search, and shortcuts.
- **Agenda.** Day tabs, categories, search, bookmarks, and session detail. Times are shown in Asia/Dubai.
- **Speakers.** Search, specializations, featured speakers, and speaker profiles.
- **Name tag.** Personal badge and QR code. Huda’s badge is `NMC-2026-001`.
- **Venue.** Dubai International Convention & Exhibition Center, with facilities and directions.
- **Live voting.** One vote per person. Results update after the vote.
- **Ask Q&A.** Ask a question, upvote, and read answers. My Questions shows your own items.
- **Resources.** Programs, slides, and links. Saving a resource adds it to the profile count.
- **Exhibitors.** Booth directory.
- **Notifications.** Event updates for the signed-in attendee.
- **Profile.** Edit details, certificates, notification settings, password, and account deletion.
- **Congress Assistant.** Answers from the published congress and the signed-in attendee’s own account. It can be wrong, and it will say when it does not know. Optional `GROQ_API_KEY` in `backend/.env` uses Groq. Without that key, a local answerer is used.

## Test accounts

Every seeded account uses the same password: `Passw0rd!`

These are local demo logins. Do not reuse this password on a public server.

| Who | Email | Password | Where to use it |
|---|---|---|---|
| Attendee, Huda Latheef | `huda@example.com` | `Passw0rd!` | Attendee app. Badge `NMC-2026-001`. Has saved sessions, resources, and certificates. |
| Speaker, Dr. Ahmed | `ahmed@example.com` | `Passw0rd!` | Attendee app. Agenda can show his linked sessions. |
| Organizer (admin) | `organizer@example.com` | `Passw0rd!` | Admin portal at http://127.0.0.1:8000/admin/ |
| Check-in desk | `desk@example.com` | `Passw0rd!` | Check-in page at http://127.0.0.1:8000/checkin/ |

An attendee login cannot open admin tools. The organizer login is the admin login.

## Admin portal

Open http://127.0.0.1:8000/admin/ and sign in as `organizer@example.com` / `Passw0rd!`.

The portal is for the organizer, not for attendees. It includes:

- **Dashboard.** Counts for the current congress.
- **Sessions.** Add a session, publish it, unpublish it, or cancel it.
- **Polls.** Create a poll, activate it, pause it, or close it.
- **Questions.** Approve, hide, reject, or answer a question, and turn moderation on or off.
- **Resources.** Add a link and publish it.
- **Exhibitors.** Add, edit, or remove a booth.
- **Attendees.** Approve or suspend an account.
- **Messages.** Organizer messages for the congress.
- **Check-in desk.** Opens the scanner used at the door.

## Android APK

The assessment file is an installable Android package built from `mobile_app/`. This repository contains the Flutter screens. It does not contain a ready `.apk`, and this Mac does not have the Flutter SDK or the `mobile_app/android` project folder yet. You build the APK on a computer that has both.

### 1. Install the tools

1. Install Flutter: https://docs.flutter.dev/get-started/install/macos
2. Install Android Studio and, inside it, the Android SDK.
3. In a terminal, run `flutter doctor` and fix anything it marks for Android. Accept the Android licenses if it asks.

### 2. Add the Android project once

The app source is already in `mobile_app/lib`. This command only adds the Android wrapper. Run it from `mobile_app` and do not delete `lib/`.

```bash
cd mobile_app
flutter create . --platforms=android --project-name nmc_congress
flutter pub get
```

### 3. Point the app at the API

A phone cannot call `127.0.0.1`. That address is the phone itself, not your computer.

- **Emulator:** use `http://10.0.2.2:8000/api/v1`
- **Real phone on the same Wi-Fi:** use your computer’s address, for example `http://192.168.1.20:8000/api/v1`. Find it with `ipconfig getifaddr en0`. The API must be started with `--host 0.0.0.0`, not only `127.0.0.1`.
- **The file you submit:** use the public HTTPS API, for example `https://YOUR_HOST/api/v1`. A release APK for review should not depend on your laptop.

Android blocks plain `http://` unless the app allows cleartext traffic. For a local demo, add `android:usesCleartextTraffic="true"` on the `<application>` tag in `mobile_app/android/app/src/main/AndroidManifest.xml`. Leave that off for a public HTTPS build.

### 4. Build the APK

Local demo against this computer:

```bash
cd mobile_app
flutter build apk --release --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1
```

Replace the address with the one from step 3.

Submission build against a hosted API:

```bash
cd mobile_app
flutter build apk --release --dart-define=API_BASE_URL=https://YOUR_HOST/api/v1
```

The file is created at:

`mobile_app/build/app/outputs/flutter-apk/app-release.apk`

Copy it to `nmc-congress-v1.0.0.apk` if the submission asks for that name. Install it by sending the file to the phone, or with `adb install app-release.apk`. More release notes are in [docs/STORE.md](docs/STORE.md) and [docs/SUBMISSION.md](docs/SUBMISSION.md).

To run it from a cable instead of making an APK:

```bash
cd mobile_app
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
```

## Tests

```bash
cd backend && .venv/bin/pytest
```
