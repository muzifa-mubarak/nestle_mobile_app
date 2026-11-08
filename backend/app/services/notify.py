"""In-app inbox plus best-effort push and email.

Without FCM_SERVER_KEY or SMTP_HOST, local mode records the message and writes it to the API log
so the congress can be demonstrated. Transactional OTP mail stays in the auth service.
"""

import json
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.entities import Bookmark, DeviceToken, EmailLog, Event, Notification, Session, User
from app.services.congress_service import _as_utc, get_current_event

log = logging.getLogger("nmc.notify")


def _allows(user: User, preference: str | None) -> bool:
    if not preference:
        return True
    try:
        prefs = json.loads(user.notification_preferences or "{}")
    except json.JSONDecodeError:
        prefs = {}
    return bool(prefs.get(preference, True))


async def register_device(db: AsyncSession, user: User, token: str, platform: str, app_version: str | None) -> dict:
    cleaned = token.strip()
    if platform not in {"ios", "android", "web"} or len(cleaned) < 8:
        from app.core.errors import AppError

        raise AppError(422, "VALIDATION_ERROR", "Enter a device token.")
    existing = await db.scalar(select(DeviceToken).where(DeviceToken.fcm_token == cleaned))
    now = datetime.now(UTC)
    if existing is None:
        db.add(DeviceToken(user_id=user.id, platform=platform, fcm_token=cleaned, app_version=app_version, last_seen_at=now))
    else:
        existing.user_id = user.id
        existing.platform = platform
        existing.app_version = app_version
        existing.last_seen_at = now
    await db.commit()
    return {"registered": True}


async def _push(tokens: list[DeviceToken], title: str, body: str, deep_link: str | None) -> bool:
    settings = get_settings()
    if not settings.fcm_server_key:
        if settings.is_local:
            log.warning("LOCAL ONLY push title=%s recipients=%s link=%s", title, len(tokens), deep_link or "")
            return True
        return False
    payload = {
        "registration_ids": [item.fcm_token for item in tokens],
        "notification": {"title": title, "body": body},
        "data": {"deep_link": deep_link or ""},
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={"Authorization": f"key={settings.fcm_server_key}"},
                json=payload,
            )
        return response.status_code < 300
    except httpx.HTTPError:
        log.exception("FCM request failed")
        return False


def _email(to_email: str, subject: str, body: str) -> tuple[str, str | None]:
    settings = get_settings()
    if not settings.smtp_host:
        if settings.is_local:
            log.warning("LOCAL ONLY email to=%s subject=%s", to_email, subject)
            return "sent", None
        return "failed", "Email is not configured."
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_port != 1025:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return "sent", None
    except OSError as exc:
        log.exception("Email send failed")
        return "failed", str(exc)[:300]


async def fanout(
    db: AsyncSession,
    users: list[User],
    *,
    kind: str,
    title: str,
    body: str,
    deep_link: str | None,
    preference: str | None,
    push: bool = True,
    email: bool = False,
) -> int:
    """Create inbox rows and attempt push or email. Caller commits."""
    count = 0
    for user in users:
        if user.deleted_at is not None or user.status == "suspended" or not _allows(user, preference):
            continue
        note = Notification(
            user_id=user.id,
            type=kind,
            title=title[:120],
            body=body[:300],
            deep_link=deep_link,
            push_status="pending",
            attempts=0,
        )
        db.add(note)
        await db.flush()
        if push:
            tokens = list((await db.scalars(select(DeviceToken).where(DeviceToken.user_id == user.id))).all())
            if not tokens:
                note.push_status = "skipped"
            else:
                note.attempts = 1
                note.push_status = "sent" if await _push(tokens, note.title, note.body, deep_link) else "failed"
        else:
            note.push_status = "skipped"
        if email:
            status, error = _email(user.email, title[:200], body)
            db.add(EmailLog(to_email=user.email, subject=title[:200], body=body, status=status, error=error))
        count += 1
    return count


async def active_attendees(db: AsyncSession) -> list[User]:
    rows = await db.scalars(select(User).where(User.role == "attendee", User.status == "active", User.deleted_at.is_(None)))
    return list(rows.all())


async def checked_in_attendees(db: AsyncSession) -> list[User]:
    from app.models.entities import Badge

    rows = await db.scalars(
        select(User)
        .join(Badge, Badge.user_id == User.id)
        .where(User.role == "attendee", User.status == "active", User.deleted_at.is_(None), Badge.checked_in_at.is_not(None))
    )
    return list(rows.all())


async def bookmarked_users(db: AsyncSession, session_id: str) -> list[User]:
    ids = list(
        (await db.scalars(select(Bookmark.user_id).where(Bookmark.target_type == "session", Bookmark.target_id == session_id))).all()
    )
    if not ids:
        return []
    return list((await db.scalars(select(User).where(User.id.in_(ids)))).all())


async def recent_deliveries(db: AsyncSession) -> dict:
    notes = list((await db.scalars(select(Notification).order_by(Notification.created_at.desc()).limit(20))).all())
    emails = list((await db.scalars(select(EmailLog).order_by(EmailLog.created_at.desc()).limit(20))).all())
    return {
        "pushes": [
            {"title": row.title, "body": row.body, "push_status": row.push_status, "deep_link": row.deep_link, "created_at": _as_utc(row.created_at).isoformat().replace("+00:00", "Z") if row.created_at else None}
            for row in notes
        ],
        "emails": [
            {"to_email": row.to_email, "subject": row.subject, "status": row.status, "error": row.error}
            for row in emails
        ],
    }


async def send_announcement(db: AsyncSession, title: str, body: str, deep_link: str | None, audience: str) -> dict:
    from app.core.errors import AppError

    title = title.strip()
    body = body.strip()
    if not title or len(title) > 60 or not body or len(body) > 240:
        raise AppError(422, "VALIDATION_ERROR", "Enter a title up to 60 characters and a message up to 240.")
    if audience not in {"all", "checked_in"}:
        raise AppError(422, "VALIDATION_ERROR", "Choose an audience.")
    users = await checked_in_attendees(db) if audience == "checked_in" else await active_attendees(db)
    count = await fanout(
        db,
        users,
        kind="announcement",
        title=title,
        body=body,
        deep_link=deep_link or "nmc://notifications",
        preference="event_updates",
        push=True,
        email=False,
    )
    await db.commit()
    return {"recipients": count}


async def session_reminders(db: AsyncSession) -> int:
    try:
        event: Event = await get_current_event(db)
    except Exception:
        return 0
    now = datetime.now(UTC)
    window_start = now + timedelta(minutes=14)
    window_end = now + timedelta(minutes=16)
    sessions = list(
        (
            await db.scalars(
                select(Session).where(
                    Session.event_id == event.id,
                    Session.visibility == "published",
                    Session.status != "cancelled",
                )
            )
        ).all()
    )
    due = [row for row in sessions if window_start <= _as_utc(row.start_at) <= window_end]
    sent = 0
    for row in due:
        users = await bookmarked_users(db, row.id)
        link = f"nmc://session/{row.id}"
        fresh = []
        for user in users:
            already = await db.scalar(
                select(Notification.id).where(Notification.user_id == user.id, Notification.type == "session_reminder", Notification.deep_link == link)
            )
            if already is None:
                fresh.append(user)
        sent += await fanout(
            db,
            fresh,
            kind="session_reminder",
            title="Starting in 15 minutes",
            body=f"{row.title}: {row.room or 'See the agenda'}",
            deep_link=link,
            preference="session_reminders",
        )
    if sent:
        await db.commit()
    return sent
