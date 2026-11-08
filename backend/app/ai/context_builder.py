import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entities import (
    Badge,
    Bookmark,
    Category,
    Certificate,
    Event,
    EventFaq,
    Exhibitor,
    Resource,
    Session,
    SessionSpeaker,
    Speaker,
    SpeakerCategory,
    User,
    Venue,
    VenueFacility,
)
from app.services.congress_service import _as_utc

_cache: dict[str, tuple[float, str, dict]] = {}


def invalidate(event_id: str | None = None) -> None:
    if event_id is None:
        _cache.clear()
    else:
        _cache.pop(event_id, None)


async def build_context(db: AsyncSession, event: Event, ttl_seconds: int = 60) -> tuple[str, dict]:
    fingerprint = await _fingerprint(db, event.id)
    cached = _cache.get(event.id)
    now = time.monotonic()
    if cached and cached[0] == fingerprint and now - cached[1] < ttl_seconds:
        return cached[2], cached[3]
    text, records = await _build(db, event)
    _cache[event.id] = (fingerprint, now, text, records)
    return text, records


async def _fingerprint(db: AsyncSession, event_id: str) -> str:
    sessions = (
        await db.execute(
            select(Session.id, Session.title, Session.status, Session.status_note, Session.room, Session.start_at, Session.visibility).where(
                Session.event_id == event_id
            )
        )
    ).all()
    faqs = (await db.execute(select(EventFaq.id, EventFaq.question, EventFaq.answer, EventFaq.visibility).where(EventFaq.event_id == event_id))).all()
    exhibitors = (
        await db.execute(select(Exhibitor.id, Exhibitor.name, Exhibitor.booth, Exhibitor.visibility).where(Exhibitor.event_id == event_id))
    ).all()
    return repr((sessions, faqs, exhibitors))


async def _build(db: AsyncSession, event: Event) -> tuple[str, dict]:
    tz = ZoneInfo(event.timezone or "Asia/Dubai")
    now_local = datetime.now(UTC).astimezone(tz)
    venue = await db.scalar(select(Venue).where(Venue.event_id == event.id))
    facilities = []
    if venue is not None:
        facilities = (
            await db.scalars(
                select(VenueFacility).where(VenueFacility.venue_id == venue.id, VenueFacility.enabled.is_(True)).order_by(VenueFacility.display_order)
            )
        ).all()
    sessions = (
        await db.scalars(
            select(Session)
            .options(selectinload(Session.category))
            .where(Session.event_id == event.id, Session.visibility == "published")
            .order_by(Session.start_at)
        )
    ).all()
    speaker_rows = (
        await db.scalars(select(Speaker).where(Speaker.event_id == event.id, Speaker.visibility == "published").order_by(Speaker.display_order, Speaker.name))
    ).all()
    session_ids = [row.id for row in sessions]
    links = []
    if session_ids:
        links = (await db.execute(select(SessionSpeaker.session_id, SessionSpeaker.speaker_id).where(SessionSpeaker.session_id.in_(session_ids)))).all()
    by_session: dict[str, list[str]] = {}
    by_speaker: dict[str, list[str]] = {}
    sessions_by_id = {row.id: row for row in sessions}
    speakers_by_id = {row.id: row for row in speaker_rows}
    for session_id, speaker_id in links:
        session = sessions_by_id.get(session_id)
        speaker = speakers_by_id.get(speaker_id)
        if session is None or speaker is None:
            continue
        by_session.setdefault(session_id, []).append(speaker.name)
        by_speaker.setdefault(speaker_id, []).append(session.title)
    specializations = await _specializations(db, [row.id for row in speaker_rows])
    faqs = (
        await db.scalars(
            select(EventFaq)
            .where(EventFaq.event_id == event.id, EventFaq.visibility == "published")
            .order_by(EventFaq.display_order, EventFaq.created_at)
        )
    ).all()
    resources = (
        await db.scalars(
            select(Resource).where(Resource.event_id == event.id, Resource.visibility == "published", Resource.published_at.is_not(None)).order_by(Resource.title)
        )
    ).all()
    exhibitors = (
        await db.scalars(
            select(Exhibitor).where(Exhibitor.event_id == event.id, Exhibitor.visibility == "published").order_by(Exhibitor.display_order, Exhibitor.name)
        )
    ).all()
    exhibitor_categories = {
        row.id: row.name
        for row in (await db.scalars(select(Category).where(Category.event_id == event.id, Category.type == "exhibitor"))).all()
    }

    day_index = _day_index(sessions, tz)
    session_records = [_session_record(row, tz, day_index, by_session.get(row.id, [])) for row in sessions]
    speaker_records = [
        {
            "id": row.id,
            "name": row.name,
            "label": row.name,
            "designation": row.designation or "",
            "organization": row.organization or "",
            "country": row.country or "",
            "bio": (row.biography or "")[:300],
            "specializations": specializations.get(row.id, []),
            "sessions": by_speaker.get(row.id, []),
        }
        for row in speaker_rows
    ]
    venue_record = None
    if venue is not None:
        venue_record = {
            "id": venue.id,
            "name": venue.name,
            "label": venue.name,
            "address": venue.address,
            "facilities": [row.label for row in facilities],
        }
    faq_records = [{"id": row.id, "question": row.question, "answer": row.answer[:1000]} for row in faqs]
    resource_records = [
        {"id": row.id, "title": row.title, "label": row.title, "type": row.type, "description": (row.description or "")[:300]} for row in resources
    ]
    records = {
        "event": {
            "name": event.name,
            "title": event.title,
            "tagline": event.tagline or "",
            "city": event.city,
            "country": event.country,
            "timezone": event.timezone,
            "description": event.description or "",
            "now_local": now_local.strftime("%I:%M %p"),
            "weekday": now_local.strftime("%A"),
            "date_label": now_local.strftime("%d %b %Y"),
        },
        "venue": venue_record,
        "sessions": session_records,
        "speakers": speaker_records,
        "faqs": faq_records,
        "resources": resource_records,
        "exhibitors": [
            {
                "id": row.id,
                "name": row.name,
                "label": row.name,
                "booth": row.booth or "",
                "category": exhibitor_categories.get(row.category_id or "", ""),
                "description": (row.description or "")[:300],
            }
            for row in exhibitors
        ],
    }
    text = _render(records)
    text = _fit_budget(text, records)
    return text, records


