# Product Requirements Document (PRD)
# Nestlé Medical Congress 2026: Mobile App, Backend & Admin Portal

**Document Version:** 2.0 (Build-ready) | **Date:** November 6, 2026 | **Status:** Draft for implementation | **Owner:** Product Management

> **How to use this document with Cursor.** Every screen, field, table, endpoint and rule needed to build the product is in here. Section 18 gives a phase-by-phase build order with a "done when" checklist per phase. Where the original PRD said "confirm with client", Section 3 now states a default decision. Override a decision in Section 3 *before* building the affected module.

## Table of Contents

1. Product Overview & Goals
2. User Personas
3. Key Product Decisions (defaults applied)
4. Feature Breakdown by Role
5. Authentication & Authorization
6. Domain Rules (business logic per module)
7. Design System
8. Mobile Screen Specifications (12 reference screens + 8 inferred screens)
9. Admin Portal
10. Notifications
11. Database Schema
12. API Structure
13. Real-time (WebSocket) Design
14. Tech Stack & Project Setup
15. Non-Functional Requirements
16. Testing & Acceptance Criteria
17. Deployment & Operations
18. Cursor Build Plan
19. Optional Enhancements (Phase 2)
20. Risks & Assumptions
Appendix A: Seed Data
Appendix B: Design Inconsistencies Found in the Screenshots
Appendix C: Reference UI Screenshots

---

## 1. Product Overview & Goals

### Vision Statement
To give every registered attendee of the Nestlé Medical Congress 2026 (Dubai, UAE) one reliable mobile companion for the event: discover the agenda and speakers, carry a digital name tag, find the venue, vote in live polls, ask the experts questions, and access approved congress materials. Organizers manage all of it from a web admin portal with no app release required.

### Business Objectives

- Centralize congress information and attendee services in a single iOS/Android app
- Replace printed schedules and badges with digital equivalents
- Enable structured audience engagement through live polls and moderated Q&A
- Make approved presentations, documents and media discoverable and securely downloadable
- Give organizers full control of event content, polls, moderation, resources and announcements through an admin portal

### Success Metrics (KPIs)

| Metric | Target (event window: May 22–23, 2026 equivalent) |
|---|---|
| Registered attendees who complete onboarding | ≥ 85% of invited attendees |
| Login success rate (valid credentials) | ≥ 99% |
| Attendees who open the Agenda at least once | ≥ 80% |
| Accepted valid votes / submitted valid votes | 100% (no lost accepted votes) |
| Q&A moderation turnaround (submit → published/rejected) | median < 2 minutes |
| Successful authorized resource opens/downloads | ≥ 98% |
| API availability during event hours | ≥ 99.9% |
| Crash-free sessions | ≥ 99.5% |
| Poll vote → result visible on other devices | p95 < 2 seconds |

### Scope: Phase 1 (this PRD)
**In scope:** Flutter mobile app (iOS + Android); FastAPI backend; PostgreSQL; Redis; S3 storage; WebSocket real-time; Next.js admin portal; email OTP verification; push notifications; digital name tag with QR; QR check-in (web-based scanner for staff); exhibitors directory (read-only); certificates (admin-issued PDFs).

**Out of scope:** ticket sales or payments, in-app chat/DMs, exhibitor lead capture, offline-first sync, CPD/accreditation integrations, public web attendee portal, medical advice or patient data of any kind.

---

## 2. User Personas

### Persona 1: Attendee (Healthcare Professional)

- **Name:** Dr. Huda, 34. Pediatric nutrition specialist (test user in screenshots: "Huda Latheef")
- **Tech comfort:** Medium
- **Goals:** See what's on today and where; save sessions; get into the venue quickly with a QR badge; vote and ask questions without queueing at a microphone; download slides afterwards
- **Pain points:** Printed agendas change; hard to find the right room; can't ask questions in a large hall; slides arrive weeks later
- **Needs:** Fast, clear, one-hand-friendly app that works on congress Wi-Fi/4G

### Persona 2: Speaker

- **Name:** Dr. Sarah Johnson, 45. Keynote speaker
- **Goals:** See questions about her session, answer the good ones, know her schedule
- **Needs:** A filtered view of questions for her sessions and the ability to post answers

### Persona 3: Moderator

- **Name:** Layla, 29. Congress program team
- **Goals:** Keep Q&A on-topic and appropriate; surface the best questions to speakers fast
- **Pain points:** Unfiltered question floods; no audit trail
- **Needs:** A real-time moderation queue with approve/hide/reject and keyboard-friendly bulk actions

### Persona 4: Event Organizer

- **Name:** Omar, 38. Event manager
- **Goals:** Publish and change sessions instantly, open/close polls live, push announcements, upload slides after each talk
- **Needs:** One portal for all content with immediate propagation to the app

### Persona 5: Administrator

- **Name:** Arjun, 40. Platform/IT owner
- **Goals:** Manage users and roles, audit sensitive actions, keep the system secure
- **Needs:** User management, role assignment, audit log, system settings

### Persona 6: Check-in Staff

- **Name:** Sara, 24. Registration desk
- **Goals:** Scan a badge QR and instantly see "valid / already checked in / invalid"
- **Needs:** A fast camera-based scanner page with big, unambiguous result states

---

## 3. Key Product Decisions (defaults applied)

The original PRD left these open. These are the decisions this PRD builds against. **Change any row here before building the affected module.**

| # | Topic | Decision (default) | Affects |
|---|---|---|---|
| D1 | Events | Data model supports multiple events (`event_id` everywhere); the app shows **one current event** (`GET /events/current`) | All content |
| D2 | Admin portal | **Included** (Next.js web app) | Section 9 |
| D3 | Registration | Public self-registration with email OTP verification. Admin can also create/import attendees and can toggle "Require admin approval" (default OFF) | Auth |
| D4 | Social sign-in | Google & Apple buttons are shown in the UI (as in the design) but controlled by feature flags `FEATURE_GOOGLE_SIGNIN`, `FEATURE_APPLE_SIGNIN` (default **OFF**; buttons hidden when OFF) | Auth |
| D5 | Roles | Single global role per user: `attendee`, `speaker`, `moderator`, `organizer`, `admin`, `checkin_staff` | RBAC |
| D6 | Voting | One vote per user per poll, **single-choice** default (multi-choice supported via poll config), not anonymous to organizers but never shown per-user to attendees. **Results visible after the attendee has voted**, or after the poll closes. Organizer can switch to "after close only" per poll | Voting |
| D7 | Q&A | Questions are **pre-moderated** by default (event setting `qna_moderation_enabled = true`). Upvote once per user per question. Speaker/moderator can answer | Q&A |
| D8 | Exhibitors | Read-only directory: list, search, category filter, detail (logo, name, booth, description, website). Admin CRUD | Exhibitors |
| D9 | Certificates | Admin issues certificates to selected attendees; backend generates a PDF from a template; attendee downloads from Profile → Certificates | Profile |
| D10 | Check-in | QR check-in via a **web scanner page in the admin portal** (camera). Not in the mobile app | Badge |
| D11 | Push notifications | Included (FCM for Android and iOS via APNs key in Firebase) | Notifications |
| D12 | Language | English only, but all strings live in localization files (`arb`) | Mobile |
| D13 | Offline | Read-only cache of agenda, speakers, venue, badge, bookmarked resources metadata. Writes (vote, question, bookmark) require connectivity | Mobile |
| D14 | Hosting | AWS, region `me-central-1` (UAE) for data residency; fallback `eu-central-1` if a service is unavailable in-region | Deployment |
| D15 | Session counts | Profile "Sessions" = number of **bookmarked sessions**. "Saved" = number of **bookmarked resources**. "Certificates" = issued certificates | Profile |
| D16 | Date handling | Store UTC; render in the event timezone (`Asia/Dubai`). **Never hardcode "May 22–23, 2026" or "Dubai"**; these come from the event record | All |
| D17 | Min OS versions | iOS 15+, Android 8.0 (API 26)+ | Mobile |
| D18 | Capacity planning | Default load target: 3,000 registered attendees, 1,500 concurrent connections, 300 votes/second burst | NFR |

---

## 4. Feature Breakdown by Role

### 4.1 Attendee Features
**Account**

- Register (full name, email, hospital/organization, password, accept terms), verify email by 6-digit OTP
- Sign in with email + password; (optional) Google/Apple; forgot/reset password
- Edit profile (name, phone, location, designation, avatar); change password; log out; request account deletion

**Home**

- Personalized greeting, featured event card, search, notification bell with unread dot, Quick Access grid (8 shortcuts), Upcoming Sessions list

**Agenda & Sessions**

- Day selector, category filter chips, search, reset filters, session list, session detail, bookmark/unbookmark, see changed/cancelled badges

**Speakers**

- Search, category filter chips, featured toggle, speaker cards, speaker detail with biography and sessions

**Digital Name Tag**

- Name tag with initials/photo, name, designation, badge ID, location, congress dates and QR code; print/share

**Venue**

- Venue name, dates, address, map preview, directions, facility chips (Wi-Fi, Parking, Catering, Accessible)

**Live Voting**

- See active polls, swipe between polls, select option, submit vote, see live results, view poll history

**Ask Q&A**

- Write and submit a question with category (and optional session/speaker), browse Popular / Recent / Answered, upvote, see answers, see "My questions"

**Resources**

- Search, filter All / PDF / Slides / Videos / Saved, bookmark, open/download

**Exhibitors**

- Browse, search, filter by category, view detail

**Notifications**

- List, unread count, mark read, deep link to related content

**Profile & Certificates**

- View profile and activity counts, download certificates, settings

### 4.2 Speaker Features

- Everything an attendee can do
- "My Sessions" filter in Agenda (sessions where the user is linked as a speaker)
- Questions tab shows questions for own sessions; can post/edit own answers

### 4.3 Moderator Features (Admin Portal)

- Q&A queue (Pending / Published / Answered / Hidden / Rejected), approve, hide, reject (with reason), flag, mark answered, post answer
- View moderation history

### 4.4 Organizer Features (Admin Portal)

- Event setup (title, tagline, dates, timezone, branding, venue, facilities)
- Sessions, categories, speakers, session↔speaker assignments, cancel/reschedule
- Polls (create, schedule, activate, pause, close, duplicate, reset results with confirmation)
- Resources (upload, metadata, publish/unpublish, replace/version)
- Exhibitors CRUD
- Announcements (compose, target, schedule, send)
- Attendees list (search, view, approve, export CSV), issue certificates
- Reports (engagement metrics)

### 4.5 Administrator Features (Admin Portal)

- Everything an organizer can do
- User management (create, edit, role change, suspend, delete, CSV import)
- Audit log viewer, system settings, feature flags

### 4.6 Check-in Staff Features (Admin Portal, `/checkin`)

- Camera QR scanner, result card (valid / already checked in / invalid / suspended), manual lookup by badge ID, today's check-in count

---

## 5. Authentication & Authorization

### 5.1 Registration Flow
```
User opens app → Welcome screen → taps "Create Account"
→ Fills: Full name, Email, Hospital/Organization, Password, ticks terms checkbox
→ Client validates (all required, email format, password policy, checkbox ticked)
→ POST /auth/register
→ Backend: normalizes email (trim + lowercase), rejects duplicates (409 EMAIL_EXISTS),
  hashes password (Argon2id), creates user status=pending_verification, role=attendee,
  creates badge record, generates 6-digit OTP (hashed, 15 min expiry, max 5 attempts)
→ Sends verification email (OTP) via worker
→ App navigates to "Verify Email" screen
→ POST /auth/verify-email {email, code}
→ Backend sets status=active (or pending_approval if approval mode is ON), email_verified_at=now
→ Returns access + refresh tokens → App goes to Home
```
**Password policy:** min 8 chars, at least 1 uppercase, 1 lowercase, 1 digit. Max 72 chars. Show requirements live under the field.

### 5.2 Login Flow
```
Enters email + password → POST /auth/login
→ Valid: returns { access_token (15 min, RS256 JWT), refresh_token (opaque, 30 days), user }
→ App stores both in flutter_secure_storage (Keychain / Keystore)
→ Dio interceptor attaches Authorization: Bearer <access_token>
→ On 401 TOKEN_EXPIRED: interceptor calls POST /auth/refresh once (single-flight lock),
  retries the original request; if refresh fails → clear storage → go to Login
→ Refresh tokens ROTATE on every use; reuse of an old refresh token revokes the whole token family
→ Logout: POST /auth/logout (revokes family) + clear secure storage + unregister device token
```
**Login errors:** `INVALID_CREDENTIALS` (generic, never reveal whether the email exists), `EMAIL_NOT_VERIFIED` (app routes to Verify Email screen), `ACCOUNT_SUSPENDED`, `ACCOUNT_PENDING_APPROVAL`, `RATE_LIMITED`.

### 5.3 Forgot / Reset Password
```
"Forgot password?" → enter email → POST /auth/forgot-password
→ Always returns 200 "If this email exists, a code has been sent." (no enumeration)
→ If user exists: 6-digit OTP (15 min, one-time) emailed
→ Reset screen: email + code + new password + confirm
→ POST /auth/reset-password → on success revokes ALL refresh tokens → redirect to Login with success toast
```

### 5.4 Admin Portal Authentication

- Same `/auth/login`; allowed only for roles `organizer`, `admin`, `moderator`, `checkin_staff`
- Access token in memory; refresh token in HTTP-only, Secure, SameSite=Strict cookie (portal uses cookie transport via `/auth/web/login`, `/auth/web/refresh`)
- Session idle timeout 30 minutes; TOTP-based MFA optional for `admin` (setting `ADMIN_MFA_REQUIRED`)

### 5.5 Role-Based Access Control (RBAC) Matrix
`Y` = allowed, `O` = own records only, `-` = no.

