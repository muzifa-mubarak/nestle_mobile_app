from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import json

import segno
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decrypt_token
from app.models.entities import (
    Badge,
    Bookmark,
    Category,
    Event,
    Exhibitor,
    Notification,
    Session,
    SessionSpeaker,
    Speaker,
    SpeakerCategory,
    User,
    Venue,
    VenueFacility,
)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def event_payload(event: Event) -> dict:
    tz = ZoneInfo(event.timezone)
    start = _as_utc(event.start_at).astimezone(tz)
    end = _as_utc(event.end_at).astimezone(tz)
    days = []
    cursor = start.date()
    index = 1
    while cursor <= end.date():
        days.append(
            {
                "index": index,
                "date": cursor.isoformat(),
                "label": f"Day {index}",
                "short": f"{cursor.strftime('%b')} {cursor.day}",
            }
        )
        index += 1
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    same_month = start.strftime("%b") == end.strftime("%b") and start.year == end.year
    if same_month:
        dates_label = f"{start.strftime('%b')} {start.day} - {end.day}, {end.year}"
    else:
        dates_label = f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}, {end.year}"
    return {
        "id": event.id,
        "name": event.name,
        "title": event.title,
        "tagline": event.tagline,
        "description": event.description,
        "start_at": _as_utc(event.start_at).isoformat().replace("+00:00", "Z"),
        "end_at": _as_utc(event.end_at).isoformat().replace("+00:00", "Z"),
        "timezone": event.timezone,
        "city": event.city,
        "country": event.country,
        "dates_label": dates_label,
        "days": days,
        "settings": {
            "qna_moderation_enabled": event.qna_moderation_enabled,
            "google_signin_enabled": event.google_signin_enabled,
            "apple_signin_enabled": event.apple_signin_enabled,
        },
    }


def format_phone(phone: str | None) -> str:
    import re

    if not phone:
        return ""
    match = re.fullmatch(r"\+971(\d{2})(\d{3})(\d{4})", phone)
    if match:
        return f"+971 {match.group(1)} {match.group(2)} {match.group(3)}"
    return phone


def _badge_attendee_type(value: str | None) -> str:
    text = (value or "Attendee").strip()
    if text.lower().endswith("attendee"):
        return "Attendee"
    return text


def session_payload(session: Session, tz_name: str, now: datetime, bookmarked: set[str] | None = None) -> dict:
    tz = ZoneInfo(tz_name)
    start = _as_utc(session.start_at).astimezone(tz)
    end = _as_utc(session.end_at).astimezone(tz)
    now_utc = _as_utc(now)
    return {
        "id": session.id,
        "title": session.title,
        "summary": session.summary,
        "description": session.description or session.summary,
        "category": {
            "id": session.category.id,
            "name": session.category.name,
            "slug": session.category.slug,
            "color": session.category.color,
        },
        "start_at": _as_utc(session.start_at).isoformat().replace("+00:00", "Z"),
        "end_at": _as_utc(session.end_at).isoformat().replace("+00:00", "Z"),
        "start_local": start.strftime("%I:%M"),
        "end_local": end.strftime("%I:%M"),
        "meridiem": start.strftime("%p"),
        "end_meridiem": end.strftime("%p"),
        "weekday": start.strftime("%A"),
        "date_label": f"{start.strftime('%B')} {start.day}, {start.year}",
        "room": session.room,
        "speaker_name": session.speaker_name,
        "status": session.status,
        "status_note": session.status_note,
        "is_bookmarked": session.id in (bookmarked or set()),
        "is_live": _as_utc(session.start_at) <= now_utc < _as_utc(session.end_at) and session.status != "cancelled",
        "is_next": False,
    }


async def _bookmarked_ids(db: AsyncSession, user_id: str, target_type: str = "session") -> set[str]:
    rows = await db.scalars(select(Bookmark.target_id).where(Bookmark.user_id == user_id, Bookmark.target_type == target_type))
    return set(rows.all())


