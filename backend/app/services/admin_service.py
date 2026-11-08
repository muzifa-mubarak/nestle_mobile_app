"""Organizer actions for the current congress."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.realtime import hub
from app.ai.context_builder import invalidate
from app.services import notify as notify_service
from app.models.entities import Category, Event, Exhibitor, Poll, PollOption, Question, Resource, Session, User
from app.services import qna_service
from app.services.congress_service import get_current_event


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_dt(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppError(422, "VALIDATION_ERROR", "Enter a valid date and time.", [{"field": field, "message": "Enter a valid date and time."}]) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _session_row(row: Session, category_name: str | None) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "summary": row.summary,
        "category_id": row.category_id,
        "category_name": category_name,
        "start_at": _iso(row.start_at),
        "end_at": _iso(row.end_at),
        "room": row.room,
        "speaker_name": row.speaker_name,
        "status": row.status,
        "visibility": row.visibility,
    }


async def _event(db: AsyncSession) -> Event:
    return await get_current_event(db)


async def overview(db: AsyncSession) -> dict:
    event = await _event(db)
    attendees = await db.scalar(select(func.count()).select_from(User).where(User.deleted_at.is_(None), User.role == "attendee"))
    sessions = await db.scalar(select(func.count()).select_from(Session).where(Session.event_id == event.id))
    active_polls = await db.scalar(select(func.count()).select_from(Poll).where(Poll.event_id == event.id, Poll.status == "active"))
    pending = await db.scalar(select(func.count()).select_from(Question).where(Question.event_id == event.id, Question.status == "pending"))
    resources = await db.scalar(select(func.count()).select_from(Resource).where(Resource.event_id == event.id))
    return {
        "event": {
            "id": event.id,
            "name": event.name,
            "title": event.title,
            "city": event.city,
            "start_at": _iso(event.start_at),
            "end_at": _iso(event.end_at),
            "qna_moderation_enabled": event.qna_moderation_enabled,
        },
        "counts": {
            "attendees": int(attendees or 0),
            "sessions": int(sessions or 0),
            "active_polls": int(active_polls or 0),
            "pending_questions": int(pending or 0),
            "resources": int(resources or 0),
        },
    }


async def set_moderation(db: AsyncSession, enabled: bool) -> dict:
    event = await _event(db)
    event.qna_moderation_enabled = enabled
    event.updated_at = datetime.now(UTC)
    await db.commit()
    return {"qna_moderation_enabled": event.qna_moderation_enabled}


async def _categories(db: AsyncSession, event_id: str, kind: str) -> list[Category]:
    rows = await db.scalars(
        select(Category).where(Category.event_id == event_id, Category.type == kind).order_by(Category.display_order, Category.name)
    )
    return list(rows.all())


async def list_sessions(db: AsyncSession) -> dict:
    event = await _event(db)
    rows = list((await db.scalars(select(Session).where(Session.event_id == event.id).order_by(Session.start_at))).all())
    names = {row.id: row.name for row in await _categories(db, event.id, "session")}
    return {
        "categories": [{"id": row.id, "name": row.name} for row in await _categories(db, event.id, "session")],
        "sessions": [_session_row(row, names.get(row.category_id)) for row in rows],
    }


async def create_session(db: AsyncSession, body: dict) -> dict:
    event = await _event(db)
    title = str(body.get("title") or "").strip()
    if not title or len(title) > 200:
        raise AppError(422, "VALIDATION_ERROR", "Enter a session title.", [{"field": "title", "message": "Enter a session title."}])
    category = await db.get(Category, body.get("category_id"))
    if category is None or category.event_id != event.id or category.type != "session":
        raise AppError(422, "VALIDATION_ERROR", "Choose a session category.", [{"field": "category_id", "message": "Choose a session category."}])
    start_at = _parse_dt(str(body.get("start_at") or ""), "start_at")
    end_at = _parse_dt(str(body.get("end_at") or ""), "end_at")
    if end_at <= start_at:
        raise AppError(422, "VALIDATION_ERROR", "The end time must be after the start time.", [{"field": "end_at", "message": "The end time must be after the start time."}])
    row = Session(
        event_id=event.id,
        category_id=category.id,
        title=title,
        summary=(body.get("summary") or title)[:300],
        start_at=start_at,
        end_at=end_at,
        room=(body.get("room") or None),
        speaker_name=(body.get("speaker_name") or None),
        status="scheduled",
        visibility=body.get("visibility") if body.get("visibility") in {"draft", "published"} else "draft",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await hub.broadcast({"type": "schedule.updated", "session_id": row.id})
    return _session_row(row, category.name)


async def set_session_state(db: AsyncSession, session_id: str, action: str) -> dict:
    event = await _event(db)
    row = await db.get(Session, session_id)
    if row is None or row.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Session not found.")
    if action == "publish":
        row.visibility = "published"
    elif action == "unpublish":
        row.visibility = "draft"
    elif action == "cancel":
        row.status = "cancelled"
        row.visibility = "published"
        await notify_service.fanout(
            db,
            await notify_service.bookmarked_users(db, row.id),
            kind="schedule",
            title="Session cancelled",
            body=f"{row.title} has been cancelled",
            deep_link=f"nmc://session/{row.id}",
            preference="session_reminders",
        )
    else:
        raise AppError(422, "VALIDATION_ERROR", "Unknown session action.")
    await db.commit()
    category = await db.get(Category, row.category_id)
    await hub.broadcast({"type": "schedule.updated", "session_id": row.id})
    return _session_row(row, category.name if category else None)


async def list_polls(db: AsyncSession) -> dict:
    event = await _event(db)
    polls = list((await db.scalars(select(Poll).where(Poll.event_id == event.id).order_by(Poll.display_order, Poll.created_at))).all())
    items = []
    for poll in polls:
        options = list(
            (await db.scalars(select(PollOption).where(PollOption.poll_id == poll.id).order_by(PollOption.display_order))).all()
        )
        items.append(
            {
                "id": poll.id,
                "question": poll.question,
                "label": poll.label,
                "status": poll.status,
                "results_visibility": poll.results_visibility,
                "options": [{"id": option.id, "label": option.label} for option in options],
            }
        )
    return {"polls": items}


async def create_poll(db: AsyncSession, body: dict) -> dict:
    event = await _event(db)
    question = str(body.get("question") or "").strip()
    labels = [str(item).strip() for item in body.get("options") or [] if str(item).strip()]
    if len(question) < 5 or len(question) > 300:
        raise AppError(422, "VALIDATION_ERROR", "Enter a poll question.", [{"field": "question", "message": "Enter a poll question."}])
    if len(labels) < 2:
        raise AppError(422, "VALIDATION_ERROR", "Add at least two options.", [{"field": "options", "message": "Add at least two options."}])
    visibility = body.get("results_visibility") if body.get("results_visibility") in {"after_vote", "live", "after_close"} else "after_vote"
    poll = Poll(
        event_id=event.id,
        question=question,
        label=(body.get("label") or "Audience Feedback")[:60],
        type="single",
        status="draft",
        results_visibility=visibility,
    )
    db.add(poll)
    await db.flush()
    for index, label in enumerate(labels):
        db.add(PollOption(poll_id=poll.id, label=label[:150], display_order=index))
    await db.commit()
    await db.refresh(poll)
    return {"id": poll.id, "status": poll.status}


async def set_poll_status(db: AsyncSession, poll_id: str, status: str) -> dict:
    event = await _event(db)
    poll = await db.get(Poll, poll_id)
    if poll is None or poll.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Poll not found.")
    allowed = {"draft", "active", "paused", "closed"}
    if status not in allowed:
        raise AppError(422, "VALIDATION_ERROR", "Choose a valid poll status.")
    poll.status = status
    poll.updated_at = datetime.now(UTC)
    if status == "active":
        await notify_service.fanout(
            db,
            await notify_service.checked_in_attendees(db),
            kind="poll",
            title="New poll is live",
            body=poll.question,
            deep_link=f"nmc://poll/{poll.id}",
            preference="event_updates",
        )
    await db.commit()
    event_type = "poll.activated" if status == "active" else "poll.results_updated"
    await hub.broadcast({"type": event_type, "poll_id": poll.id, "status": status})
    return {"id": poll.id, "status": poll.status}


async def list_questions(db: AsyncSession, status: str | None) -> dict:
    event = await _event(db)
    query = select(Question).where(Question.event_id == event.id)
    if status:
        query = query.where(Question.status == status)
    rows = list((await db.scalars(query.order_by(Question.created_at.desc()))).all())
    categories = {row.id: row.name for row in await _categories(db, event.id, "question")}
    authors = {}
    if rows:
        users = await db.scalars(select(User).where(User.id.in_({row.user_id for row in rows})))
        authors = {user.id: user.full_name for user in users.all()}
    return {
        "questions": [
            {
                "id": row.id,
                "text": row.text,
                "status": row.status,
                "author_name": authors.get(row.user_id, "Attendee"),
                "category_name": categories.get(row.category_id),
                "upvote_count": row.upvote_count,
                "flagged": row.flagged,
                "created_at": _iso(row.created_at),
            }
            for row in rows
        ]
    }


async def moderate_question(db: AsyncSession, question_id: str, action: str, actor: User, reason: str | None = None, answer_text: str | None = None) -> dict:
    event = await _event(db)
    question = await db.get(Question, question_id)
    if question is None or question.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    if action == "approve":
        question.status = "published"
        question.updated_at = datetime.now(UTC)
        await db.commit()
        await hub.broadcast({"type": "question.published", "question_id": question.id})
        return {"id": question.id, "status": question.status}
    if action == "hide":
        question.status = "hidden"
    elif action == "reject":
        question.status = "rejected"
        question.reject_reason = (reason or "Not accepted")[:300]
        author = await db.get(User, question.user_id)
        if author is not None:
            await notify_service.fanout(
                db,
                [author],
                kind="qna",
                title="Question not published",
                body=f"Reason: {question.reject_reason}",
                deep_link="nmc://qna/mine",
                preference="qna",
                push=False,
            )
    elif action == "answer":
        return await qna_service.answer_question(db, question_id, actor, answer_text or "")
    else:
        raise AppError(422, "VALIDATION_ERROR", "Unknown moderation action.")
    question.updated_at = datetime.now(UTC)
    await db.commit()
    await hub.broadcast({"type": "question.updated", "question_id": question.id, "status": question.status})
    return {"id": question.id, "status": question.status}


async def list_resources(db: AsyncSession) -> dict:
    event = await _event(db)
    rows = list((await db.scalars(select(Resource).where(Resource.event_id == event.id).order_by(Resource.created_at.desc()))).all())
    return {
        "resources": [
            {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "type": row.type,
                "visibility": row.visibility,
                "external_url": row.external_url,
            }
            for row in rows
        ]
    }


async def create_resource(db: AsyncSession, actor: User, body: dict) -> dict:
    event = await _event(db)
    title = str(body.get("title") or "").strip()
    if not title or len(title) > 200:
        raise AppError(422, "VALIDATION_ERROR", "Enter a resource title.", [{"field": "title", "message": "Enter a resource title."}])
    kind = body.get("type") if body.get("type") in {"document", "link", "video", "slides"} else "link"
    url = (body.get("external_url") or "").strip() or None
    if kind == "link" and not url:
        raise AppError(422, "VALIDATION_ERROR", "Enter a link for this resource.", [{"field": "external_url", "message": "Enter a link for this resource."}])
    row = Resource(
        event_id=event.id,
        title=title,
        description=(body.get("description") or None),
        type=kind,
        external_url=url,
        visibility="draft",
        created_by=actor.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "title": row.title, "visibility": row.visibility}


async def set_resource_visibility(db: AsyncSession, resource_id: str, visibility: str) -> dict:
    event = await _event(db)
    row = await db.get(Resource, resource_id)
    if row is None or row.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Resource not found.")
    if visibility not in {"draft", "published"}:
        raise AppError(422, "VALIDATION_ERROR", "Choose draft or published.")
    was_published = row.visibility == "published"
    row.visibility = visibility
    row.published_at = datetime.now(UTC) if visibility == "published" else None
    row.updated_at = datetime.now(UTC)
    if visibility == "published" and not was_published:
        await notify_service.fanout(
            db,
            await notify_service.active_attendees(db),
            kind="resource",
            title="New resource available",
            body=row.title,
            deep_link=f"nmc://resource/{row.id}",
            preference="resources",
        )
    await db.commit()
    return {"id": row.id, "visibility": row.visibility}


async def list_attendees(db: AsyncSession) -> dict:
    rows = list(
        (
            await db.scalars(
                select(User).where(User.deleted_at.is_(None), User.role == "attendee").order_by(User.full_name)
            )
        ).all()
    )
    return {
        "attendees": [
            {
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "organization": row.organization,
                "status": row.status,
            }
            for row in rows
        ]
    }


def _exhibitor_admin(row: Exhibitor, category_name: str | None) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "booth": row.booth,
        "description": row.description,
        "website": row.website,
        "contact_email": row.contact_email,
        "category_id": row.category_id,
        "category_name": category_name,
        "visibility": row.visibility,
        "display_order": row.display_order,
    }


async def list_exhibitors(db: AsyncSession) -> dict:
    event = await _event(db)
    rows = list((await db.scalars(select(Exhibitor).where(Exhibitor.event_id == event.id).order_by(Exhibitor.display_order, Exhibitor.name))).all())
    categories = await _categories(db, event.id, "exhibitor")
    names = {row.id: row.name for row in categories}
    return {
        "categories": [{"id": row.id, "name": row.name} for row in categories],
        "exhibitors": [_exhibitor_admin(row, names.get(row.category_id or "")) for row in rows],
    }


async def create_exhibitor(db: AsyncSession, body: dict) -> dict:
    event = await _event(db)
    name = str(body.get("name") or "").strip()
    if not name or len(name) > 160:
        raise AppError(422, "VALIDATION_ERROR", "Enter an exhibitor name.", [{"field": "name", "message": "Enter an exhibitor name."}])
    category_id = body.get("category_id") or None
    if category_id:
        category = await db.get(Category, category_id)
        if category is None or category.event_id != event.id or category.type != "exhibitor":
            raise AppError(422, "VALIDATION_ERROR", "Choose an exhibitor category.", [{"field": "category_id", "message": "Choose an exhibitor category."}])
    row = Exhibitor(
        event_id=event.id,
        category_id=category_id,
        name=name,
        booth=(body.get("booth") or None),
        description=(body.get("description") or None),
        website=(body.get("website") or None),
        contact_email=(body.get("contact_email") or None),
        visibility="published" if body.get("visibility") == "published" else "draft",
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    invalidate(event.id)
    category = await db.get(Category, row.category_id) if row.category_id else None
    return _exhibitor_admin(row, category.name if category else None)


async def update_exhibitor(db: AsyncSession, exhibitor_id: str, body: dict) -> dict:
    event = await _event(db)
    row = await db.get(Exhibitor, exhibitor_id)
    if row is None or row.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Exhibitor not found.")
    if "name" in body and body["name"] is not None:
        name = str(body["name"]).strip()
        if not name:
            raise AppError(422, "VALIDATION_ERROR", "Enter an exhibitor name.", [{"field": "name", "message": "Enter an exhibitor name."}])
        row.name = name[:160]
    for field in ("booth", "description", "website", "contact_email"):
        if field in body:
            row.__setattr__(field, body[field] or None)
    if body.get("visibility") in {"draft", "published"}:
        row.visibility = body["visibility"]
    if body.get("category_id"):
        category = await db.get(Category, body["category_id"])
        if category is None or category.event_id != event.id or category.type != "exhibitor":
            raise AppError(422, "VALIDATION_ERROR", "Choose an exhibitor category.", [{"field": "category_id", "message": "Choose an exhibitor category."}])
        row.category_id = category.id
    await db.commit()
    invalidate(event.id)
    category = await db.get(Category, row.category_id) if row.category_id else None
    return _exhibitor_admin(row, category.name if category else None)


async def delete_exhibitor(db: AsyncSession, exhibitor_id: str) -> dict:
    event = await _event(db)
    row = await db.get(Exhibitor, exhibitor_id)
    if row is None or row.event_id != event.id:
        raise AppError(404, "NOT_FOUND", "Exhibitor not found.")
    await db.delete(row)
    await db.commit()
    invalidate(event.id)
    return {"deleted": True}


async def set_attendee_status(db: AsyncSession, user_id: str, status: str) -> dict:
    if status not in {"active", "suspended", "pending_verification"}:
        raise AppError(422, "VALIDATION_ERROR", "Choose a valid attendee status.")
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.role != "attendee":
        raise AppError(404, "NOT_FOUND", "Attendee not found.")
    was_active = user.status == "active"
    user.status = status
    if status == "active" and user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)
    if status == "active" and not was_active:
        await notify_service.fanout(
            db,
            [user],
            kind="account",
            title="You're approved!",
            body="Your congress account is active",
            deep_link="nmc://home",
            preference=None,
            push=True,
            email=True,
        )
    await db.commit()
    return {"id": user.id, "status": user.status}