| Feature / Action | Attendee | Speaker | Moderator | Organizer | Admin | Check-in |
|---|---|---|---|---|---|---|
| Register / login / edit own profile | Y | Y | Y | Y | Y | Y |
| View agenda, speakers, venue, exhibitors | Y | Y | - | Y | Y | - |
| Bookmark sessions/resources | Y | Y | - | - | - | - |
| View own badge | Y | Y | - | - | - | - |
| Vote in polls | Y | Y | - | - | - | - |
| Submit / upvote questions | Y | Y | - | - | - | - |
| Answer questions | - | O (own sessions) | Y | Y | Y | - |
| Moderate questions | - | - | Y | Y | Y | - |
| Create/edit sessions, speakers, categories | - | - | - | Y | Y | - |
| Create/activate/close polls | - | - | - | Y | Y | - |
| Upload/publish resources | - | - | - | Y | Y | - |
| Manage exhibitors | - | - | - | Y | Y | - |
| Send announcements | - | - | - | Y | Y | - |
| Issue certificates | - | - | - | Y | Y | - |
| Manage users & roles | - | - | - | - | Y | - |
| View audit logs / system settings | - | - | - | - | Y | - |
| Scan badge / check-in | - | - | - | Y | Y | Y |

### 5.6 Security Requirements

- Passwords hashed with **Argon2id** (`argon2-cffi`; memory 64 MB, time cost 3, parallelism 4)
- JWT signed with **RS256**; keys from environment/Secrets Manager; `kid` header for rotation; claims: `sub`, `role`, `iat`, `exp`, `jti`
- Refresh tokens: 256-bit random, stored **hashed (SHA-256)**, rotated, family-based reuse detection
- Mobile tokens in Keychain/Keystore only; never in SharedPreferences or logs
- Rate limits (Redis sliding window): login 10/min/IP and 5/min/email; register 5/min/IP; forgot-password 3/min/email; OTP verify 5 attempts per code; question submit 5 per 10 min/user; vote 20/min/user; upvote 60/min/user
- Account lockout: 10 failed logins → 15 min lock (counter in Redis)
- All inputs validated server-side with Pydantic v2; output never contains `password_hash`, token hashes or storage keys
- CORS restricted to the admin portal origin; mobile uses no cookies
- Every protected endpoint declares its required roles through a FastAPI dependency (`require_roles(...)`); authorization on the **backend**, never UI-only
- Audit log entries for: role change, user suspend/delete, poll activate/pause/close/reset, question moderation, resource publish/unpublish, announcement send, certificate issue, check-in scan, settings change

---

## 6. Domain Rules (business logic per module)

### 6.1 Agenda

- Sessions belong to an event; `start_at < end_at` (DB CHECK); `status` ∈ `scheduled | changed | cancelled | draft`. Only `scheduled | changed | cancelled` and `visibility = published` are returned to attendees
- "Day" = the calendar date of `start_at` in the event timezone. The day list is derived from distinct session dates ∪ event start→end dates (so Day tabs exist even before sessions are added). Labels: `Day 1`, `Day 2`... plus short date `May 22`
- Default sort: `start_at ASC, display_order ASC`
- Category filter: single-select chips; `All` = no filter. `Reset` clears category and search
- `changed` shows an amber "Updated" chip; `cancelled` shows a red "Cancelled" chip and strike-through title; both still listed
- Bookmark toggle is idempotent (`PUT` creates if missing, `DELETE` removes if present)

### 6.2 Upcoming Sessions (Home)

- Next 5 sessions where `end_at > now()`, status ≠ cancelled, ordered by `start_at`
- If the event has not started: first sessions of Day 1. If finished: empty state "The congress has ended. Thank you for joining."

### 6.3 Speakers

- Featured speakers appear first (`is_featured DESC`, then `display_order`, then name)
- Speaker has one or more **specializations** (category of type `speaker`), e.g. Nutrition, Research, Pediatric
- Search matches name, designation, organization, country (case-insensitive, `ILIKE`/trigram)

### 6.4 Badge / QR

- Badge auto-created at registration. `badge_code` format `NMC-{year}-{seq:03d}` (e.g. `NMC-2026-001`), unique per event
- QR content = `nmc://badge/{token}` where `token` is a 32-byte URL-safe random string. Store only `SHA-256(token)`. The plain token is returned only to the owner via `GET /me/badge`
- QR never contains name, email, or phone
- If a user is suspended or the badge is revoked, verification returns `status: revoked`
- First valid scan sets `checked_in_at`; later scans return `already_checked_in` with the original time

### 6.5 Venue

- Facilities are configurable rows (key, label, icon, enabled). Seeded: `wifi`, `parking`, `catering`, `accessible`
- Directions button opens the native maps app via `geo:`/`maps:` URL using lat/lng or the address fallback
- If lat/lng is missing or the map fails to load, show the address card only

### 6.6 Live Voting