def _mark_next(sessions: list[dict], now: datetime) -> None:
    upcoming = [item for item in sessions if item["status"] != "cancelled" and item["end_at"] > now.isoformat().replace("+00:00", "Z")]
    if not upcoming:
        return
    live = next((item for item in upcoming if item["is_live"]), None)
    target = live or upcoming[0]
    target["is_next"] = True


async def get_current_event(db: AsyncSession) -> Event:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        raise AppError(404, "NOT_FOUND", "No current congress is published.")
    return event


async def upcoming_sessions(db: AsyncSession, event: Event, limit: int = 5, user_id: str | None = None) -> dict:
    now = datetime.now(UTC)
    base = (
        select(Session)
        .options(selectinload(Session.category))
        .where(
            Session.event_id == event.id,
            Session.visibility == "published",
            Session.status != "cancelled",
        )
    )
    if now > _as_utc(event.end_at):
        return {
            "sessions": [],
            "empty_reason": "ended",
            "message": "The congress has ended. Thank you for joining.",
        }
    if now < _as_utc(event.start_at):
        tz = ZoneInfo(event.timezone)
        day1 = _as_utc(event.start_at).astimezone(tz).date()
        rows = (await db.scalars(base.order_by(Session.start_at, Session.display_order))).all()
        chosen = [row for row in rows if _as_utc(row.start_at).astimezone(tz).date() == day1][:limit]
    else:
        chosen = (
            await db.scalars(
                base.where(Session.end_at > now).order_by(Session.start_at, Session.display_order).limit(limit)
            )
        ).all()
    saved = await _bookmarked_ids(db, user_id) if user_id else set()
    return {
        "sessions": [session_payload(row, event.timezone, now, saved) for row in chosen],
        "empty_reason": None,
        "message": None,
    }


def _initials(name: str) -> str:
    titles = {"dr", "dr.", "prof", "prof.", "mr", "mr.", "mrs", "mrs.", "ms", "ms."}
    parts = [part for part in name.replace(".", " ").split() if part.lower() not in titles]
    if not parts:
        parts = name.split()
    letters = "".join(part[0] for part in parts[:2] if part)
    return letters.upper()


def _badge_dates(event: Event) -> str:
    tz = ZoneInfo(event.timezone)
    start = _as_utc(event.start_at).astimezone(tz)
    end = _as_utc(event.end_at).astimezone(tz)
    if start.month == end.month and start.year == end.year:
        return f"{start.day} - {end.day} {start.strftime('%B')} {start.year}"
    return f"{start.day} {start.strftime('%b')} - {end.day} {end.strftime('%b')} {end.year}"


def _qr_modules(payload: str) -> list[str]:
    matrix = segno.make(payload, error="m").matrix
    rows = ["".join("1" if cell else "0" for cell in row) for row in matrix]
    pad = "0000"
    quiet = "0" * (len(rows[0]) + 8)
    return [quiet] * 4 + [pad + row + pad for row in rows] + [quiet] * 4


async def search_sessions(db: AsyncSession, event: Event, query: str, user_id: str | None = None) -> dict:
    term = f"%{query.strip().lower()}%"
    rows = (
        await db.scalars(
            select(Session)
            .options(selectinload(Session.category))
            .where(
                Session.event_id == event.id,
                Session.visibility == "published",
                func.lower(Session.title).like(term),
            )
            .order_by(Session.start_at)
            .limit(20)
        )
    ).all()
    now = datetime.now(UTC)
    saved = await _bookmarked_ids(db, user_id) if user_id else set()
    speakers = await list_speakers(db, event, query, None, False, None, None, 8)
    exhibitors = await list_exhibitors(db, event, query, None)
    return {
        "sessions": [session_payload(row, event.timezone, now, saved) for row in rows],
        "speakers": speakers["speakers"],
        "resources": [],
        "exhibitors": exhibitors["exhibitors"][:8],
    }


