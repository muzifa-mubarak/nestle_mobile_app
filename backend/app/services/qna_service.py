from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.core.realtime import hub
from app.models.entities import Answer, Category, Question, QuestionUpvote, Session, SessionSpeaker, Speaker, User
from app.services import notify as notify_service
from app.services.congress_service import _as_utc, get_current_event

PROFANITY = {"spamword", "idiot"}
ANSWER_ROLES = {"speaker", "moderator", "organizer", "admin"}


def _initials(name: str) -> str:
    cleaned = name.strip()
    return cleaned[:1].upper() if cleaned else ""


def _flagged(text: str) -> bool:
    words = {part.strip(".,!?").lower() for part in text.split()}
    return bool(words & PROFANITY)


async def _category(db: AsyncSession, event_id: str, category_id: str) -> Category:
    row = await db.get(Category, category_id)
    if row is None or row.event_id != event_id or row.type != "question":
        raise AppError(422, "VALIDATION_ERROR", "Choose a question category.", [{"field": "category_id", "message": "Choose a question category."}])
    return row


def _answer_payload(answer: Answer | None, author: User | None) -> dict | None:
    if answer is None or author is None:
        return None
    return {
        "text": answer.answer_text,
        "author_name": author.full_name,
        "author_role": author.role,
        "answered_at": _as_utc(answer.created_at).isoformat().replace("+00:00", "Z"),
    }


async def _card(db: AsyncSession, question: Question, user: User) -> dict:
    category = await db.get(Category, question.category_id)
    author = await db.get(User, question.user_id)
    answer = await db.scalar(select(Answer).where(Answer.question_id == question.id))
    answer_author = await db.get(User, answer.author_user_id) if answer else None
    speaker = await db.get(Speaker, question.speaker_id) if question.speaker_id else None
    voted = await db.scalar(
        select(QuestionUpvote.id).where(QuestionUpvote.question_id == question.id, QuestionUpvote.user_id == user.id)
    )
    footer_name = answer_author.full_name if answer_author else (speaker.name if speaker else (author.full_name if author else "Attendee"))
    return {
        "id": question.id,
        "text": question.text,
        "status": question.status,
        "category": {"id": category.id, "name": category.name, "slug": category.slug, "color": category.color} if category else None,
        "session_id": question.session_id,
        "speaker_id": question.speaker_id,
        "upvote_count": question.upvote_count,
        "has_upvoted": voted is not None,
        "is_mine": question.user_id == user.id,
        "flagged": question.flagged if question.user_id == user.id or user.role in ANSWER_ROLES else False,
        "reject_reason": question.reject_reason if question.user_id == user.id else None,
        "created_at": _as_utc(question.created_at).isoformat().replace("+00:00", "Z") if question.created_at else None,
        "footer_name": footer_name,
        "footer_initials": _initials(footer_name),
        "answer": _answer_payload(answer, answer_author),
    }


async def list_questions(db: AsyncSession, user: User, tab: str, category_id: str | None, session_id: str | None, cursor: str | None, limit: int) -> dict:
    event = await get_current_event(db)
    try:
        offset = max(int(cursor or "0"), 0)
    except ValueError:
        offset = 0
    limit = min(max(limit, 1), 100)
    filters = [Question.event_id == event.id, Question.status.in_(["published", "answered"])]
    if category_id:
        filters.append(Question.category_id == category_id)
    if session_id:
        filters.append(Question.session_id == session_id)
    stmt = select(Question).options(selectinload(Question.category)).where(*filters)
    if tab == "popular":
        stmt = stmt.order_by(Question.upvote_count.desc(), Question.created_at.desc())
    elif tab == "answered":
        stmt = (
            stmt.join(Answer, Answer.question_id == Question.id)
            .where(Question.status == "answered")
            .order_by(Answer.created_at.desc())
        )
    else:
        stmt = stmt.order_by(Question.created_at.desc())
    rows = (await db.scalars(stmt.offset(offset).limit(limit + 1))).all()
    page = rows[:limit]
    return {
        "questions": [await _card(db, row, user) for row in page],
        "next_cursor": str(offset + limit) if len(rows) > limit else None,
    }


async def my_questions(db: AsyncSession, user: User) -> dict:
    event = await get_current_event(db)
    rows = (
        await db.scalars(
            select(Question)
            .options(selectinload(Question.category))
            .where(Question.event_id == event.id, Question.user_id == user.id)
            .order_by(Question.created_at.desc())
        )
    ).all()
    return {"questions": [await _card(db, row, user) for row in rows]}


async def get_question(db: AsyncSession, question_id: str, user: User) -> dict:
    row = await db.scalar(select(Question).options(selectinload(Question.category)).where(Question.id == question_id))
    if row is None:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    if row.status in {"hidden", "rejected", "pending"} and row.user_id != user.id and user.role not in ANSWER_ROLES:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    return await _card(db, row, user)