async def account_context(db: AsyncSession, user: User, event: Event, records: dict) -> str:
    """Facts about the signed-in attendee only. Not cached and never mixed with other accounts."""
    badge = await db.scalar(select(Badge).where(Badge.user_id == user.id, Badge.event_id == event.id))
    saved_sessions = (
        await db.scalars(select(Bookmark.target_id).where(Bookmark.user_id == user.id, Bookmark.target_type == "session"))
    ).all()
    saved_resources = await db.scalar(
        select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user.id, Bookmark.target_type == "resource")
    )
    certificates = await db.scalar(
        select(func.count()).select_from(Certificate).where(Certificate.user_id == user.id, Certificate.event_id == event.id, Certificate.status == "issued")
    )
    event_count = await db.scalar(select(func.count()).select_from(Event))
    sessions = records.get("sessions") or []
    by_id = {row["id"]: row["title"] for row in sessions}
    saved_titles = [by_id[item] for item in saved_sessions if item in by_id]
    days = sorted({row["day_label"] for row in sessions})
    tz = ZoneInfo(event.timezone or "Asia/Dubai")
    start = _as_utc(event.start_at).astimezone(tz)
    end = _as_utc(event.end_at).astimezone(tz)
    lines = [
        f"Name: {user.full_name}",
        f"Organization: {user.organization}",
        f"Designation: {user.designation or 'not set'}",
        f"Location: {user.location or 'not set'}",
        f"Badge ID: {badge.badge_code if badge else 'not issued'}",
        f"Saved sessions: {len(saved_titles)}" + (f" ({', '.join(saved_titles)})" if saved_titles else ""),
        f"Saved resources: {int(saved_resources or 0)}",
        f"Certificates: {int(certificates or 0)}",
        f"Events in the app: {int(event_count or 0)}",
        f"Current event: {event.name}",
        f"Event dates: {start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')} ({event.timezone})",
        f"Sessions in the current event: {len(sessions)} across {len(days) or 0} day(s)",
    ]
    return "\n".join(lines)


def known_ids(records: dict) -> dict[tuple[str, str], str]:
    known: dict[tuple[str, str], str] = {}
    venue = records.get("venue")
    if venue:
        known[("venue", venue["id"])] = venue["name"]
    for row in records.get("sessions") or []:
        known[("session", row["id"])] = row["title"]
    for row in records.get("speakers") or []:
        known[("speaker", row["id"])] = row["name"]
    for row in records.get("resources") or []:
        known[("resource", row["id"])] = row["title"]
    for row in records.get("exhibitors") or []:
        known[("exhibitor", row["id"])] = row["name"]
    return known