async def profile_payload(db: AsyncSession, user: User) -> dict:
    badge = await db.scalar(select(Badge).where(Badge.user_id == user.id))
    session_count = await db.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user.id, Bookmark.target_type == "session")
    )
    saved_count = await db.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user.id, Bookmark.target_type == "resource")
    )
    from app.models.entities import Certificate

    certificate_count = await db.scalar(
        select(func.count()).select_from(Certificate).where(Certificate.user_id == user.id, Certificate.status == "issued")
    )
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "organization": user.organization,
        "designation": user.designation,
        "attendee_type": user.attendee_type,
        "phone": user.phone,
        "phone_display": format_phone(user.phone),
        "location": user.location,
        "notification_preferences": __import__("json").loads(user.notification_preferences or "{}") or {
            "event_updates": True,
            "session_reminders": True,
            "qna": True,
            "resources": True,
        },
        "avatar_url": user.avatar_url,
        "badge_code": badge.badge_code if badge else None,
        "role": user.role,
        "status": user.status,
        "counts": {
            "sessions": int(session_count or 0),
            "saved": int(saved_count or 0),
            "certificates": int(certificate_count or 0),
        },
    }


async def categories_for(db: AsyncSession, event_id: str, category_type: str) -> list[dict]:
    rows = (
        await db.scalars(
            select(Category).where(Category.event_id == event_id, Category.type == category_type).order_by(Category.display_order, Category.name)
        )
    ).all()
    return [{"id": row.id, "name": row.name, "slug": row.slug, "color": row.color} for row in rows]


async def speaker_session_ids(db: AsyncSession, event_id: str, user_id: str) -> set[str]:
    speaker_ids = list((await db.scalars(select(Speaker.id).where(Speaker.event_id == event_id, Speaker.user_id == user_id))).all())
    if not speaker_ids:
        return set()
    rows = await db.scalars(select(SessionSpeaker.session_id).where(SessionSpeaker.speaker_id.in_(speaker_ids)))
    return set(rows.all())


async def agenda(db: AsyncSession, event: Event, user_id: str, day: str | None, category_id: str | None, query: str | None, saved_only: bool, mine: bool = False) -> dict:
    tz = ZoneInfo(event.timezone)
    now = datetime.now(UTC)
    today = now.astimezone(tz).date().isoformat()
    selected = day or _as_utc(event.start_at).astimezone(tz).date().isoformat()
    rows = (
        await db.scalars(
            select(Session)
            .options(selectinload(Session.category))
            .where(Session.event_id == event.id, Session.visibility == "published", Session.status.in_(["scheduled", "changed", "cancelled"]))
            .order_by(Session.start_at, Session.display_order)
        )
    ).all()
    bookmarked = await _bookmarked_ids(db, user_id)
    mine_ids = await speaker_session_ids(db, event.id, user_id)
    term = (query or "").strip().lower()
    chosen = []
    for row in rows:
        local_date = _as_utc(row.start_at).astimezone(tz).date().isoformat()
        if local_date != selected:
            continue
        if mine and row.id not in mine_ids:
            continue
        if category_id and row.category_id != category_id:
            continue
        if term and term not in row.title.lower() and term not in (row.speaker_name or "").lower() and term not in (row.room or "").lower():
            continue
        if saved_only and row.id not in bookmarked:
            continue
        chosen.append(row)
    payload = [session_payload(row, event.timezone, now, bookmarked) for row in chosen]
    _mark_next(payload, now)
    selected_date = datetime.fromisoformat(selected)
    return {
        "date": selected,
        "weekday": selected_date.strftime("%A"),
        "date_label": f"{selected_date.strftime('%B')} {selected_date.day}, {selected_date.year}",
        "heading": "My Sessions" if mine else ("Today's Sessions" if selected == today else "Sessions"),
        "can_filter_mine": bool(mine_ids),
        "sessions": payload,
    }


async def session_detail(db: AsyncSession, session_id: str, user_id: str) -> dict:
    row = await db.scalar(select(Session).options(selectinload(Session.category)).where(Session.id == session_id))
    if row is None or row.visibility != "published":
        raise AppError(404, "NOT_FOUND", "Session not found.")
    event = await db.get(Event, row.event_id)
    bookmarked = await _bookmarked_ids(db, user_id)
    payload = session_payload(row, event.timezone if event else "Asia/Dubai", datetime.now(UTC), bookmarked)
    payload["timezone"] = event.timezone if event else "Asia/Dubai"
    payload["speakers"] = await _session_speakers(db, row.id)
    return payload