async def ask_question(db: AsyncSession, user: User, text: str, category_id: str, session_id: str | None, speaker_id: str | None) -> dict:
    event = await get_current_event(db)
    cleaned = " ".join(text.split())
    if len(cleaned) < 10 or len(cleaned) > 500:
        raise AppError(422, "VALIDATION_ERROR", "Enter a question between 10 and 500 characters.", [{"field": "text", "message": "Enter a question between 10 and 500 characters."}])
    await _category(db, event.id, category_id)
    if session_id:
        session = await db.get(Session, session_id)
        if session is None or session.event_id != event.id or session.visibility != "published":
            raise AppError(422, "VALIDATION_ERROR", "That session is not available.", [{"field": "session_id", "message": "That session is not available."}])
    if speaker_id:
        speaker = await db.get(Speaker, speaker_id)
        if speaker is None or speaker.event_id != event.id:
            raise AppError(422, "VALIDATION_ERROR", "That speaker is not available.", [{"field": "speaker_id", "message": "That speaker is not available."}])
    moderated = bool(event.qna_moderation_enabled)
    status = "pending" if moderated else "published"
    question = Question(
        event_id=event.id,
        user_id=user.id,
        session_id=session_id,
        speaker_id=speaker_id,
        category_id=category_id,
        text=cleaned,
        status=status,
        flagged=_flagged(cleaned),
    )
    db.add(question)
    await db.commit()
    await db.refresh(question)
    message = "Submitted for moderation. It will appear once approved." if moderated else "Question submitted"
    if status == "published":
        await hub.broadcast({"type": "question.published", "question": await _card(db, question, user)})
    return {"id": question.id, "status": status, "message": message, "flagged": question.flagged}


async def set_upvote(db: AsyncSession, question_id: str, user: User, enabled: bool) -> dict:
    question = await db.get(Question, question_id)
    if question is None:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    if question.user_id == user.id:
        raise AppError(403, "CANNOT_UPVOTE_OWN", "You cannot upvote your own question.")
    if question.status not in {"published", "answered"}:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    existing = await db.scalar(
        select(QuestionUpvote).where(QuestionUpvote.question_id == question.id, QuestionUpvote.user_id == user.id)
    )
    if enabled and existing is None:
        db.add(QuestionUpvote(question_id=question.id, user_id=user.id))
        question.upvote_count += 1
        try:
            await db.flush()
        except IntegrityError as exc:
            await db.rollback()
            raise AppError(409, "ALREADY_UPVOTED", "You have already upvoted this question.") from exc
    if not enabled and existing is not None:
        await db.delete(existing)
        question.upvote_count = max(0, question.upvote_count - 1)
    await db.commit()
    return {"upvoted": enabled and (existing is not None or enabled), "upvote_count": question.upvote_count}


async def answer_question(db: AsyncSession, question_id: str, user: User, text: str) -> dict:
    if user.role not in ANSWER_ROLES:
        raise AppError(403, "FORBIDDEN", "Only speakers and moderators can answer questions.")
    cleaned = text.strip()
    if len(cleaned) < 1 or len(cleaned) > 2000:
        raise AppError(422, "VALIDATION_ERROR", "Enter an answer up to 2000 characters.", [{"field": "answer_text", "message": "Enter an answer up to 2000 characters."}])
    question = await db.scalar(select(Question).options(selectinload(Question.category)).where(Question.id == question_id))
    if question is None or question.status in {"hidden", "rejected", "pending"}:
        raise AppError(404, "NOT_FOUND", "Question not found.")
    existing = await db.scalar(select(Answer).where(Answer.question_id == question.id))
    if existing is not None:
        raise AppError(409, "ALREADY_ANSWERED", "This question already has an answer.")
    if user.role == "speaker" and question.session_id:
        speaker = await db.scalar(select(Speaker).where(Speaker.user_id == user.id, Speaker.event_id == question.event_id))
        assigned = None
        if speaker is not None:
            assigned = await db.scalar(
                select(SessionSpeaker).where(SessionSpeaker.session_id == question.session_id, SessionSpeaker.speaker_id == speaker.id)
            )
        if assigned is None:
            raise AppError(403, "FORBIDDEN", "You can only answer questions for your own session.")
    db.add(Answer(question_id=question.id, author_user_id=user.id, answer_text=cleaned))
    question.status = "answered"
    question.updated_at = datetime.now(UTC)
    voter_ids = list((await db.scalars(select(QuestionUpvote.user_id).where(QuestionUpvote.question_id == question.id))).all())
    recipient_ids = {question.user_id, *voter_ids}
    recipients = list((await db.scalars(select(User).where(User.id.in_(recipient_ids)))).all())
    await notify_service.fanout(
        db,
        recipients,
        kind="qna",
        title="Your question was answered",
        body=f"{user.full_name} replied",
        deep_link=f"nmc://question/{question.id}",
        preference="qna",
    )
    await db.commit()
    card = await _card(db, question, user)
    await hub.broadcast({"type": "question.answered", "question": card})
    return card


async def today_sessions(db: AsyncSession) -> list[dict]:
    event = await get_current_event(db)
    from zoneinfo import ZoneInfo

    tz = ZoneInfo(event.timezone)
    today = datetime.now(UTC).astimezone(tz).date().isoformat()
    rows = (
        await db.scalars(
            select(Session).where(Session.event_id == event.id, Session.visibility == "published").order_by(Session.start_at)
        )
    ).all()
    chosen = [row for row in rows if _as_utc(row.start_at).astimezone(tz).date().isoformat() == today]
    return [{"id": row.id, "title": row.title} for row in chosen]