def _day_index(sessions: list[Session], tz: ZoneInfo) -> dict[str, tuple[int, str]]:
    dates = []
    for row in sessions:
        local = _as_utc(row.start_at).astimezone(tz).date()
        if local not in dates:
            dates.append(local)
    return {str(day): (index + 1, day.strftime("%a %d %b %Y")) for index, day in enumerate(dates)}


def _session_record(row: Session, tz: ZoneInfo, day_index: dict, speakers: list[str]) -> dict:
    start = _as_utc(row.start_at).astimezone(tz)
    end = _as_utc(row.end_at).astimezone(tz)
    day_number, _ = day_index[str(start.date())]
    category = row.category.name if row.category is not None else ""
    slug = row.category.slug if row.category is not None else ""
    return {
        "id": row.id,
        "title": row.title,
        "label": row.title,
        "summary": row.summary or "",
        "day_number": day_number,
        "day_label": f"Day {day_number}",
        "date_label": start.strftime("%d %b %Y"),
        "weekday": start.strftime("%A"),
        "start": start.strftime("%I:%M %p"),
        "end": end.strftime("%I:%M %p"),
        "start_sort": start.strftime("%H:%M"),
        "category": category,
        "category_slug": slug,
        "room": row.room or "",
        "status": row.status,
        "status_note": row.status_note or "",
        "speakers": speakers or ([row.speaker_name] if row.speaker_name else []),
    }


async def _specializations(db: AsyncSession, speaker_ids: list[str]) -> dict[str, list[str]]:
    if not speaker_ids:
        return {}
    rows = (
        await db.execute(
            select(SpeakerCategory.speaker_id, Category.name)
            .join(Category, Category.id == SpeakerCategory.category_id)
            .where(SpeakerCategory.speaker_id.in_(speaker_ids))
        )
    ).all()
    grouped: dict[str, list[str]] = {}
    for speaker_id, name in rows:
        grouped.setdefault(speaker_id, []).append(name)
    return grouped


def _render(records: dict) -> str:
    event = records["event"]
    lines = [
        f"Event: {event['title']} · {event['name']} · {event['city']}, {event['country']} · {event['timezone']}",
        f"Now: {event['date_label']} {event['now_local']} {event['weekday']}",
    ]
    if event.get("tagline"):
        lines.append(f"Tagline: {event['tagline']}")
    if event.get("description"):
        lines.append(f"Description: {event['description']}")
    venue = records.get("venue")
    if venue:
        lines.append(f"[venue:{venue['id']}] {venue['name']} · {venue['address']} · Facilities: {', '.join(venue['facilities']) or 'none'}")
    for row in records["sessions"]:
        note = f" · Note: {row['status_note']}" if row["status_note"] else ""
        speakers = ", ".join(row["speakers"]) or "none"
        lines.append(
            f"[session:{row['id']}] {row['day_label']} · {row['weekday']} {row['date_label']} · {row['start']}–{row['end']} · "
            f"{row['category']} · {row['title']} · {row['room']} · Status: {row['status']}{note} · Speakers: {speakers}"
        )
    for row in records["speakers"]:
        specs = ", ".join(row["specializations"])
        sessions = ", ".join(row["sessions"])
        lines.append(
            f"[speaker:{row['id']}] {row['name']} · {row['designation']} · {row['organization']} · {row['country']} · "
            f"{specs} · {row['bio']} · Sessions: {sessions}"
        )
    for row in records["faqs"]:
        lines.append(f"FAQ: {row['question']} — {row['answer']}")
    for row in records["resources"]:
        lines.append(f"[resource:{row['id']}] {row['title']} · {row['type']} · {row['description']}")
    for row in records.get("exhibitors") or []:
        lines.append(f"[exhibitor:{row['id']}] {row['name']} · Booth {row['booth']} · {row['category']} · {row['description']}")
    return "\n".join(lines)


def _fit_budget(text: str, records: dict) -> str:
    if len(text) // 4 <= 12000:
        return text
    for row in records["speakers"]:
        row["bio"] = ""
    text = _render(records)
    if len(text) // 4 <= 12000:
        return text
    for row in records["resources"]:
        row["description"] = ""
    return _render(records)