- Poll lifecycle: `draft → scheduled → active → closed`; `active ↔ paused` allowed. Backend is the source of truth; if `starts_at`/`ends_at` are set a worker transitions status automatically (checked every 5 s)
- A vote is accepted only if: poll `status = active`, `now()` within window, option belongs to poll, user has not voted (single-choice) or selection count ≤ `max_choices` (multi)
- Enforced with `UNIQUE (poll_id, user_id, option_id)` plus a service check inside one transaction (lock the poll row with `SELECT ... FOR SHARE`, then count the user's existing votes for that poll). A user with any existing vote on a single-choice poll gets `ALREADY_VOTED`
- Idempotency: `Idempotency-Key` header stored for 24 h in Redis; a retry with the same key returns the original response
- Percentages: computed from persisted votes using the **largest remainder method** so displayed integers always total 100%; `total_votes` = number of distinct voters
- Result visibility (`results_visibility`): `after_vote` (default) | `live` | `after_close`. When hidden, API returns `results: null` and the app shows "Results will be shown after you vote / after the poll closes"
- Attendee may **not** change a vote in Phase 1
- Poll swiping: the app shows the list of active (and scheduled-visible) polls as pages; "Next Poll" moves forward, arrow buttons move back/forward, dots indicate position

### 6.7 Q&A

- Question text: 10–500 characters, trimmed, profanity filter (configurable word list) → auto-flag (not auto-reject)
- Category: one of event's `question` categories (General, Nutrition, Research, Clinical). Optional `session_id`, optional `speaker_id`
- Status machine: `pending → published → answered`; `pending/published → hidden`; `pending → rejected`. With moderation OFF new questions go straight to `published`
- Lists: `Popular` = published/answered by `upvote_count DESC, created_at DESC`; `Recent` = `created_at DESC`; `Answered` = status answered, newest answer first
- Authors always see their own pending/rejected questions in "My questions" with status chip
- Upvote: one per user per question; cannot upvote own question; toggle allowed (second tap removes upvote)
- Answer: stored in `answers`; question status becomes `answered`; author gets a notification
- Attendees cannot edit/delete a question after submission (Phase 1)

### 6.8 Resources

- Types: `pdf`, `slides`, `video`, `document`, `link`. Filter chips map: PDF→`pdf`, Slides→`slides`, Videos→`video`, Saved→user's bookmarks
- Files in S3 private bucket; metadata in DB. Max 100 MB per file (video via external link or ≤ 500 MB upload); allowed MIME: `application/pdf`, `.pptx/.ppt`, `video/mp4`
- `GET /resources/{id}/access` returns a pre-signed URL valid 5 minutes; for `link` type returns the external URL. Increments `download_count`
- Unpublished resources: 404 for attendees; existing signed URLs expire naturally
- Displays: icon by type, title (1 line ellipsis), description (1 line ellipsis), file size (human readable, e.g. `4.2 MB`)

### 6.9 Notifications

- Created by system events or announcements; one row per recipient. Push is sent via FCM with `data.deep_link`
- Unread count = rows with `read_at IS NULL`

### 6.10 Certificates

- Admin selects attendees → `POST /admin/certificates/issue`; system creates `certificates` rows with `certificate_number` `NMC-CERT-2026-{seq:05d}`, generates PDF (ReportLab) from template (logo, name, event, dates, number), stores in S3
- Attendee downloads via signed URL

---

## 7. Design System

> Values below are estimated from the screenshots. Confirm against the Figma file if available; otherwise treat these as the source of truth. Implement as Flutter `ThemeData` + a `AppTokens` class; never hardcode colors in widgets.

### 7.1 Colors

| Token | Hex | Use |
|---|---|---|
| `bgNavy900` | `#071A4A` | Screen background (top of gradient) |
| `bgNavy700` | `#0B2C78` | Screen background (bottom of gradient) |
| `surface` | `#FFFFFF` | Cards, content sheets |
| `surfaceMuted` | `#F3F6FC` | Inputs, chips (inactive), list tiles |
| `primary` | `#2F6BFF` | Primary buttons, active chips, selected states |
| `primaryCyan` | `#4FC3F7` | Gradient end for buttons / badge header |
| `accentGold` | `#F5B942` | Highlights, "CONGRESS" word, active day tab, featured star |
| `textOnDark` | `#FFFFFF` | Text on navy |
| `textOnDarkMuted` | `#A9B8DC` | Subtitles on navy |
| `textPrimary` | `#0B1B45` | Text on white |
| `textMuted` | `#6B7A99` | Secondary text |
| `success` | `#22A06B` | Answered chip, success states |
| `warning` | `#F59E0B` | Updated chip |
| `danger` | `#E5484D` | Errors, cancelled |
| `border` | `#E3E8F4` | Dividers, input borders |

Primary button gradient: `LinearGradient(left→right, #2F6BFF → #4FC3F7)`. Screen background: vertical `LinearGradient(bgNavy900 → bgNavy700)`.

### 7.2 Typography
Font: **Inter** (fallback: system). Weights 400/500/600/700/800.

| Style | Size / Weight | Use |
|---|---|---|
| `display` | 28 / 800 | Welcome title "NESTLÉ CONGRESS" |
| `h1` | 22 / 700 | Screen hero titles, greeting |
| `h2` | 18 / 700 | Section titles ("Quick Access") |
| `title` | 15 / 700 | Card titles, session titles |
| `body` | 13 / 400 | Descriptions |
| `caption` | 11 / 500 | Meta, chips, tags |
| `overline` | 10 / 700, letter-spacing 0.8, uppercase | Category labels ("KEYNOTE", "FEATURED EVENT") |

### 7.3 Shape, spacing, elevation

- Spacing scale: 4, 8, 12, 16, 20, 24, 32. Screen horizontal padding 20
- Radius: card 20, input 14, chip 999, button 14, badge 24, bottom sheet 28 (top corners)
- Elevation: cards use soft shadow `0 8 24 rgba(7,26,74,0.12)`
- Touch targets ≥ 44×44

### 7.4 Reusable components (build these first)
`AppScaffold` (gradient bg, safe area, optional back button + title + trailing icon), `HeroCard` (icon tile + title + subtitle), `WhiteSheet` (rounded top white container), `AppTextField` (leading icon, trailing visibility toggle, error text), `PrimaryButton` (gradient, loading state, trailing icon), `SocialButton`, `FilterChip`, `SectionHeader` (title + "View All"), `SessionTile`, `SpeakerTile`, `QuickAccessTile`, `ResourceTile`, `QuestionTile`, `PollOptionTile` (with progress bar), `StatCard`, `EmptyState`, `ErrorState` (with Retry), `SkeletonLoader`, `StatusChip`, `BottomNavBar` (Home, Profile).

### 7.5 Iconography
Use `lucide_icons` (or Material Symbols Rounded). Icon tiles are 44×44 rounded-14 squares with a tinted background.

---

## 8. Mobile Screen Specifications

**Global rules for every screen**

- Each data screen implements 4 states: **Loading** (skeleton), **Empty** (illustration/icon + message), **Error** (message + Retry button), **Content**
- Pull-to-refresh on all list screens
- Back button (top-left, 40×40 rounded tile with chevron) on every screen except Home and Profile
- Bottom navigation (Home | Profile) shows **only** on Home and Profile. All other screens are pushed on top without it
- Routes use `go_router`; unauthenticated users are redirected to `/welcome`
- Text must never wrap mid-token: times like `08:30 AM` use a fixed-width column with `softWrap: false` (see Appendix B)

### Route Map

| Route | Screen |
|---|---|
| `/welcome` | Login (Welcome Back) |
| `/register` | Create Account |
| `/verify-email` | Verify Email (OTP) |
| `/forgot-password`, `/reset-password` | Password reset |
| `/home` | Home |
| `/quick-access` | Quick Access |
| `/agenda`, `/agenda/:sessionId` | Agenda, Session Detail |
| `/speakers`, `/speakers/:id` | Speakers, Speaker Detail |
| `/name-tag` | My Name Tag |
| `/venue` | Venue |
| `/voting`, `/voting/history` | Live Voting, Poll History |
| `/qna`, `/qna/mine` | Ask Q&A, My Questions |
| `/resources` | Resources |
| `/exhibitors`, `/exhibitors/:id` | Exhibitors, Exhibitor Detail |
| `/notifications` | Notifications |
| `/profile`, `/profile/edit`, `/profile/certificates`, `/settings` | Profile area |

---

### 8.1 Welcome / Login (`/welcome`)  *(Screenshot 1)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/01_login.png" alt="01_login" width="260"></div>
**Layout:** Navy gradient background → top branding block → white login card → bottom feature chips.

| Element | Spec |
|---|---|
| Event pill | Outlined pill, text `NESTLÉ MEDICAL CONGRESS`, overline style, gold border |
| Title | Two lines: `NESTLÉ` (white) / `CONGRESS` (gold), `display` style, centered |
| Divider | Short gold line under title |
| Tagline | `The Next Era of Nutrition & Health` (from `event.tagline`), `textOnDarkMuted` |
| Card | White, radius 28, padding 20 |
| Card header | Left: `Welcome Back` (h2) + `Sign in to continue your congress experience` (caption muted). Right: 44×44 blue rounded tile with shield icon |
| Email field | Leading mail/user icon, placeholder `Enter your email`, keyboard `emailAddress`, autofill hints |
| Password field | Leading lock icon, placeholder `Enter your password`, trailing eye toggle |
| Sign In button | Full width, gradient, label `Sign In`, trailing arrow →; loading spinner replaces arrow while submitting |
| Divider | Centered caption `OR CONTINUE WITH` |
| Social row | Two equal buttons: **G** (Google) and **Apple** logo. Hidden entirely when feature flags are OFF |
| Forgot link | Centered `Forgot password?` with small lock icon, primary color → `/forgot-password` |
| Footer text | `Don't have an account?` + `Create Account →` (gold/bold) → `/register` |
| Feature chips (bottom) | 3 translucent tiles: `Global Experts`, `Knowledge Sessions`, `Networking & Opportunities` (icon + 2-line label) |

**Behavior:** Validate on submit: email format, password non-empty. Call `POST /auth/login`. On `EMAIL_NOT_VERIFIED` → navigate to `/verify-email` with the email and auto-trigger resend. On other errors show inline red text under the form (use backend `message`). Disable the button while loading. Keyboard `done` submits.

### 8.2 Create Account (`/register`)  *(Screenshot 2)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/02_register.png" alt="02_register" width="260"></div>

| Element | Spec |
|---|---|
| Title | `Join the` (white, h1) / `NESTLÉ` (white) / `CONGRESS` (gold) |
| Subtitle | `Create your attendee profile and access sessions, resources, voting and Q&A.` |
| Card fields (in order) | `Full name` (person icon), `Email address` (mail icon), `Hospital / Organization` (building icon), `Create password` (lock icon + eye toggle) |
| Terms row | Checkbox + `I agree to the congress terms, privacy policy and attendee guidelines.` The words *terms*, *privacy policy*, *attendee guidelines* are tappable links (open in-app web view of CMS pages) |
| Button | `Create Account` with person-plus icon, gradient |
| Divider | `OR SIGN UP WITH` + Google / Apple buttons (flag-controlled) |
| Footer | `Already have an account?` + `Sign In` → `/welcome` |

**Validation (client + server):** name 2–100 chars; email valid; organization 2–150 chars; password policy (Section 5.1) with live checklist; terms must be ticked (button disabled otherwise). Backend field errors map to the matching field. `EMAIL_EXISTS` shows under email: "An account with this email already exists."

### 8.3 Verify Email (`/verify-email`)  *(inferred)*
6-box OTP input (auto-advance, paste support, SMS/email autofill), caption showing masked email (`h***@example.com`), `Verify` button, `Resend code` link with 60-second countdown, `Change email` link. Errors: `INVALID_CODE`, `CODE_EXPIRED`, `TOO_MANY_ATTEMPTS`. Success → home (or "Awaiting approval" screen if approval mode ON).

### 8.4 Forgot / Reset Password *(inferred)*
Forgot: email field + `Send code`. Always shows success message. Reset: email (prefilled), 6-digit code, new password, confirm password → success toast → `/welcome`.

---

### 8.5 Home (`/home`)  *(Screenshot 3)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/03_home.png" alt="03_home" width="260"></div>
**Layout (scrollable, navy bg, bottom nav):**

1. **Top row:** left overline `NESTLÉ MEDICAL CONGRESS`; right bell icon button (tile) with a small red dot when `unread_count > 0` → `/notifications`
2. **Greeting:** `Welcome Back,` / `{first name or full_name} 👋` (h1). Use `user.full_name` as-is (e.g. "Dr. Testing")
3. **Search bar:** rounded field with search icon, placeholder `Search sessions, speakers, topics...`, trailing cyan circular filter/arrow button. Submitting opens a **Global Search** results page (sessions, speakers, resources, exhibitors in grouped sections) via `GET /search?q=`
4. **Featured Event card:** gradient blue card, overline chip `FEATURED EVENT` (gold), title `event.name` (white, 2 lines), caption `{start} - {end}, {year} • {city}, {country}`, right side circular icon (leaf/drop). Tap opens an "About the event" bottom sheet (description from the event record)
5. **Quick Access header:** `Quick Access` + `View All ›` → `/quick-access`
6. **Quick Access grid:** 4 columns × 2 rows of icon tiles (blue-gradient square icon + label below): `Agenda`, `Speakers`, `Name Tag`, `Venue`, `Voting`, `Ask Q&A`, `Resources`, `Exhibitors` → routes `/agenda`, `/speakers`, `/name-tag`, `/venue`, `/voting`, `/qna`, `/resources`, `/exhibitors`
7. **Upcoming Sessions header:** `Upcoming Sessions` + `View All ›` → `/agenda`
8. **Upcoming list:** up to 5 `SessionTile`s (same component as Agenda)
9. **Bottom nav:** `Home` (active, house icon) | `Profile` (person icon)

**API:** `GET /events/current`, `GET /me`, `GET /notifications/unread-count`, `GET /events/{id}/sessions/upcoming?limit=5`. Load in parallel; each section handles its own loading/error.

### 8.6 Quick Access (`/quick-access`)  *(Screenshot 4)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/04_quick_access.png" alt="04_quick_access" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back tile, title `Quick Access`, trailing grid-icon tile toggling **grid (2 columns) / list** layout |
| Hero card | Cyan-blue gradient; icon tile (sparkles); title `Explore Congress Tools`; subtitle `Everything you need for the full event experience` |
| White sheet | Search field `Search quick access`, filter chips `All`, `Event`, `Interactive`, `Tools` |
| Tiles (2-col grid) | Icon tile, title, description, tag chip, trailing arrow |

**Tile definitions (static config in app, titles localized):**

| Tile | Description | Tag | Route |
|---|---|---|---|
| Agenda | View full congress schedule | Event | `/agenda` |
| Speakers | Explore global medical experts | Event | `/speakers` |
| Name Tag | Access your digital badge | Tools | `/name-tag` |
| Venue | Location, facilities and directions | Event | `/venue` |
| Voting | Join live polls and see results | Interactive | `/voting` |
| Ask Q&A | Ask questions and upvote topics | Interactive | `/qna` |
| Resources | Presentations, documents and media | Tools | `/resources` |
| Exhibitors | Meet congress partners and sponsors | Event | `/exhibitors` |

Chip filters by tag; search filters by title/description (client-side, case-insensitive). Empty state: "No tools match your search."

### 8.7 Congress Agenda (`/agenda`)  *(Screenshot 5)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/05_agenda.png" alt="05_agenda" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back tile, title `Congress Agenda`, trailing search icon tile (expands an inline search field above the list) |
| Day hero card | Gold calendar icon tile; `Day 1 Schedule` (h2, white); `{weekday}, {Month} {day}, {year}` computed from the selected date in event timezone |
| Day selector | Two (or N) large tabs: `Day 1` / `May 22` and `Day 2` / `May 23`. Selected = gold fill with dark text; unselected = translucent navy. Horizontally scrollable if > 3 days |
| White sheet | Header row: `Today's Sessions` (h2; label becomes `Sessions` when the selected day ≠ today) + `Reset` button (refresh icon) |
| Category chips | `All`, then categories of type `session` (seed: Keynote, Nutrition, Research). Selected = primary blue filled |
| Session list | `SessionTile` per session |

**SessionTile layout:** Left column (fixed 56 px width, no wrap): start time `08:30` over `AM`. Middle: category icon tile (tinted by category), then overline category (`KEYNOTE` gold for keynote, `NUTRITION` blue, `RESEARCH` purple), title (title style, max 2 lines), row with pin icon + room or speaker name (`Main Auditorium`, `Dr. Ahmed`) caption. Right: bookmark icon (outline → filled blue when saved). First/next-up session may have a gold border highlight (the session currently live or next to start).

- Tap tile → `/agenda/:sessionId`. Tap bookmark → optimistic toggle; on failure revert and show snackbar
- Status chips: `Updated` (amber), `Cancelled` (red)
- Live indicator: red dot + `LIVE` when `start_at <= now < end_at`

**Session Detail (`/agenda/:sessionId`):** app bar with bookmark; category chip; title (h1); time range with timezone abbreviation; room with pin icon; status banner if changed/cancelled; `About this session` description; `Speakers` list (tap → speaker detail); `Ask a question` button → `/qna` prefilled with `session_id`.

**API:** `GET /events/{id}/agenda?date=2026-05-22&category_id=&q=`, `GET /sessions/{id}`, `PUT|DELETE /me/bookmarks/session/{id}`.

### 8.8 Speakers (`/speakers`)  *(Screenshot 6)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/06_speakers.png" alt="06_speakers" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, title `Speakers`, trailing star tile = **Featured only** toggle (filled gold when on) |
| Hero card | Icon tile (people); title `Global Medical Experts`; subtitle `Meet speakers from nutrition, research and healthcare` |
| Search row | `Search speakers` field with trailing filter icon (opens bottom sheet with Country filter) |
| Chips | `All`, then categories of type `speaker` (seed: Nutrition, Research, Pediatric); horizontally scrollable |
| Speaker card | Avatar circle (photo or initials, e.g. `SJ`, with gold ring for featured); overline `FEATURED SPEAKER` (featured only); name `Dr. Sarah Johnson`; designation `Pediatric Nutrition Specialist`; pin + country (`United Kingdom`); blue chip with first assigned session title; trailing star (featured) or empty star outline + chevron |

Tap card → `/speakers/:id`: large avatar, name, designation, organization + country, tags (specializations), `Biography`, `Sessions` list (SessionTiles).
Search debounce 300 ms, server-side. Pagination: cursor, 20 per page, infinite scroll.

### 8.9 My Name Tag (`/name-tag`)  *(Screenshot 7)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/07_name_tag.png" alt="07_name_tag" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, title `My Name Tag`, trailing printer icon (gold) → system print/share of the badge as PDF/image |
| Badge card | White card radius 24 centered on navy. Header strip: cyan-blue gradient with text `NESTLÉ MEDICAL` / `CONGRESS 2026` |
| Avatar | 80 px circle with gold ring; photo or initials (`HL`) |
| Name | `Huda Latheef` (h2, bold) |
| Subtitle | `{designation} • {attendee_type}` e.g. `Flutter Developer • Attendee`, followed by small gold ribbon/medal icon |
| Info rows | (1) icon `Badge ID` / `NMC-2026-001`; (2) pin `Location` / `Dubai, UAE`; (3) calendar `Congress Date` / `22 - 23 May 2026` |
| QR | Centered, 160×160, white background, quiet zone, generated client-side from `qr_payload` (`qr_flutter`). Caption `Show this QR code at check-in` |

Behavior: on open, request screen brightness boost (restore on exit). Cached for offline (badge ID + QR payload). If `status = revoked`, show red banner "Badge not active, contact registration desk" and blur QR. After check-in show green chip `Checked in`.
**API:** `GET /me/badge`.

### 8.10 Venue (`/venue`)  *(Screenshot 8)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/08_venue.png" alt="08_venue" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, `Venue`, trailing gold navigation-arrow tile → open directions in native maps |
| Venue header | `Dubai International Convention & Exhibition Center` (h1 white) and calendar + `22 - 23 May 2026` |
| Address card | White card, pin icon tile, overline `Venue Address`, text `World Trade Centre, Dubai, United Arab Emirates` |
| Map | Card labelled `Map Preview` chip (top-left); map with gold pin marker. Use `google_maps_flutter` (or static map image fallback). Tap opens native maps |
| Facilities | White card titled `Venue Facilities`, 2×2 grid of chips with icons: `Free Wi-Fi`, `Parking`, `Catering`, `Accessible` (from `venue_facilities`, enabled only) |
| Notices | Optional list of organizer notices below facilities |

If map fails or coordinates absent → show a static "Map unavailable" placeholder; address and facilities always remain visible.
**API:** `GET /events/{id}/venue`.

### 8.11 Live Voting (`/voting`)  *(Screenshot 9)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/09_voting.png" alt="09_voting" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, `Live Voting`, trailing gold ballot icon → `/voting/history` |
| Hero card | Gold bar-chart icon tile; `Audience Interaction`; `Swipe polls, choose answers, and submit your vote` |
| Pager dots | One dot per poll, current is elongated blue |
| Poll card (white) | Top chips: status chip: gold `● VOTING` while active and not yet voted, green `● VOTED` after the user has voted (the reference image shows `VOTED`), `PAUSED` grey, `CLOSED` red + category label (`Audience Feedback`); question (h2, e.g. `How would you rate the current session?`); caption `101 total votes` (live) |
| Option tile | Rounded tile: radio circle (left), label, percentage (right, bold), thin progress bar under label, small caption `55 votes` right-aligned under bar. Selected tile: blue border + filled check circle. Progress bar and numbers appear only when results are visible |
| Bottom bar | Left arrow button (previous poll), center gradient `Next Poll` (becomes `Submit Vote` when an unsubmitted option is selected on an active poll; becomes `Voted ✓` disabled after voting), right arrow button (next poll) |

**Behavior**

1. Load `GET /polls/active`. Pages swipe horizontally (`PageView`)
2. Tap an option → selects locally (single-choice replaces selection)
3. `Submit Vote` → `POST /polls/{id}/votes` with `Idempotency-Key` (UUID v4 per attempt) → on success lock options, show results, snackbar "Vote submitted"
4. Errors: `ALREADY_VOTED` (show results, lock), `POLL_CLOSED` (refresh poll), `POLL_NOT_ACTIVE`, `RATE_LIMITED`; network failure → keep selection, show Retry
5. Subscribe to WebSocket topic `polls`; on `poll.results_updated` update counts/percentages with a 300 ms animated bar; on `poll.activated` insert a new page and show a snackbar "New poll available"; on `poll.closed` mark closed
6. Empty state: "No active polls right now. Polls will appear here during sessions."

**Poll History (`/voting/history`):** list of closed polls the user voted in or that are public, each showing question and final results.

### 8.12 Ask Q&A (`/qna`)  *(Screenshot 10)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/10_qna.png" alt="10_qna" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, `Ask Q&A`, trailing gold chat icon → `/qna/mine` |
| Hero card | Blue chat icon tile; `Ask the Experts`; `Submit your questions and vote for top discussions` |
| Composer card (white) | Title `Write your question`; multiline field (3 lines, placeholder `Type your question for the speaker...`, counter `0/500`); category chips `General`, `Nutrition`, `Research`, `Clinical` (default General); optional `Link to session` selector (bottom sheet of today's sessions); gradient button `Submit Question` with send icon |
| Tabs | Segmented control: `Popular` · `Recent` (default, gold when selected) · `Answered` |
| Question tile | Left: upvote column (chevron-up + count, e.g. `24`; filled blue if upvoted). Middle: chips (category in blue, `Answered` in green), question text (title style), footer: small avatar/initial + `Dr. Ahmed` (answerer or session speaker) and right-aligned `↩ Reply` link (opens answer thread bottom sheet; moderators/speakers see an inline answer composer) |

**Behavior:** Submit disabled until ≥ 10 chars. After submit: clear field, toast "Question submitted" (or "Submitted for moderation. It will appear once approved" when moderation ON). List refreshes. Infinite scroll, 20/page, server-side sort by tab. Upvote is optimistic with rollback on failure. WebSocket `question.published` prepends to Recent; `question.answered` updates tile.
**Answer sheet:** shows full question, answer text, answerer name/role, timestamp.
**My Questions (`/qna/mine`):** the user's questions with status chips `Pending`, `Published`, `Answered`, `Rejected` (with reason).

### 8.13 Resources (`/resources`)  *(Screenshot 11)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/11_resources.png" alt="11_resources" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Back, `Resources`, trailing gold folder icon (toggles Saved filter shortcut) |
| Hero card | Cloud-download icon tile; `Congress Library`; `Access presentations, documents and media files` |
| Search | `Search resources` (debounce 300 ms) |
| Chips | `All`, `PDF`, `Slides`, `Videos`, `Saved` |
| Resource tile | Colored icon tile by type (PDF red, Slides orange, Video purple); overline type label (`PDF`, `SLIDES`); title (1 line ellipsis, e.g. `Congress Scientific Prog…`); description (1 line ellipsis); file-size row with small icon (`4.2 MB`); right column: bookmark icon (top), download icon (bottom) |

**Behavior:** Tap tile → request access URL → PDF opens in in-app viewer (`flutter_pdfview` / system viewer), Slides download then open with system share sheet, Videos open in in-app player (`video_player`/`chewie`) or external link. Download icon saves to device and shows progress. Bookmark toggles optimistic. Errors: `RESOURCE_UNAVAILABLE`, `DOWNLOAD_FAILED` (Retry), `UNSUPPORTED_FORMAT`.
**API:** `GET /resources?type=&q=&saved=true`, `GET /resources/{id}/access`, `PUT|DELETE /me/bookmarks/resource/{id}`.

### 8.14 My Profile (`/profile`)  *(Screenshot 12)*

<div style="page-break-inside:avoid"><b>Reference UI (build to match):</b><br><img src="ui_reference/screens/12_profile.png" alt="12_profile" width="260"></div>

| Element | Spec |
|---|---|
| App bar | Title `My Profile` (centered, back tile on left only when pushed), trailing gear → `/settings` |
| Header | Avatar 88 px with gold ring and small gold pencil badge (tap → pick image: camera/gallery, upload via `POST /me/avatar`); name `Huda Latheef`; subtitle `Medical Congress Attendee` (= `attendee_type` label); gold-outlined chip `ID: NMC-2026-001` |
| Info card (white) | Rows: mail icon `Email` / value; phone icon `Phone` / value; pin icon `Location` / value. Tap row or `Edit` → `/profile/edit` |
| Stats row | 3 stat cards: calendar `12` `Sessions` → `/agenda?saved=true`; bookmark `05` `Saved` → `/resources` with Saved chip; medal `03` `Certificates` → `/profile/certificates`. Numbers zero-padded to 2 digits |
| Bottom nav | Home | Profile (active) |

**Edit Profile (`/profile/edit`):** editable: full name, organization, designation, phone (E.164 validation), location. Read-only: email, badge ID. Save → `PATCH /me`.
**Certificates (`/profile/certificates`):** cards with event name, issue date, number, `Download PDF` button. Empty: "No certificates yet."

### 8.15 Settings (`/settings`)  *(inferred)*
Rows: Notification preferences (toggles: Event updates, Session reminders, Q&A responses, New resources), Change password, Terms of Service, Privacy Policy, Attendee Guidelines (web views from CMS), App version, `Request account deletion` (confirm modal), `Log out` (confirm modal).

### 8.16 Notifications (`/notifications`)  *(inferred)*
App bar `Notifications` + `Mark all read`. List tiles: type icon, title, body (2 lines), relative time, unread dot/bold. Tap → mark read + deep link. Empty: "You're all caught up."

### 8.17 Exhibitors (`/exhibitors`, `/exhibitors/:id`)  *(inferred, Quick Access shortcut)*
List: search, category chips (from `exhibitor` categories), tiles with logo, name, booth (`Booth A12`), short description. Detail: logo, name, booth, category, description, website button (opens browser), contact email (optional).

### 8.18 Global UI behaviors

- **Deep links:** `nmc://session/{id}`, `nmc://poll/{id}`, `nmc://question/{id}`, `nmc://resource/{id}`, `nmc://notifications`. Cold-start deep link waits for auth then routes
- **Snackbars** for success/error confirmations, floating above bottom nav
- **Force update:** if `GET /app/config` returns `min_app_version` > installed → blocking "Update required" screen
- **Maintenance mode:** if backend returns `503 MAINTENANCE` show a friendly full-screen message with Retry

---

## 9. Admin Portal

**Stack:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, React Hook Form + Zod, TanStack Table, dnd-kit (reorder), Recharts, `html5-qrcode` (scanner), TipTap (rich text).

**Layout:** Top bar (logo, event switcher (single event in P1), user menu, logout) + collapsible left sidebar + content area. Sidebar items are filtered by role.

### Sidebar Navigation

| Item | Route | Roles |
|---|---|---|
| Dashboard | `/` | organizer, admin, moderator |
| Event Setup | `/event` | organizer, admin |
| Sessions | `/sessions` | organizer, admin |
| Speakers | `/speakers` | organizer, admin |
| Categories | `/categories` | organizer, admin |
| Polls | `/polls` | organizer, admin |
| Q&A Moderation | `/qna` | moderator, organizer, admin |
| Resources | `/resources` | organizer, admin |
| Exhibitors | `/exhibitors` | organizer, admin |
| Attendees | `/attendees` | organizer, admin |
| Certificates | `/certificates` | organizer, admin |
| Announcements | `/announcements` | organizer, admin |
| Check-in | `/checkin` | checkin_staff, organizer, admin |
| Users & Roles | `/users` | admin |
| Audit Log | `/audit` | admin |
| Settings | `/settings` | admin |

### 9.1 Dashboard

- Summary cards: Registered attendees, Checked in, Active polls, Pending questions, Resources published, Downloads (24 h)
- Charts: registrations per day (line), check-ins per hour (bar), votes per poll (horizontal bar), questions by status (donut)
- Live widget: currently running session + next session

### 9.2 Event Setup
Form fields: name, tagline, description (rich text), start date/time, end date/time, timezone (default `Asia/Dubai`), city, country, hero image, branding colors (read-only defaults), venue (name, address, lat, lng, notices), facilities (toggle + label + icon), settings toggles: `registration_open`, `require_approval`, `qna_moderation_enabled`, `google_signin_enabled`, `apple_signin_enabled`. Save → `PATCH /admin/events/{id}`; changes reflect in the app on next fetch / `event.updated` WS message.

### 9.3 Sessions

- Table: Time, Title, Category, Room, Speakers, Status, Visibility, Actions. Filters: day, category, status. Search by title
- Create/Edit modal: title, summary, description, category, date, start time, end time, room, speakers (multi-select with order), visibility (draft/published), status. Validation: end > start; warn on room/speaker overlap (non-blocking warning, "Dr. X is already in Session Y at this time")
- Actions: Publish/Unpublish, Cancel (optional reason → notifies bookmarkers), Duplicate, Delete (confirm)
- Changing time/room/title of a published session sets status `changed` and sends a notification to users who bookmarked it

### 9.4 Speakers & Categories

- Speakers: table with photo, name, designation, organization, country, specializations, featured toggle; modal form with photo upload (JPG/PNG ≤ 5 MB), biography (rich text), link to a user account (optional, enables the `speaker` role flows)
- Categories: tabbed by type (Session, Speaker, Question, Resource, Exhibitor); name, slug, color, order (drag-and-drop)

### 9.5 Polls

- Table: Question, Session, Status, Votes, Starts, Ends, Actions
- Create/Edit: question, category label (e.g. Audience Feedback), session (optional), type (single/multiple), max choices, options (2–10, drag reorder), results visibility (after_vote/live/after_close), starts_at/ends_at (optional), status
- Controls: **Activate**, **Pause**, **Resume**, **Close**, **Duplicate**, **Reset votes** (typed confirmation "RESET", audit logged)
- Live results panel (bars, count, total) updating through WebSocket
- Cannot edit options after votes exist (only question text and visibility)

### 9.6 Q&A Moderation

- Tabs: Pending | Published | Answered | Hidden | Rejected, with counts and live updates
- Row: question, author (name, org), category, session, upvotes, flags (profanity), submitted time
- Actions: Approve, Hide, Reject (reason select + free text, sent to author), Mark answered, Answer (rich text ≤ 2,000 chars), Assign to speaker, Flag
- Keyboard shortcuts: `A` approve, `H` hide, `R` reject, `↓/↑` navigate
- Moderation history drawer per question

### 9.7 Resources

- Table: Title, Type, Size, Version, Status, Downloads, Updated, Actions
- Upload flow: request pre-signed upload URL (`POST /admin/media/upload-url`) → browser PUTs directly to S3 with progress bar → `POST /admin/resources` with metadata
- Fields: title, description, type, category, session (optional), visibility (published/unpublished), file or external URL
- Replace file → increments `version` (previous kept in S3 versioning)
- Publish/Unpublish toggle. Unpublishing triggers no notification; publishing optionally sends `new_resource` notification (checkbox)

### 9.8 Exhibitors
Table + modal: name, logo upload, booth, category, description, website, contact email, order, published toggle.

### 9.9 Attendees

- Table: Name, Email, Organization, Badge ID, Status, Checked in, Registered. Search, filter by status/checked-in
- Row actions: View, Approve (pending_approval → active), Suspend/Unsuspend, Resend verification, Revoke/Regenerate badge
- Export CSV (name, email, organization, badge ID, status, checked-in time); **Import CSV** (columns: full_name, email, organization, designation; creates pending accounts and sends an invite email with a set-password OTP)

### 9.10 Certificates
Select attendees (all checked-in or manual selection) → Issue. Table of issued certificates with Download, Revoke, Resend email. Template settings (logo, signatory name, title).

### 9.11 Announcements
Compose: title (≤ 60), body (≤ 240), optional deep link (picker for session/poll/resource), audience (All / Checked-in only / Speakers), send now or schedule. Status: Draft → Scheduled → Sent. Delivery stats (sent, failed).

### 9.12 Check-in (`/checkin`)
Full-screen camera scanner. On scan: `POST /admin/checkin/verify {token}` → big result card: ✅ green "Checked in" with name, organization, badge ID; 🟡 amber "Already checked in at {time}"; 🔴 red "Invalid / Revoked / Suspended". Auto-resets after 3 s. Manual search by badge ID/name. Counter of today's check-ins.

### 9.13 Users & Roles (admin)
Table (Name, Email, Role, Status, Last login). Create user (name, email, temp password or invite, role). Change role (confirm modal; admin cannot demote themselves or remove the last admin). Suspend/Delete. Bulk actions.

### 9.14 Audit Log & Settings

- Audit log: filter by actor, action, entity, date; JSON metadata viewer; export CSV; read-only
- Settings: platform name, support email, email sender name/reply-to, `min_app_version` (ios/android), maintenance mode toggle, profanity word list, feature flags

---

## 10. Notifications

### 10.1 Triggers

| Trigger | Channel | Recipients | Title | Body (template) | Deep link |
|---|---|---|---|---|---|
| Registration | Email | New user | Verify your email | Your code is {{code}}. Expires in 15 minutes | n/a |
| Password reset | Email | User | Reset your password | Your code is {{code}}. Expires in 15 minutes | n/a |
| Account approved | Email + push | User | You're approved! | Your congress account is active | `nmc://home` |
| Session reminder | Push + in-app | Users who bookmarked | Starting in 15 minutes | {{title}}: {{room}} | `nmc://session/{id}` |
| Session changed | Push + in-app | Bookmarkers | Schedule update | {{title}} has changed: {{summary}} | `nmc://session/{id}` |
| Session cancelled | Push + in-app | Bookmarkers | Session cancelled | {{title}} has been cancelled | `nmc://session/{id}` |
| Poll activated | Push + in-app | All checked-in attendees | New poll is live | {{question}} | `nmc://poll/{id}` |
| Question answered | Push + in-app | Question author + upvoters | Your question was answered | {{answerer}} replied | `nmc://question/{id}` |
| Question rejected | In-app | Author | Question not published | Reason: {{reason}} | `nmc://qna/mine` |
| New resource | Push + in-app | All attendees | New resource available | {{title}} | `nmc://resource/{id}` |
| Certificate issued | Email + push | Attendee | Your certificate is ready | Download it from your profile | `nmc://certificates` |
| Announcement | Push + in-app | Per audience | {{title}} | {{body}} | optional |

### 10.2 Implementation

- Background worker (**ARQ** on Redis) handles: email sending, push fan-out (FCM batch of 500), session reminders (scheduled job every minute looking at sessions starting in 15 ± 1 min), poll auto-transitions, scheduled announcements, certificate PDF generation
- Email via **AWS SES** (SPF, DKIM, DMARC configured); templates stored in `email_templates` table (key, subject, html, text, variables) editable by admin
- Push via **Firebase Cloud Messaging**; device tokens stored in `device_tokens`; remove tokens when FCM returns `UNREGISTERED`
- `notifications` row created for each recipient (in-app inbox); push is best-effort
- Failed email/push: retry up to 3 times with exponential backoff (30 s, 2 min, 10 min); status recorded
- Users can disable categories in Settings (`notification_preferences`); transactional emails (OTP/reset) cannot be disabled

---

## 11. Database Schema

**Engine:** PostgreSQL 16. Extensions: `pgcrypto` (UUIDs via `gen_random_uuid()`), `citext` (emails), `pg_trgm` (search). All timestamps `TIMESTAMPTZ` (UTC). All PKs UUID. Soft-delete column `deleted_at` where noted. Managed by **Alembic** migrations (never edit the DB by hand).

### 11.1 Entity Relationship Overview
```
events ──< venues ──< venue_facilities
events ──< sessions >──< speakers  (via session_speakers)
events ──< categories
events ──< polls ──< poll_options ; polls ──< votes >── users
events ──< questions ──< answers ; questions ──< question_upvotes >── users
events ──< resources ; events ──< exhibitors ; events ──< announcements
users ──< bookmarks ; users ──< badges ; users ──< notifications
users ──< refresh_tokens ; users ──< device_tokens ; users ──< certificates
users ──< audit_logs
```

### 11.2 Enums
`user_role`: attendee, speaker, moderator, organizer, admin, checkin_staff
`user_status`: pending_verification, pending_approval, active, suspended
`session_status`: scheduled, changed, cancelled
`visibility`: draft, published
`category_type`: session, speaker, question, resource, exhibitor
`poll_status`: draft, scheduled, active, paused, closed
`poll_type`: single, multiple
`results_visibility`: after_vote, live, after_close
`question_status`: pending, published, answered, hidden, rejected
`resource_type`: pdf, slides, video, document, link
`bookmark_target`: session, resource
`badge_status`: active, revoked
`notification_status`: pending, sent, failed
`otp_purpose`: verify_email, reset_password

### 11.3 Core Tables

**users**

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| email | CITEXT | UNIQUE, NOT NULL (stored normalized) |
| password_hash | VARCHAR(255) | NULLABLE (null for social-only) |
| google_sub | VARCHAR(255) | UNIQUE, NULLABLE |
| apple_sub | VARCHAR(255) | UNIQUE, NULLABLE |
| full_name | VARCHAR(100) | NOT NULL |
| organization | VARCHAR(150) | NOT NULL |
| designation | VARCHAR(120) | NULLABLE |
| attendee_type | VARCHAR(50) | DEFAULT 'Medical Congress Attendee' |
| phone | VARCHAR(20) | NULLABLE (E.164) |
| location | VARCHAR(120) | NULLABLE |
| avatar_url | TEXT | NULLABLE (S3 key) |
| role | user_role | NOT NULL DEFAULT attendee |
| status | user_status | NOT NULL DEFAULT pending_verification |
| email_verified_at | TIMESTAMPTZ | NULLABLE |
| terms_accepted_at | TIMESTAMPTZ | NOT NULL |
| last_login_at | TIMESTAMPTZ | NULLABLE |
| failed_login_count | INT | DEFAULT 0 |
| locked_until | TIMESTAMPTZ | NULLABLE |
| notification_preferences | JSONB | DEFAULT '{"event_updates":true,"session_reminders":true,"qna":true,"resources":true}' |
| created_at / updated_at | TIMESTAMPTZ | DEFAULT now() |
| deleted_at | TIMESTAMPTZ | NULLABLE |

**email_otps**: id PK; user_id FK→users (CASCADE); purpose otp_purpose; code_hash VARCHAR(255); expires_at; attempts INT DEFAULT 0; consumed_at NULLABLE; created_at. Index (user_id, purpose, created_at DESC).

**refresh_tokens**: id PK; user_id FK; family_id UUID (index); token_hash CHAR(64) UNIQUE; device_info VARCHAR(200); expires_at; revoked_at NULLABLE; replaced_by UUID NULLABLE; created_at.

**device_tokens**: id PK; user_id FK; platform ENUM(ios, android); fcm_token TEXT UNIQUE; app_version; last_seen_at; created_at.

**events**

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(200) | NOT NULL |
| tagline | VARCHAR(200) | NULLABLE |
| description | TEXT | NULLABLE |
| start_at / end_at | TIMESTAMPTZ | NOT NULL, CHECK end_at > start_at |
| timezone | VARCHAR(60) | NOT NULL DEFAULT 'Asia/Dubai' |
| city / country | VARCHAR(80) | NOT NULL |
| hero_image_url | TEXT | NULLABLE |
| is_current | BOOLEAN | DEFAULT false (partial unique index: only one true) |
| settings | JSONB | DEFAULT '{"registration_open":true,"require_approval":false,"qna_moderation_enabled":true,"google_signin_enabled":false,"apple_signin_enabled":false}' |
| created_at / updated_at | TIMESTAMPTZ | |

**venues**: id PK; event_id FK UNIQUE; name VARCHAR(200); address TEXT; latitude NUMERIC(9,6) NULL; longitude NUMERIC(9,6) NULL; notices JSONB DEFAULT '[]'.
**venue_facilities**: id PK; venue_id FK; key VARCHAR(40); label VARCHAR(60); icon VARCHAR(40); enabled BOOL DEFAULT true; display_order INT. UNIQUE (venue_id, key).

**categories**: id PK; event_id FK; type category_type; name VARCHAR(60); slug VARCHAR(60); color VARCHAR(9) NULL; display_order INT DEFAULT 0. UNIQUE (event_id, type, slug).

**sessions**

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| event_id | UUID | FK, NOT NULL, indexed |
| category_id | UUID | FK→categories, NOT NULL |
| title | VARCHAR(200) | NOT NULL |
| summary | VARCHAR(300) | NULLABLE |
| description | TEXT | NULLABLE |
| start_at / end_at | TIMESTAMPTZ | NOT NULL, CHECK end_at > start_at |
| room | VARCHAR(120) | NULLABLE |
| status | session_status | DEFAULT scheduled |
| status_note | VARCHAR(300) | NULLABLE (cancellation/change reason) |
| visibility | visibility | DEFAULT draft |
| display_order | INT | DEFAULT 0 |
| created_at / updated_at | TIMESTAMPTZ | |
Index: (event_id, start_at), (event_id, category_id).

**speakers**: id PK; event_id FK; user_id FK→users NULL; name VARCHAR(120); designation VARCHAR(160); organization VARCHAR(160) NULL; country VARCHAR(80) NULL; biography TEXT NULL; photo_url TEXT NULL; is_featured BOOL DEFAULT false; display_order INT; visibility; created_at/updated_at. GIN trigram index on name.
**speaker_categories**: speaker_id FK, category_id FK, PK(both).
**session_speakers**: session_id FK, speaker_id FK, display_order INT, PK(session_id, speaker_id).

**bookmarks**: id PK; user_id FK; target_type bookmark_target; target_id UUID; created_at. UNIQUE (user_id, target_type, target_id).

**badges**: id PK; user_id FK UNIQUE per event; event_id FK; badge_code VARCHAR(30) UNIQUE; qr_token_hash CHAR(64) UNIQUE; qr_token_enc TEXT (token encrypted with app key so it can be re-shown to the owner); status badge_status DEFAULT active; checked_in_at NULL; checked_in_by FK NULL; issued_at.

**polls**

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| event_id | UUID | FK |
| session_id | UUID | FK NULL |
| question | VARCHAR(300) | NOT NULL |
| label | VARCHAR(60) | DEFAULT 'Audience Feedback' |
| type | poll_type | DEFAULT single |
| max_choices | INT | DEFAULT 1 |
| status | poll_status | DEFAULT draft |
| results_visibility | results_visibility | DEFAULT after_vote |
| starts_at / ends_at | TIMESTAMPTZ | NULLABLE |
| display_order | INT | DEFAULT 0 |
| created_by | UUID | FK |
| created_at / updated_at | TIMESTAMPTZ | |
**poll_options**: id PK; poll_id FK (CASCADE); label VARCHAR(150); display_order INT.
**votes**: id PK; poll_id FK; option_id FK; user_id FK; created_at; idempotency_key VARCHAR(64) NULL. UNIQUE (poll_id, user_id, option_id); index (poll_id, option_id).

**questions**: id PK; event_id FK; user_id FK; session_id FK NULL; speaker_id FK NULL; category_id FK; text VARCHAR(500); status question_status; upvote_count INT DEFAULT 0 (denormalized, updated in the same transaction); flagged BOOL DEFAULT false; reject_reason VARCHAR(300) NULL; moderated_by FK NULL; moderated_at NULL; created_at; updated_at. Indexes: (event_id, status, created_at DESC), (event_id, status, upvote_count DESC).
**question_upvotes**: id PK; question_id FK; user_id FK; created_at. UNIQUE (question_id, user_id).
**answers**: id PK; question_id FK; author_user_id FK; answer_text TEXT (≤ 2000); created_at; updated_at.

**resources**: id PK; event_id FK; session_id FK NULL; category_id FK NULL; title VARCHAR(200); description VARCHAR(300) NULL; type resource_type; storage_key TEXT NULL; external_url TEXT NULL; mime_type VARCHAR(100) NULL; file_size BIGINT NULL; version INT DEFAULT 1; visibility; download_count INT DEFAULT 0; published_at NULL; created_by FK; created_at/updated_at. CHECK (storage_key IS NOT NULL OR external_url IS NOT NULL). GIN trigram on title.

**exhibitors**: id PK; event_id FK; category_id FK NULL; name VARCHAR(160); booth VARCHAR(40) NULL; description TEXT NULL; logo_url TEXT NULL; website TEXT NULL; contact_email VARCHAR(255) NULL; display_order INT; visibility.

**notifications**: id PK; user_id FK; type VARCHAR(50); title VARCHAR(120); body VARCHAR(300); deep_link VARCHAR(200) NULL; read_at NULL; push_status notification_status DEFAULT pending; attempts INT DEFAULT 0; created_at. Index (user_id, read_at, created_at DESC).
**announcements**: id PK; event_id FK; title; body; deep_link NULL; audience ENUM(all, checked_in, speakers); status ENUM(draft, scheduled, sent); scheduled_at NULL; sent_at NULL; sent_count INT; failed_count INT; created_by FK; created_at.
**email_templates**: key VARCHAR(60) PK; subject; html; text; variables JSONB; updated_by; updated_at.
**email_log**: id PK; to_email; template_key; status notification_status; attempts; provider_message_id; error; created_at.

**certificates**: id PK; event_id FK; user_id FK; certificate_number VARCHAR(30) UNIQUE; file_key TEXT; status ENUM(issued, revoked); issued_by FK; issued_at. UNIQUE (event_id, user_id).

**cms_pages**: key VARCHAR(40) PK (`terms`, `privacy`, `guidelines`, `about`); title; body_markdown; updated_by; updated_at.
**app_settings**: key PK; value JSONB; updated_at. (min_app_version_ios/android, maintenance_mode, profanity_words)
**audit_logs**: id PK; actor_user_id FK NULL; action VARCHAR(80); entity_type VARCHAR(40); entity_id UUID NULL; metadata JSONB; ip INET NULL; created_at. Index (created_at DESC), (actor_user_id), (entity_type, entity_id).

### 11.4 Integrity Rules

- FKs everywhere with `ON DELETE` rules: user-owned rows CASCADE on hard delete; content rows RESTRICT
- Vote, upvote and bookmark uniqueness enforced by DB constraints, not just code
- `questions.upvote_count` and votes counts are updated inside the same transaction as the insert
- Required indexes: all FKs, `sessions(event_id,start_at)`, `polls(event_id,status)`, `questions(event_id,status,created_at)`, `resources(event_id,type,visibility)`, trigram indexes for search
- Deleting a user anonymizes (name → "Deleted user", email → hashed placeholder) and removes tokens, bookmarks, device tokens; keeps votes/questions anonymized for aggregate integrity

---

## 12. API Structure

Base URL: `/api/v1`. JSON only. Auth: `Authorization: Bearer <access_token>` unless marked **[Public]**. Field names are `snake_case`. Timestamps are ISO 8601 UTC (`2026-05-22T04:30:00Z`). IDs are UUIDs. OpenAPI docs auto-generated at `/docs`.

### 12.1 Standard Response Format
Success:
```json
{ "success": true, "data": { }, "meta": { "next_cursor": "eyJpZCI6...", "limit": 20, "total": 150 } }
```
Error:
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please check the highlighted fields.",
    "field_errors": [ { "field": "email", "message": "Enter a valid email address." } ],
    "request_id": "9f2c1c7e-..."
  }
}
```
**HTTP codes:** 200, 201, 204, 400, 401 (`UNAUTHORIZED`, `TOKEN_EXPIRED`), 403 (`FORBIDDEN`), 404 (`NOT_FOUND`), 409 (`CONFLICT` variants), 422 (`VALIDATION_ERROR`), 429 (`RATE_LIMITED`, with `Retry-After`), 503 (`MAINTENANCE`).
**Pagination:** cursor-based (`?limit=20&cursor=...`), default 20, max 100, stable ordering.

### 12.2 Authentication

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| POST | `/auth/register` | Create account, send OTP | Public |
| POST | `/auth/verify-email` | Verify OTP, returns tokens | Public |
| POST | `/auth/resend-verification` | Resend OTP (60 s cooldown) | Public |
| POST | `/auth/login` | Email + password | Public |
| POST | `/auth/google` / `/auth/apple` | Social sign-in (flag) | Public |
| POST | `/auth/refresh` | Rotate refresh token | Public |
| POST | `/auth/logout` | Revoke token family | Required |
| POST | `/auth/forgot-password` | Send reset OTP | Public |
| POST | `/auth/reset-password` | Reset with OTP | Public |
| POST | `/auth/web/login`, `/auth/web/refresh`, `/auth/web/logout` | Cookie-based variants for admin portal | Public/Required |

**POST /auth/register**
```json
// request
{ "full_name": "Huda Latheef", "email": "huda@example.com", "organization": "Dubai Hospital",
  "password": "Str0ngPass!", "accepted_terms": true }