def _speaker_card(speaker: Speaker, categories: list[Category], session: Session | None) -> dict:
    return {
        "id": speaker.id,
        "name": speaker.name,
        "designation": speaker.designation,
        "organization": speaker.organization,
        "country": speaker.country,
        "photo_url": speaker.photo_url,
        "is_featured": bool(speaker.is_featured),
        "initials": _initials(speaker.name),
        "specializations": [{"id": row.id, "name": row.name, "slug": row.slug, "color": row.color} for row in categories],
        "session": None if session is None else {"id": session.id, "title": session.title},
    }


async def _speaker_links(db: AsyncSession, speaker_ids: list[str]) -> tuple[dict[str, list[Category]], dict[str, Session]]:
    if not speaker_ids:
        return {}, {}
    category_rows = (
        await db.execute(
            select(SpeakerCategory.speaker_id, Category)
            .join(Category, Category.id == SpeakerCategory.category_id)
            .where(SpeakerCategory.speaker_id.in_(speaker_ids))
            .order_by(Category.display_order, Category.name)
        )
    ).all()
    categories: dict[str, list[Category]] = {speaker_id: [] for speaker_id in speaker_ids}
    for speaker_id, category in category_rows:
        categories[speaker_id].append(category)
    session_rows = (
        await db.execute(
            select(SessionSpeaker.speaker_id, Session)
            .join(Session, Session.id == SessionSpeaker.session_id)
            .where(SessionSpeaker.speaker_id.in_(speaker_ids), Session.visibility == "published")
            .order_by(Session.start_at, SessionSpeaker.display_order)
        )
    ).all()
    first_session: dict[str, Session] = {}
    for speaker_id, session in session_rows:
        first_session.setdefault(speaker_id, session)
    return categories, first_session


async def _session_speakers(db: AsyncSession, session_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(Speaker)
            .join(SessionSpeaker, SessionSpeaker.speaker_id == Speaker.id)
            .where(SessionSpeaker.session_id == session_id)
            .order_by(SessionSpeaker.display_order, Speaker.name)
        )
    ).scalars().all()
    return [{"id": row.id, "name": row.name, "designation": row.designation, "initials": _initials(row.name)} for row in rows]


async def list_speakers(
    db: AsyncSession,
    event: Event,
    query: str | None,
    category_id: str | None,
    featured: bool,
    country: str | None,
    cursor: str | None,
    limit: int,
) -> dict:
    try:
        offset = max(int(cursor or "0"), 0)
    except ValueError:
        offset = 0
    limit = min(max(limit, 1), 100)
    filters = [Speaker.event_id == event.id, Speaker.visibility == "published"]
    if featured:
        filters.append(Speaker.is_featured.is_(True))
    if country:
        filters.append(func.lower(Speaker.country) == country.strip().lower())
    term = (query or "").strip().lower()
    if term:
        like = f"%{term}%"
        filters.append(
            or_(
                func.lower(Speaker.name).like(like),
                func.lower(func.coalesce(Speaker.designation, "")).like(like),
                func.lower(func.coalesce(Speaker.organization, "")).like(like),
                func.lower(func.coalesce(Speaker.country, "")).like(like),
            )
        )
    stmt = select(Speaker).where(*filters)
    if category_id:
        stmt = stmt.join(SpeakerCategory, SpeakerCategory.speaker_id == Speaker.id).where(SpeakerCategory.category_id == category_id)
    stmt = stmt.order_by(Speaker.is_featured.desc(), Speaker.display_order, Speaker.name)
    rows = (await db.scalars(stmt.offset(offset).limit(limit + 1))).all()
    page = rows[:limit]
    categories, sessions = await _speaker_links(db, [row.id for row in page])
    countries = (
        await db.scalars(
            select(Speaker.country)
            .where(Speaker.event_id == event.id, Speaker.visibility == "published", Speaker.country.is_not(None))
            .distinct()
            .order_by(Speaker.country)
        )
    ).all()
    next_cursor = str(offset + limit) if len(rows) > limit else None
    return {
        "speakers": [_speaker_card(row, categories.get(row.id, []), sessions.get(row.id)) for row in page],
        "next_cursor": next_cursor,
        "countries": [item for item in countries if item],
    }


async def speaker_detail(db: AsyncSession, speaker_id: str, user_id: str | None = None) -> dict:
    speaker = await db.get(Speaker, speaker_id)
    if speaker is None or speaker.visibility != "published":
        raise AppError(404, "NOT_FOUND", "Speaker not found.")
    event = await db.get(Event, speaker.event_id)
    categories, _sessions = await _speaker_links(db, [speaker.id])
    session_rows = (
        await db.scalars(
            select(Session)
            .options(selectinload(Session.category))
            .join(SessionSpeaker, SessionSpeaker.session_id == Session.id)
            .where(SessionSpeaker.speaker_id == speaker.id, Session.visibility == "published")
            .order_by(Session.start_at, Session.display_order)
        )
    ).all()
    now = datetime.now(UTC)
    bookmarked = await _bookmarked_ids(db, user_id) if user_id else set()
    card = _speaker_card(speaker, categories.get(speaker.id, []), session_rows[0] if session_rows else None)
    card["biography"] = speaker.biography
    card["sessions"] = [session_payload(row, event.timezone if event else "Asia/Dubai", now, bookmarked) for row in session_rows]
    return card


async def badge_payload(db: AsyncSession, user: User) -> dict:
    badge = await db.scalar(select(Badge).where(Badge.user_id == user.id))
    if badge is None:
        raise AppError(404, "NOT_FOUND", "Badge not found.")
    event = await db.get(Event, badge.event_id)
    if event is None:
        event = await get_current_event(db)
    token = decrypt_token(badge.qr_token_enc)
    payload = f"nmc://badge/{token}"
    status = "revoked" if user.status == "suspended" or badge.status == "revoked" else badge.status
    location = user.location or f"{event.city}, {event.country}"
    checked_in = _as_utc(badge.checked_in_at).isoformat().replace("+00:00", "Z") if badge.checked_in_at else None
    return {
        "badge_code": badge.badge_code,
        "full_name": user.full_name,
        "designation": user.designation,
        "attendee_type": _badge_attendee_type(user.attendee_type),
        "location": location,
        "initials": _initials(user.full_name),
        "avatar_url": user.avatar_url,
        "event_name": event.title,
        "event_dates_label": _badge_dates(event),
        "qr_payload": payload,
        "qr_modules": _qr_modules(payload),
        "status": status,
        "checked_in_at": checked_in,
    }


async def venue_payload(db: AsyncSession, event: Event) -> dict:
    venue = await db.scalar(select(Venue).where(Venue.event_id == event.id))
    if venue is None:
        raise AppError(404, "NOT_FOUND", "Venue is not published yet.")
    facilities = (
        await db.scalars(
            select(VenueFacility)
            .where(VenueFacility.venue_id == venue.id, VenueFacility.enabled.is_(True))
            .order_by(VenueFacility.display_order, VenueFacility.label)
        )
    ).all()
    try:
        notices = json.loads(venue.notices or "[]")
    except json.JSONDecodeError:
        notices = []
    from urllib.parse import quote

    query = f"{venue.latitude},{venue.longitude}" if venue.latitude is not None and venue.longitude is not None else venue.address
    return {
        "id": venue.id,
        "name": venue.name,
        "address": venue.address,
        "latitude": venue.latitude,
        "longitude": venue.longitude,
        "dates_label": _badge_dates(event),
        "map_available": venue.latitude is not None and venue.longitude is not None,
        "directions_url": f"https://www.google.com/maps/search/?api=1&query={quote(str(query))}",
        "facilities": [
            {"key": row.key, "label": row.label, "icon": row.icon, "display_order": row.display_order} for row in facilities
        ],
        "notices": notices if isinstance(notices, list) else [],
    }