// 201
{ "success": true, "data": { "email": "huda@example.com", "verification_required": true, "otp_expires_in": 900 } }
```
**POST /auth/login**
```json
// request
{ "email": "huda@example.com", "password": "Str0ngPass!", "device_info": "iPhone 15 / iOS 17" }
// 200
{ "success": true, "data": {
  "access_token": "eyJ...", "refresh_token": "r_8f3...", "expires_in": 900,
  "user": { "id": "uuid", "full_name": "Huda Latheef", "email": "huda@example.com", "role": "attendee" } } }
```
**POST /auth/refresh** `{ "refresh_token": "r_8f3..." }` → same shape as login (new pair).

### 12.3 Profile & Device

| Method | Endpoint | Description |
|---|---|---|
| GET | `/me` | Current profile + counts |
| PATCH | `/me` | Update `full_name, organization, designation, phone, location, notification_preferences` |
| POST | `/me/avatar` | Get pre-signed upload URL; then `PATCH /me {avatar_key}` |
| PATCH | `/me/password` | `{current_password, new_password}` |
| DELETE | `/me` | Request account deletion |
| POST | `/me/devices` | Register FCM token `{platform, fcm_token, app_version}` |
| DELETE | `/me/devices/{fcm_token}` | Unregister |
| GET | `/me/badge` | Badge + QR payload |
| GET | `/me/certificates` | Issued certificates |
| GET | `/me/bookmarks?target_type=session` | Bookmarked IDs |
| PUT / DELETE | `/me/bookmarks/{target_type}/{target_id}` | Add / remove (idempotent, 204) |

**GET /me**
```json
{ "success": true, "data": {
  "id": "uuid", "full_name": "Huda Latheef", "email": "huda@example.com", "organization": "Dubai Hospital",
  "designation": "Flutter Developer", "attendee_type": "Medical Congress Attendee",
  "phone": "+971562834212", "location": "Dubai, UAE", "avatar_url": "https://cdn.../a.jpg",
  "badge_code": "NMC-2026-001", "role": "attendee",
  "counts": { "sessions": 12, "saved": 5, "certificates": 3 } } }