async def set_bookmark(db: AsyncSession, user_id: str, target_type: str, target_id: str, enabled: bool) -> dict:
    if target_type == "session":
        session = await db.get(Session, target_id)
        if session is None or session.visibility != "published":
            raise AppError(404, "NOT_FOUND", "Session not found.")
    elif target_type == "resource":
        from app.models.entities import Resource

        resource = await db.get(Resource, target_id)
        if resource is None or resource.visibility != "published" or resource.published_at is None:
            raise AppError(404, "NOT_FOUND", "Resource not found.")
    else:
        raise AppError(404, "NOT_FOUND", "Bookmark target not found.")
    existing = await db.scalar(
        select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.target_type == target_type, Bookmark.target_id == target_id)
    )
    if enabled and existing is None:
        db.add(Bookmark(user_id=user_id, target_type=target_type, target_id=target_id))
    if not enabled and existing is not None:
        await db.delete(existing)
    await db.commit()
    return {"bookmarked": enabled}


def _exhibitor_payload(row: Exhibitor, category: Category | None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "booth": row.booth,
        "description": row.description,
        "logo_url": row.logo_url,
        "website": row.website,
        "contact_email": row.contact_email,
        "display_order": row.display_order,
        "visibility": row.visibility,
        "category": {"id": category.id, "name": category.name} if category else None,
    }


async def list_exhibitors(db: AsyncSession, event: Event, query: str | None, category_id: str | None) -> dict:
    stmt = select(Exhibitor).where(Exhibitor.event_id == event.id, Exhibitor.visibility == "published")
    if category_id:
        stmt = stmt.where(Exhibitor.category_id == category_id)
    if query and query.strip():
        term = f"%{query.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Exhibitor.name).like(term), func.lower(Exhibitor.booth).like(term), func.lower(Exhibitor.description).like(term)))
    rows = list((await db.scalars(stmt.order_by(Exhibitor.display_order, Exhibitor.name))).all())
    categories = {
        item.id: item
        for item in (
            await db.scalars(select(Category).where(Category.event_id == event.id, Category.type == "exhibitor"))
        ).all()
    }
    return {"exhibitors": [_exhibitor_payload(row, categories.get(row.category_id or "")) for row in rows]}


async def get_exhibitor(db: AsyncSession, exhibitor_id: str) -> dict:
    row = await db.get(Exhibitor, exhibitor_id)
    if row is None or row.visibility != "published":
        raise AppError(404, "NOT_FOUND", "Exhibitor not found.")
    category = await db.get(Category, row.category_id) if row.category_id else None
    return _exhibitor_payload(row, category)


def _notification_payload(row: Notification) -> dict:
    created = _as_utc(row.created_at) if row.created_at else None
    read_at = _as_utc(row.read_at) if row.read_at else None
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "deep_link": row.deep_link,
        "read_at": read_at.isoformat().replace("+00:00", "Z") if read_at else None,
        "is_read": read_at is not None,
        "created_at": created.isoformat().replace("+00:00", "Z") if created else None,
    }


async def list_notifications(db: AsyncSession, user_id: str) -> dict:
    rows = list(
        (
            await db.scalars(
                select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(50)
            )
        ).all()
    )
    return {"notifications": [_notification_payload(row) for row in rows], "unread_count": await unread_count(db, user_id)}


async def mark_notification_read(db: AsyncSession, user_id: str, notification_id: str) -> dict:
    row = await db.get(Notification, notification_id)
    if row is None or row.user_id != user_id:
        raise AppError(404, "NOT_FOUND", "Notification not found.")
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await db.commit()
    return {"id": row.id, "is_read": True, "unread_count": await unread_count(db, user_id)}


async def mark_all_notifications_read(db: AsyncSession, user_id: str) -> dict:
    rows = list(
        (await db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None)))).all()
    )
    now = datetime.now(UTC)
    for row in rows:
        row.read_at = now
    await db.commit()
    return {"updated": len(rows), "unread_count": 0}


async def unread_count(db: AsyncSession, user_id: str) -> int:
    value = await db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return int(value or 0)