```
**GET /me/badge**
```json
{ "success": true, "data": {
  "badge_code": "NMC-2026-001", "full_name": "Huda Latheef", "designation": "Flutter Developer",
  "attendee_type": "Attendee", "location": "Dubai, UAE", "event_name": "NESTLÉ MEDICAL CONGRESS 2026",
  "event_dates_label": "22 - 23 May 2026", "qr_payload": "nmc://badge/Xk3...", "status": "active", "checked_in_at": null } }
```

### 12.4 Event, Venue, Search, Config

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/app/config` | `min_app_version`, maintenance flag, feature flags | Public |
| GET | `/events/current` | Active event | Public |
| GET | `/events/{event_id}/venue` | Venue + facilities | Required |
| GET | `/search?q=` | Grouped results: sessions, speakers, resources, exhibitors | Required |
| GET | `/cms/{key}` | Terms / privacy / guidelines / about | Public |

**GET /events/current**
```json
{ "success": true, "data": {
  "id": "uuid", "name": "The Next Era of Nutrition & Health", "title": "NESTLÉ MEDICAL CONGRESS 2026",
  "tagline": "The Next Era of Nutrition & Health", "start_at": "2026-05-21T20:00:00Z", "end_at": "2026-05-23T14:00:00Z",
  "timezone": "Asia/Dubai", "city": "Dubai", "country": "United Arab Emirates", "dates_label": "May 22 - 23, 2026",
  "days": [ { "index": 1, "date": "2026-05-22", "label": "Day 1", "short": "May 22" },
            { "index": 2, "date": "2026-05-23", "label": "Day 2", "short": "May 23" } ],
  "settings": { "qna_moderation_enabled": true, "google_signin_enabled": false, "apple_signin_enabled": false } } }
```

### 12.5 Agenda & Speakers

| Method | Endpoint | Description |
|---|---|---|
| GET | `/events/{id}/agenda?date=&category_id=&q=&saved=` | Sessions for a day |
| GET | `/events/{id}/sessions/upcoming?limit=5` | Next sessions |
| GET | `/sessions/{id}` | Session detail with speakers |
| GET | `/events/{id}/categories?type=session` | Category chips |
| GET | `/events/{id}/speakers?q=&category_id=&featured=&country=&cursor=` | Speaker list |
| GET | `/speakers/{id}` | Speaker detail + sessions |

**GET /events/{id}/agenda?date=2026-05-22**
```json
{ "success": true, "data": { "date": "2026-05-22", "sessions": [
  { "id": "uuid", "title": "Opening Ceremony", "category": { "id": "uuid", "name": "Keynote", "slug": "keynote" },
    "start_at": "2026-05-22T04:30:00Z", "end_at": "2026-05-22T05:30:00Z", "start_local": "08:30", "meridiem": "AM",
    "room": "Main Auditorium", "status": "scheduled", "speakers": [ { "id": "uuid", "name": "Main Auditorium Host" } ],
    "is_bookmarked": false, "is_live": false } ] } }
```

### 12.6 Voting

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/polls/active` | Visible polls (active/paused, plus closed in last 10 min) | Required |
| GET | `/polls/history` | Closed polls | Required |
| GET | `/polls/{id}` | Poll + options + my vote + results (if visible) | Required |
| POST | `/polls/{id}/votes` | Submit vote (header `Idempotency-Key`) | Required |
| GET | `/polls/{id}/results` | Results if visible | Required |

**GET /polls/active**
```json
{ "success": true, "data": [ {
  "id": "uuid", "label": "Audience Feedback", "question": "How would you rate the current session?",
  "status": "active", "type": "single", "max_choices": 1, "results_visibility": "after_vote",
  "has_voted": true, "my_option_ids": ["uuid-b"], "total_votes": 101, "closes_at": null,
  "options": [
    { "id": "uuid-a", "label": "Excellent", "votes": 55, "percent": 54 },
    { "id": "uuid-b", "label": "Very Good", "votes": 31, "percent": 31 },
    { "id": "uuid-c", "label": "Good", "votes": 10, "percent": 10 },
    { "id": "uuid-d", "label": "Fair", "votes": 5, "percent": 5 } ] } ] }
```
(`votes`/`percent` are `null` when results are not visible to this user.)

**POST /polls/{id}/votes**
```json
// headers: Idempotency-Key: 6d1f...
// request
{ "option_ids": ["uuid-b"] }
// 201
{ "success": true, "data": { "accepted": true, "has_voted": true, "results_visible": true, "poll": { "...same as GET /polls/{id}" } } }
// 409
{ "success": false, "error": { "code": "ALREADY_VOTED", "message": "You have already voted in this poll." } }
```
Error codes: `POLL_NOT_ACTIVE`, `POLL_CLOSED`, `ALREADY_VOTED`, `INVALID_OPTION`, `TOO_MANY_CHOICES`.

### 12.7 Q&A

| Method | Endpoint | Description |
|---|---|---|
| GET | `/questions?tab=popular\|recent\|answered&category_id=&session_id=&cursor=` | Visible questions |
| GET | `/questions/mine` | Own questions incl. pending/rejected |
| POST | `/questions` | Submit question |
| GET | `/questions/{id}` | Detail with answer |
| PUT / DELETE | `/questions/{id}/upvote` | Add / remove upvote (idempotent) |
| POST | `/questions/{id}/answer` | Speaker (own session) / moderator / organizer / admin |

**POST /questions**
```json
{ "text": "How can pediatric nutrition plans be personalized for children with different growth patterns?",
  "category_id": "uuid", "session_id": null, "speaker_id": null }
// 201
{ "success": true, "data": { "id": "uuid", "status": "pending", "message": "Submitted for moderation." } }
```
**GET /questions?tab=recent** item:
```json
{ "id": "uuid", "text": "How can pediatric...", "category": { "name": "Nutrition" }, "status": "answered",
  "upvote_count": 24, "has_upvoted": false, "is_mine": false, "created_at": "2026-05-22T07:10:00Z",
  "answer": { "text": "Growth charts...", "author_name": "Dr. Ahmed", "answered_at": "2026-05-22T08:00:00Z" } }
```

### 12.8 Resources & Exhibitors

| Method | Endpoint | Description |
|---|---|---|
| GET | `/resources?type=pdf\|slides\|video&q=&saved=true&cursor=` | Published resources |
| GET | `/resources/{id}` | Detail |
| GET | `/resources/{id}/access` | `{url, expires_in, kind: "download"\|"external"}` |
| GET | `/events/{id}/exhibitors?q=&category_id=` | Exhibitors |
| GET | `/exhibitors/{id}` | Detail |

Resource item: `{ id, title, description, type, file_size_bytes, file_size_label: "4.2 MB", is_bookmarked, version, updated_at }`.

### 12.9 Notifications

| Method | Endpoint | Description |
|---|---|---|
| GET | `/notifications?cursor=` | Inbox |
| GET | `/notifications/unread-count` | `{count}` |
| PATCH | `/notifications/{id}` | Mark read |
| POST | `/notifications/read-all` | Mark all read |

### 12.10 Admin API (`/admin/...`, roles per RBAC matrix)

| Area | Endpoints |
|---|---|
| Events | `GET/PATCH /admin/events/{id}`, `PUT /admin/events/{id}/venue`, `PUT /admin/venues/{id}/facilities` |
| Sessions | `GET/POST /admin/sessions`, `GET/PATCH/DELETE /admin/sessions/{id}`, `POST /admin/sessions/{id}/publish\|unpublish\|cancel\|duplicate` |
| Speakers | `GET/POST /admin/speakers`, `PATCH/DELETE /admin/speakers/{id}` |
| Categories | `GET/POST /admin/categories`, `PATCH/DELETE /admin/categories/{id}`, `POST /admin/categories/reorder` |
| Polls | `GET/POST /admin/polls`, `PATCH/DELETE /admin/polls/{id}`, `POST /admin/polls/{id}/activate\|pause\|resume\|close\|duplicate\|reset` |
| Q&A | `GET /admin/questions?status=`, `POST /admin/questions/{id}/approve\|hide\|reject\|flag`, `POST /admin/questions/{id}/answer`, `GET /admin/questions/{id}/history` |
| Resources | `POST /admin/media/upload-url`, `GET/POST /admin/resources`, `PATCH/DELETE /admin/resources/{id}`, `POST /admin/resources/{id}/publish\|unpublish\|replace` |
| Exhibitors | `GET/POST /admin/exhibitors`, `PATCH/DELETE /admin/exhibitors/{id}` |
| Attendees | `GET /admin/attendees`, `GET /admin/attendees/{id}`, `POST /admin/attendees/{id}/approve\|suspend\|unsuspend\|resend-verification\|regenerate-badge`, `GET /admin/attendees/export`, `POST /admin/attendees/import` |
| Certificates | `POST /admin/certificates/issue`, `GET /admin/certificates`, `POST /admin/certificates/{id}/revoke` |
| Announcements | `GET/POST /admin/announcements`, `PATCH /admin/announcements/{id}`, `POST /admin/announcements/{id}/send` |
| Check-in | `POST /admin/checkin/verify`, `GET /admin/checkin/stats` |
| Users | `GET/POST /admin/users`, `PATCH /admin/users/{id}` (role/status), `DELETE /admin/users/{id}` |
| Analytics | `GET /admin/analytics/overview\|registrations\|checkins\|polls\|questions` |
| Audit/Settings | `GET /admin/audit`, `GET/PATCH /admin/settings`, `GET/PATCH /admin/cms/{key}`, `GET/PATCH /admin/email-templates/{key}` |

**POST /admin/checkin/verify** → `{ "token": "Xk3..." }`
```json
{ "success": true, "data": { "result": "valid", "full_name": "Huda Latheef", "organization": "Dubai Hospital",
  "badge_code": "NMC-2026-001", "checked_in_at": "2026-05-22T04:12:00Z" } }
```
`result` ∈ `valid | already_checked_in | revoked | suspended | invalid`.

---

## 13. Real-time (WebSocket) Design

**Endpoint:** `wss://api.<domain>/ws?token=<access_token>` (FastAPI WebSocket). Validate JWT on connect; close with code 4401 if invalid/expired. Client sends heartbeat `{"type":"ping"}` every 25 s; server replies `{"type":"pong"}`; connections idle > 60 s are dropped.

**Subscription:** after connect the client sends `{"type":"subscribe","topics":["polls","questions","notifications","schedule"]}`. Per-user topic `user:{id}` is auto-subscribed.

**Server → client events**

| Event | Payload | Triggered by |
|---|---|---|
| `poll.activated` | `{poll_id}` | Organizer activates poll |
| `poll.closed` | `{poll_id}` | Close or auto end |
| `poll.paused` / `poll.resumed` | `{poll_id}` | Organizer |
| `poll.results_updated` | `{poll_id, total_votes, options:[{id,votes,percent}]}` | Vote accepted (throttled to max 1/sec per poll) |
| `question.published` | `{question}` | Moderation approve or auto publish |
| `question.answered` | `{question_id, answer}` | Answer posted |
| `question.upvoted` | `{question_id, upvote_count}` | Upvote (throttled) |
| `schedule.updated` | `{session_id, status}` | Session changed/cancelled |
| `notification.new` | `{notification}` | Per-user |
| `event.updated` | `{}` | Event settings changed |

**Scaling:** each API instance subscribes to Redis pub/sub channels (`ws:polls`, `ws:questions`, ...). Publishers (HTTP handlers/workers) publish to Redis; every instance forwards to its local sockets. Results for `poll.results_updated` are computed with one grouped query and cached in Redis for 1 s.
**Client fallback:** if the socket fails 3 reconnects (exponential backoff 1, 2, 4, up to 30 s with jitter), switch to polling `GET /polls/active` every 5 s while the Voting screen is visible and `GET /questions` every 10 s on Q&A. On reconnect, refetch current screen data (no message replay).

---

## 14. Tech Stack & Project Setup

### 14.1 Architecture Overview
```
 Flutter App (iOS/Android) ──HTTPS/WSS──┐      Next.js Admin Portal ──HTTPS/WSS──┐
                                         ▼                                        ▼
                              CloudFront (CDN) → ALB (HTTPS, WebSocket sticky-free)
                                         ▼
                              FastAPI (ECS Fargate, N stateless tasks)
                       ┌────────┬────────┴────────┬───────────────┐
                       ▼        ▼                 ▼               ▼
              PostgreSQL 16   Redis 7        S3 (private)     ARQ Worker (ECS)
              (RDS Multi-AZ)  (ElastiCache)  + CloudFront     → SES, FCM, PDF jobs
```

### 14.2 Technology Choices

| Layer | Technology | Rationale |
|---|---|---|
| Mobile | **Flutter 3.x (stable) + Dart 3** | Single codebase for iOS/Android |
| Mobile state | **Riverpod 2 (`flutter_riverpod`, `riverpod_annotation`)** | Testable, compile-safe |
| Mobile routing | **go_router** | Deep links, auth redirect |
| HTTP | **Dio** + interceptors (auth, refresh, logging, retry) | Token refresh single-flight |
| Models | **freezed + json_serializable** | Immutable models |
| Secure storage | **flutter_secure_storage** | Keychain/Keystore |
| Other packages | `qr_flutter`, `google_maps_flutter`, `url_launcher`, `firebase_messaging`, `flutter_local_notifications`, `web_socket_channel`, `cached_network_image`, `shimmer`, `intl`, `flutter_pdfview`, `video_player`+`chewie`, `printing`, `screen_brightness`, `connectivity_plus`, `hive` (offline read cache), `image_picker`, `sentry_flutter` | |
| Backend | **Python 3.12 + FastAPI + Uvicorn/Gunicorn** | OpenAPI built-in, async |
| ORM / migrations | **SQLAlchemy 2.0 (async) + Alembic** | |
| Validation | **Pydantic v2** | |
| Auth libs | `PyJWT[crypto]`, `argon2-cffi` | RS256, Argon2id |
| Database | **PostgreSQL 16** | Transactions for voting |
| Cache / pub-sub / rate limit | **Redis 7** | WS fan-out, idempotency |
| Jobs | **ARQ** (async, Redis) | Email, push, reminders |
| Storage | **AWS S3** private bucket + pre-signed URLs (`boto3`/`aioboto3`) | |
| Email | **AWS SES** | |
| Push | **Firebase Cloud Messaging** (APNs key uploaded to Firebase) | |
| PDF | **ReportLab** | Certificates |
| Admin portal | **Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Query/Table, RHF + Zod, Recharts, dnd-kit, TipTap, html5-qrcode** | |
| Testing | pytest + httpx + pytest-asyncio + testcontainers (backend); `flutter_test`, `mocktail`, `integration_test` (mobile); Playwright (admin E2E); k6 (load) | |
| CI/CD | **GitHub Actions** (lint, test, build, scan, deploy) | |
| IaC | **Terraform** | |
| Observability | CloudWatch + **Sentry** (backend, admin, mobile); OpenTelemetry traces optional | |

### 14.3 Repository Structure (monorepo)
```
nmc-congress/
├── mobile_app/                  # Flutter
│   └── lib/
│       ├── core/                # theme/tokens, router, dio client, storage, errors, l10n, ws client
│       ├── shared/widgets/      # AppScaffold, PrimaryButton, chips, tiles, states
│       └── features/
│           ├── auth/ home/ quick_access/ agenda/ speakers/ name_tag/ venue/
│           ├── voting/ qna/ resources/ exhibitors/ notifications/ profile/ settings/
│           └── <feature>/{data (repository, dto), domain (models), presentation (screens, providers, widgets)}
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/              # routers: auth, me, events, agenda, speakers, polls, questions,
│   │   │                        #          resources, exhibitors, notifications, admin/*, ws.py
│   │   ├── core/                # config, security (jwt, argon2), deps (require_roles), rate_limit, errors, logging
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic request/response
│   │   ├── services/            # business logic (voting_service, qna_service, badge_service, ...)
│   │   ├── workers/             # ARQ tasks
│   │   └── realtime/            # connection manager, redis pubsub
│   ├── migrations/              # Alembic
│   ├── tests/
│   └── scripts/seed.py
├── admin_portal/                # Next.js
├── infrastructure/              # Terraform, docker-compose.yml
├── docs/                        # openapi.json export, runbooks, ADRs
└── README.md
```
Rules: business logic only in `services/`; route handlers stay thin; one repository/provider layer per mobile feature.

### 14.4 Local Development (`docker-compose.yml`)
Services: `postgres:16`, `redis:7`, `minio` (S3-compatible), `mailhog` (SMTP catcher), `backend`, `worker`. `make dev` starts all; `make migrate`; `make seed` loads Appendix A data.

### 14.5 Environment Variables (backend `.env.example`)
```
APP_ENV=local|staging|production
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nmc
REDIS_URL=redis://localhost:6379/0
JWT_PRIVATE_KEY_PATH=... / JWT_PUBLIC_KEY_PATH=... / JWT_KEY_ID=k1
ACCESS_TOKEN_MINUTES=15  REFRESH_TOKEN_DAYS=30
S3_BUCKET=... S3_REGION=me-central-1 S3_ENDPOINT_URL=(minio only) CDN_BASE_URL=...
SES_SENDER=no-reply@... SES_REGION=...
FCM_CREDENTIALS_JSON=...(secret ref)
BADGE_TOKEN_ENC_KEY=...  CORS_ORIGINS=https://admin.<domain>
SENTRY_DSN=... FEATURE_GOOGLE_SIGNIN=false FEATURE_APPLE_SIGNIN=false
```
Secrets in AWS Secrets Manager in staging/production; never committed.

---

## 15. Non-Functional Requirements

### 15.1 Performance

- API latency p95: reads < 500 ms, writes < 800 ms at target load; vote endpoint p95 < 300 ms
- Home screen interactive < 2 s on 4G; cold start < 3 s
- Poll update propagation p95 < 2 s; WebSocket message delivery p95 < 1 s
- Lists paginated (≤ 100 items); images served through CDN, resized (thumb 200 px, medium 600 px)
- DB: indexes per Section 11.4; no N+1 queries (use `selectinload`/joins); `EXPLAIN` reviewed for agenda, questions, resources queries
- Redis caching (TTL): event config 60 s, agenda per day 30 s (invalidated on admin edit), speakers 60 s, poll results 1 s

### 15.2 Security (OWASP Top 10 / OWASP MASVS)

- **A01 Access control:** `require_roles` on every route; object-level checks (users access only their own bookmarks, questions-mine, badge); event scoping on every query; IDOR tests mandatory
- **A02 Crypto:** TLS 1.2+ only; Argon2id; RS256; encrypted badge token at rest; S3 SSE-KMS; RDS encryption at rest
- **A03 Injection:** SQLAlchemy parameterized queries only; Pydantic validation; HTML-escape rich text on admin render (sanitize with `bleach`/DOMPurify)
- **A04 Insecure design:** threat model before build; abuse controls (rate limits, idempotency)
- **A05 Misconfiguration:** private S3, no public ACLs, security headers on admin (CSP, HSTS, X-Frame-Options), debug off in prod, CORS allowlist
- **A07 Auth failures:** lockout, OTP attempt limits, refresh rotation + reuse detection, MFA option for admin
- **A08 Integrity:** dependency pinning, `pip-audit`, `npm audit`, `flutter pub outdated` in CI; signed builds
- **A09 Logging:** structured JSON logs with `request_id`; never log passwords, OTPs, tokens, QR tokens; mask emails/phones; retain 90 days
- **Mobile:** certificate pinning (optional, behind config), no secrets in app bundle, jailbreak/root detection (warn only), obfuscated release builds (`--obfuscate --split-debug-info`)
- **File uploads:** validate MIME + extension + size server-side; store with random keys; optional ClamAV scan job
- **Privacy / compliance:** collect only fields in this PRD; consent timestamp stored; export/delete workflows; analytics events contain no PII; confirm UAE PDPL (Federal Decree-Law 45/2021) and Nestlé corporate policy requirements with legal. This PRD is not legal advice

### 15.3 Scalability & Reliability

- Stateless API containers, horizontal autoscaling (CPU 60% / request count), min 2 tasks in production, 4 during event days
- RDS PostgreSQL Multi-AZ, automated backups (35 days) + PITR; RPO ≤ 5 min, RTO ≤ 30 min; restore tested before event
- Redis ElastiCache with replica; app degrades gracefully if Redis is down (rate limit fails open for reads, closed for votes)
- Zero-downtime rolling deploys; DB migrations backward compatible (expand → migrate → contract)
- Health endpoints: `/health/live`, `/health/ready` (checks DB + Redis)
- Load test (k6) before launch: 1,500 concurrent WebSocket clients, 300 votes/s burst for 30 s, 500 req/s agenda reads; pass = error rate < 0.5%, p95 within Section 15.1

### 15.4 Accessibility
WCAG 2.1 AA: contrast ≥ 4.5:1 (verify gold on navy and white text on gradient), `Semantics` labels on all icon buttons, dynamic type up to 130% without clipping, 44 px touch targets, no information by color alone (status chips include text), VoiceOver/TalkBack tested for Login, Agenda, Voting.

### 15.5 Localization & Time
All strings in `app_en.arb`; `intl` for dates/numbers; all times shown in event timezone, with device-timezone hint if different ("Times shown in Dubai time (GMT+4)").

### 15.6 Compatibility
iOS 15+, Android 8.0+ (API 26+). Phone layouts 360–430 dp wide; tablets get centered max-width 600 dp column. Portrait only in Phase 1.

### 15.7 Observability
Sentry (crashes, errors), CloudWatch alarms: 5xx > 1% for 5 min, p95 latency > 2 s, DB CPU > 80%, Redis memory > 80%, SES bounce > 5%, queue depth > 1,000, WebSocket connections drop > 30% in 1 min. Dashboards: API, DB, Realtime, Business (votes accepted/rejected, questions pending, downloads).

---

## 16. Testing & Acceptance Criteria

### 16.1 Test Levels

| Level | Tools | Coverage target |
|---|---|---|
| Unit (backend) | pytest | Services (voting, qna, badge, auth) ≥ 85% |
| API/integration | pytest + httpx + testcontainers (Postgres, Redis) | Every endpoint: success, validation, authz (each role), rate limit |
| Concurrency | pytest asyncio | 200 parallel votes by same user → exactly 1 accepted; 200 parallel upvotes → count correct |
| Mobile unit/widget | flutter_test, mocktail | Providers, validators, key widgets, golden tests for 12 reference screens |
| Mobile integration | integration_test | Register → verify → login → bookmark → vote → question → resource open |
| Admin E2E | Playwright | Create session → appears in app API; poll lifecycle; moderation |
| Load | k6 | Section 15.3 |
| Security | OWASP ZAP baseline, manual IDOR/authz tests, dependency scan | No critical/high open |
| UAT | Organizer + 10 attendees on staging | Sign-off |

### 16.2 Acceptance Criteria by Module (Given / When / Then)

| Module | Criteria |
|---|---|
| Registration | Given valid data, When I submit, Then one account is created in `pending_verification` and an OTP email is sent. Given an existing email (any case), Then 409 `EMAIL_EXISTS`. Given unticked terms, Then the button is disabled |
| Verify | Given a correct code within 15 min, Then account becomes active and I land on Home. Given 5 wrong codes, Then the code is invalidated |
| Login | Valid → Home. Invalid → generic error, no email enumeration. 10 failures → locked 15 min. Token refresh works silently; logout invalidates refresh |
| Home | Greeting shows my name; event card data comes from API; 8 Quick Access tiles route correctly; bell dot reflects unread; Upcoming shows next ≤ 5 sessions |
| Quick Access | Chips filter by tag; search filters tiles; empty state shown when none |
| Agenda | Day tab switches date and header label; category chip filters; Reset clears filters; bookmark persists after app relaunch and on another device; cancelled/changed chips visible; times in Dubai time |
| Speakers | Search (300 ms debounce), chips, featured toggle, detail with sessions; missing photo shows initials |
| Name Tag | Shows my data and unique QR; QR contains no personal data; scanning valid QR in `/checkin` checks me in once; second scan reports already checked in; revoked badge reports revoked |
| Venue | Address and facilities always visible; map failure does not hide them; Directions opens native maps |
| Voting | Only active polls accept votes; second vote → `ALREADY_VOTED`; concurrent duplicates → one vote; results hidden/visible per `results_visibility`; percentages sum to 100; other devices update within 2 s; offline vote shows retry and never double-counts (idempotency) |
| Q&A | < 10 chars blocked; submitted question appears as pending (moderation ON) in My Questions only; after approve it appears in Recent for all; one upvote per user; own-question upvote blocked; answer sets status Answered and notifies author; hidden question disappears for attendees but remains in audit |
| Resources | Search and chips work; Saved shows only my bookmarks; signed URL expires after 5 min; unpublished resource returns 404; file size label correct |
| Profile | Counts reflect actual data; only allowed fields editable; avatar upload works; certificates list and download |
| Notifications | Unread count correct; tapping marks read and deep-links; push received on iOS and Android physical devices |
| Admin | Publishing a session makes it visible in the app within 30 s (cache TTL) without an app update; poll activation reaches clients < 2 s; unpublishing a resource denies new access; admin cannot demote self or last admin; audit rows exist for sensitive actions |

### 16.3 Release Exit Criteria

- All Must requirements done; all acceptance criteria pass on staging
- No open critical/high security findings; no blocker/critical defects in core journeys
- Load test passed; backup restore rehearsed; rollback plan verified
- Signed iOS (TestFlight → App Store) and Android (AAB → Play) builds tested on ≥ 6 physical devices (3 iOS, 3 Android, low/mid/high tiers)
- OpenAPI export, runbook and handover documentation delivered; UAT sign-off recorded

---

## 17. Deployment & Operations

### 17.1 Environments

| Env | Purpose | Data |
|---|---|---|
| Local | Dev (docker-compose) | Seed data |
| Dev | Shared integration | Synthetic |
| Staging/UAT | Production-like, client acceptance | Masked/synthetic |
| Production | Live | Real, restricted access |

### 17.2 CI/CD (GitHub Actions)

- **PR checks:** `ruff` + `mypy` + pytest (with Postgres/Redis services); `dart format`, `flutter analyze`, `flutter test`; admin `eslint`, `tsc`, build; dependency + secret scanning
- **Main branch:** build Docker image → push ECR → deploy to staging → run smoke tests
- **Release tag:** manual approval → run Alembic migration job → rolling ECS deploy to production → smoke tests → auto-rollback on failed health checks
- **Mobile:** Fastlane lanes for TestFlight and Play internal track; flavors `dev`, `staging`, `prod` with different API base URLs and Firebase configs

### 17.3 Backend Deployment Steps

1. Provision VPC, RDS (Multi-AZ), ElastiCache, S3 (block public access, versioning, SSE-KMS), CloudFront, ALB, ECS, ECR, Secrets Manager, SES (verify domain, SPF/DKIM/DMARC, request production access) via Terraform
2. Set env vars/secret references per environment
3. Run migrations (`alembic upgrade head`) as a one-off ECS task before deploying
4. Deploy API + worker services behind HTTPS; ALB idle timeout ≥ 120 s for WebSockets
5. Configure CORS, rate limits, alarms, log retention, backup policy
6. Smoke tests: register/login, agenda, vote, question, resource access, WebSocket connect
7. Seed production event content via admin portal (not via seed script)

### 17.4 Mobile Release Steps

1. Set bundle IDs, icons, splash, signing; Firebase projects; APNs key; Google Maps keys (restricted by bundle ID/SHA-1)
2. Build `prod` flavor release with obfuscation; upload symbols to Sentry/Crashlytics
3. Internal testing (TestFlight / Play internal) → UAT → store submission (privacy nutrition labels/Data Safety form, camera not required in mobile app, notification permission rationale)
4. Staged rollout (10% → 50% → 100%); monitor crash-free sessions and backend error rate
5. Event-day freeze: no deploys 24 h before and during the event except hotfixes approved by product owner

### 17.5 Event-Day Runbook (summary)
T-7 days: load test + restore test + freeze content model. T-1 day: scale API to 4 tasks, verify SES quotas, test push on real devices, on-call roster published. During event: monitor dashboards, moderator and organizer logged in, kill-switch toggles available (disable Q&A submissions, close all polls, maintenance mode). T+1: scale down, export reports, issue certificates.

---

## 18. Cursor Build Plan

### 18.1 Rules to give Cursor (put in `.cursorrules` / `AGENTS.md`)

1. Follow this PRD exactly; if something is ambiguous, ask before inventing behavior. Do not add features that are out of scope
2. Mobile: Flutter + Riverpod + go_router + Dio + freezed; feature-first folders; no business logic in widgets; all colors/spacing/text styles from `AppTokens`/`ThemeData`; all strings in `.arb`
3. Backend: FastAPI + SQLAlchemy 2 async + Alembic + Pydantic v2; thin routers, logic in `services/`; every route declares role dependency; every list endpoint paginated
4. Every screen implements loading, empty, error and content states
5. Every DB change is an Alembic migration; never mutate schema manually
6. Never log secrets, tokens, OTPs or QR tokens; never return password hashes or storage keys
7. Write tests with each feature (pytest for services/endpoints; widget tests for screens)
8. Use the API response envelope from Section 12.1 and the error codes listed

### 18.2 Phases (build in this order; do not start a phase until the previous "Done when" passes)

| Phase | Build | Done when |
|---|---|---|
| **0. Scaffold** | Monorepo, docker-compose, FastAPI skeleton with `/health`, Alembic, Flutter app with theme tokens + shared widgets + router, Next.js skeleton, CI | `make dev` runs all services; Flutter app shows themed placeholder; CI green |
| **1. DB & Seed** | All tables/enums from Section 11 as migrations; `seed.py` with Appendix A data | `make seed` populates event, sessions, speakers, polls, resources; schema matches Section 11 |
| **2. Auth (backend)** | Register, OTP verify, login, refresh rotation, logout, forgot/reset, rate limits, RBAC deps, audit helper | Auth acceptance criteria pass in pytest incl. reuse detection and lockout |
| **3. Auth (mobile)** | Screens 8.1–8.4, secure storage, Dio refresh interceptor, redirect guard | Can register, verify (Mailhog), login, auto-refresh, logout on device |
| **4. Home + Quick Access** | `/events/current`, `/me`, upcoming sessions, notification count; screens 8.5, 8.6, bottom nav | Home matches screenshot 3; tiles navigate |
| **5. Agenda + Speakers** | Endpoints 12.5; screens 8.7, 8.8 + details; bookmarks | Day/category filters, bookmark persistence, search |
| **6. Name Tag + Venue + Profile** | Badge service, QR, venue API, profile, avatar upload; screens 8.9, 8.10, 8.14 | Matches screenshots 6/7/12; QR renders; counts correct |
| **7. Voting + realtime** | Poll services (transactional, idempotent), WebSocket + Redis pub/sub; screen 8.11 | Concurrency test passes; 2 devices update live; polling fallback works |
| **8. Q&A** | Services, moderation states, upvotes; screen 8.12 + My Questions | Matches screenshot 10; moderation rules enforced |
| **9. Resources** | S3 upload/signed access; screen 8.13 with viewer/downloader | PDF opens, slides download, bookmarks/Saved work |
| **10. Admin portal** | Pages in Section 9 in this order: Event/Venue, Sessions/Speakers/Categories, Polls, Q&A, Resources, Exhibitors, Attendees, Announcements, Check-in, Users/Audit/Settings | Organizer can run a full event without DB access |
| **11. Notifications** | Worker, FCM, SES templates, inbox screen, deep links, reminders | Push received on real devices; reminders fire 15 min before |
| **12. Exhibitors + Certificates + Settings** | Screens 8.15, 8.17, certificate PDF | Certificates download; exhibitors list/detail |
| **13. Hardening** | Rate limits tuning, caching, a11y pass, load test, security tests, Sentry | Section 16.3 exit criteria |
| **14. Release** | Terraform, staging → production, store builds | Live with runbook |

### 18.3 Prompt Template for Each Task in Cursor
> "Implement **[Phase N: feature]** from the PRD. Read PRD sections **[list]**. Create/modify only these files: **[paths]**. Requirements: **[paste the relevant table rows]**. Include loading/empty/error states, tests, and Alembic migration if the schema changes. After coding, list what you implemented, what you skipped, and how to run/test it."

---

## 19. Optional Enhancements (Phase 2)

- Google/Apple sign-in enabled in production (flags already in place)
- Session attendance tracking via room QR scans; CPD/accreditation integration; auto-eligible certificates
- Exhibitor lead capture (scan attendee badge), booth map and appointment booking
- In-app networking: attendee directory (opt-in), 1:1 messaging
- Interactive floor plan with indoor navigation
- Word-cloud and open-text polls; quiz mode with leaderboard
- Session feedback forms; post-event survey
- Multi-language (Arabic RTL) and multi-event switcher
- Offline-first sync; tablet layouts; web attendee portal
- Real-time translation/captions links

---

## 20. Risks & Assumptions

### Assumptions

| # | Assumption |
|---|---|
| A1 | Attendees have iOS 15+ / Android 8+ phones and event Wi-Fi or mobile data |
| A2 | Single congress at launch, English only |
| A3 | Attendee list is either self-registering or imported by organizers; no payment in-app |
| A4 | Colors/fonts are estimated from screenshots until the Figma file is provided |
| A5 | Client allows AWS `me-central-1` (or approves an alternative region) |
| A6 | Apple Developer and Google Play accounts and a Google Maps/Firebase project are provided by the client |
| A7 | Content (speakers, sessions, files) is supplied by the organizers and entered through the admin portal |
| A8 | All uploaded resources are approved, non-patient, non-confidential-clinical content |

### Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Vote burst overloads DB at poll activation | Medium | High | Idempotent transactional writes, Redis caching of results, autoscaling, load test at 300 votes/s |
| R2 | Duplicate/invalid votes | Medium | High | DB unique constraints + service checks + rate limits + audit |
| R3 | Inappropriate or off-topic questions | High | Medium | Pre-moderation default, profanity auto-flag, moderator kill switch |
| R4 | Poor venue connectivity | High | Medium | Cached read-only content, retry with idempotency, polling fallback |
| R5 | Push/email deliverability issues | Medium | Medium | SES domain auth, FCM token cleanup, in-app inbox as source of truth |
| R6 | Scope creep (exhibitors, certificates, chat) | High | Medium | Section 3 decisions + change control; Phase 2 backlog |
| R7 | Security vulnerability in auth/data access | Low | Critical | RBAC tests, IDOR tests, pen test before launch, Argon2id/RS256 |
| R8 | Store review delays (esp. Apple, sign-in with Apple) | Medium | High | Submit early; Apple sign-in required if Google sign-in is enabled |
| R9 | Data-residency / UAE PDPL non-compliance | Medium | High | In-region hosting, consent records, deletion workflow, legal review |
| R10 | Design assets differ from estimated tokens | Medium | Low | Tokens centralized; swap values once Figma received |
| R11 | Content changes during event cause stale caches | Low | Medium | Short TTLs, cache invalidation on admin writes, WebSocket `schedule.updated` |

---

## Appendix A: Seed Data (for `scripts/seed.py`, based on the screenshots)

**Event:** name `The Next Era of Nutrition & Health`, title `NESTLÉ MEDICAL CONGRESS 2026`, tagline `The Next Era of Nutrition & Health`, 2026-05-22 00:00 → 2026-05-23 23:59 (`Asia/Dubai`), Dubai, United Arab Emirates, `is_current = true`.
**Venue:** `Dubai International Convention & Exhibition Center`, address `World Trade Centre, Dubai, United Arab Emirates`, lat 25.2285, lng 55.2867; facilities: Free Wi-Fi (`wifi`), Parking (`parking`), Catering (`catering`), Accessible (`accessible`).
**Categories:** session: Keynote, Nutrition, Research; speaker: Nutrition, Research, Pediatric; question: General, Nutrition, Research, Clinical; resource: PDF, Slides, Video; exhibitor: Sponsor, Partner.
**Speakers:** Dr. Sarah Johnson (Pediatric Nutrition Specialist, United Kingdom, featured, Nutrition + Pediatric); Dr. Hassan Ali (Clinical Research Director, UAE, Research); Dr. Ahmed Khalid (add designation, UAE); Dr. Ahmed (host/moderator for opening).
**Sessions (Day 1):** 08:30–09:30 Opening Ceremony (Keynote, Main Auditorium); 09:30–10:30 Welcome & Introduction (Keynote, Dr. Hassan Ali); 10:30–11:30 Future of Pediatric Nutrition (Nutrition, Dr. Sarah Johnson). Add 3 sessions for Day 2 (e.g. Research Poster Session, Clinical Nutrition Panel, Closing Remarks).
**Poll:** `How would you rate the current session?` label `Audience Feedback`, single choice, options Excellent, Very Good, Good, Fair, Poor, status active, `after_vote`. Seed 101 sample votes (55/31/10/3/2) in dev only.
**Questions:** `How can pediatric nutrition plans be personalized for children with different growth patterns?` (Nutrition, answered, 24 upvotes, answered by Dr. Ahmed) plus 3 published and 2 pending.
**Resources:** `Congress Scientific Program` (PDF, 4.2 MB, "Complete schedule and session details"); `Pediatric Nutrition Guidelines` (PDF, 2.8 MB, "Clinical reference material"); `Keynote Presentation Slides` (Slides, 8.6 MB, "The Next Era of Nutrition & Health"). Use placeholder files of matching types in dev.
**Users (dev):** `admin@test.local` (admin), `organizer@test.local`, `moderator@test.local`, `checkin@test.local`, `speaker@test.local`, `huda@example.com` (attendee, "Huda Latheef", Flutter Developer, Dubai, UAE, +971562834212, badge `NMC-2026-001`), password `Passw0rd!` for all (dev/staging only).

## Appendix B: Design Inconsistencies Found in the Screenshots

| # | Finding | Resolution in this PRD |
|---|---|---|
| 1 | Agenda header shows "Thursday, May 22, 2026", but May 22, 2026 is a **Friday** | Weekday is computed from the date in the event timezone, never hardcoded |
| 2 | Session times wrap (`08:3` / `0`) in the Agenda list | Fixed-width time column with no wrapping (Section 8.7) |
| 3 | Last category chips truncated (`Cl…`, `Pedia…`, `Sen…`, `Researc…`) | Chips scroll horizontally; never clip text |
| 4 | Profile shows hardcoded-looking test values ("Dr. Testing", "Flutter Developer • Attendee") | Real data from API; subtitle uses `designation • attendee_type` |
| 5 | Poll results show 54% / 31% / 10% (sum 95%) with options cut off | All options rendered (scrollable); percentages use largest remainder to sum to 100 |
| 6 | Quick Access screen only shows 4 of 8 tiles | All 8 tiles in a scrollable grid |
| 7 | Event dates/location are hardcoded in design | Come from `events` table |

## Appendix C: Reference UI Screenshots

> **For the AI coding assistant:** the images in this document are the visual source of truth. Each screen's image is also embedded directly under its spec in Section 8. Individual screen crops are in `ui_reference/screens/`. Where an image disagrees with the text in Section 8, the text wins (see Appendix B for known design bugs not to copy).

### C.1 Sheet 1: Welcome/Login, Create Account, Home, Quick Access, Agenda, Speakers, Name Tag, Venue
![UI sheet 1](ui_reference/ui_screens_1_auth_home_agenda_speakers_nametag_venue.png)

| Position (left to right, top row then bottom row) | Screen | Spec section |
|---|---|---|
| Top 1 | Welcome Back (Login) | 8.1 |
| Top 2 | Join the NESTLÉ CONGRESS (Create Account) | 8.2 |
| Top 3 | Home | 8.5 |
| Top 4 | Quick Access | 8.6 |
| Bottom 1 | Congress Agenda | 8.7 |
| Bottom 2 | Speakers | 8.8 |
| Bottom 3 | My Name Tag | 8.9 |
| Bottom 4 | Venue | 8.10 |

### C.2 Sheet 2: Live Voting, Ask Q&A, Resources, My Profile
![UI sheet 2](ui_reference/ui_screens_2_voting_qna_resources_profile.png)

| Position (left to right) | Screen | Spec section |
|---|---|---|
| 1 | Live Voting | 8.11 |
| 2 | Ask Q&A | 8.12 |
| 3 | Resources | 8.13 |
| 4 | My Profile | 8.14 |

### C.3 Screens with no reference image (built from this PRD's text only)
Verify Email, Forgot/Reset Password, Session Detail, Speaker Detail, Poll History, My Questions, Exhibitors list/detail, Notifications, Settings, Edit Profile, Certificates. Reuse the same design tokens, components and layout patterns as the reference screens.

---
**End of Document**

| Version | Date | Author | Changes |
|---|---|---|---|
| 1.0 | (original) | NTAM | Initial requirements baseline |
| 2.0 | November 6, 2026 | Product Management | Build-ready rewrite: decisions, screen specs, schema, API, NFR, Cursor plan |
