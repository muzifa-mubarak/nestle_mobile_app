import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_builder import account_context, build_context, invalidate, known_ids
from app.ai.llm_client import LLMResult, generate, resolve_provider
from app.ai.prompt import build_system_prompt
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.rate_limit import limiter
from app.models.entities import AiConversation, AiMessage, Event, EventFaq, User
from app.services import congress_service

log = logging.getLogger("nmc.ai")
SUGGESTIONS = [
    "When is this congress, and how many sessions are there?",
    "How many sessions have I saved?",
    "How do I open my name tag?",
    "Where is the venue?",
]
FALLBACK = "The assistant is unavailable right now. Here are related results."


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _loads(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


async def suggestions() -> dict:
    return {"suggestions": SUGGESTIONS}


async def current_conversation(db: AsyncSession, user: User) -> dict:
    event = await congress_service.get_current_event(db)
    conversation = await _active(db, user.id, event.id)
    if conversation is None:
        return {"conversation_id": None, "messages": []}
    await _drop_expired(db, conversation.id)
    rows = (
        await db.scalars(select(AiMessage).where(AiMessage.conversation_id == conversation.id).order_by(AiMessage.created_at.desc()).limit(50))
    ).all()
    rows = list(reversed(rows))
    return {"conversation_id": conversation.id, "messages": [_message_payload(row) for row in rows]}


async def clear_conversation(db: AsyncSession, user: User) -> None:
    event = await congress_service.get_current_event(db)
    conversation = await _active(db, user.id, event.id)
    if conversation is not None:
        conversation.archived_at = datetime.now(UTC)
        await db.commit()


async def chat(db: AsyncSession, user: User, message: str, conversation_id: str | None) -> dict:
    settings = get_settings()
    if not settings.ai_enabled:
        raise AppError(503, "AI_DISABLED", "The assistant is not available right now.")
    cleaned = " ".join((message or "").split())
    if not cleaned or len(cleaned) > 500:
        raise AppError(422, "VALIDATION_ERROR", "Enter a question between 1 and 500 characters.")
    _limit(user.id, settings.ai_rate_limit_per_min, 60, "You're asking quickly. Try again in {n}s.")
    _limit(user.id, settings.ai_rate_limit_per_day, 86400, "You've reached today's assistant limit. Try again tomorrow.")
    event = await congress_service.get_current_event(db)
    conversation = await _conversation_for(db, user, event, conversation_id)
    history_rows = (
        await db.scalars(
            select(AiMessage)
            .where(AiMessage.conversation_id == conversation.id, AiMessage.status == "ok")
            .order_by(AiMessage.created_at.desc())
            .limit(settings.ai_history_messages)
        )
    ).all()
    history = [{"role": row.role, "content": row.content} for row in reversed(history_rows)]
    text, records = await build_context(db, event, settings.ai_context_ttl_seconds)
    known = known_ids(records)
    system = await _system_prompt(db, user, event, text, records)
    started = datetime.now(UTC)
    result = await generate(settings=settings, system=system, history=history, user_message=cleaned, records=records, known=known)
    if result.failed:
        result = await _fallback(db, event, user, cleaned, result.model)
    latency = int((datetime.now(UTC) - started).total_seconds() * 1000)
    user_row = AiMessage(conversation_id=conversation.id, role="user", content=cleaned, status="ok")
    assistant_row = AiMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=result.answer,
        references_json=json.dumps(result.references),
        followups_json=json.dumps(result.followups),
        status="ok" if not result.failed else "error",
        error_code="AI_UNAVAILABLE" if result.failed else None,
        model=result.model,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency,
    )
    db.add(user_row)
    db.add(assistant_row)
    conversation.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(assistant_row)
    log.info("ai chat user=%s chars=%s provider=%s latency_ms=%s", user.id, len(cleaned), resolve_provider(settings), latency)
    return {
        "conversation_id": conversation.id,
        "message_id": assistant_row.id,
        "answer": result.answer,
        "references": result.references,
        "followups": result.followups,
        "created_at": _iso(assistant_row.created_at),
    }


async def admin_test(db: AsyncSession, user: User, message: str) -> dict:
    settings = get_settings()
    if user.role not in {"organizer", "admin"}:
        raise AppError(403, "FORBIDDEN", "You do not have access to this action.")
    if not settings.ai_enabled:
        raise AppError(503, "AI_DISABLED", "The assistant is not available right now.")
    cleaned = " ".join((message or "").split())
    if not cleaned or len(cleaned) > 500:
        raise AppError(422, "VALIDATION_ERROR", "Enter a question between 1 and 500 characters.")
    event = await congress_service.get_current_event(db)
    text, records = await build_context(db, event, settings.ai_context_ttl_seconds)
    system = await _system_prompt(db, user, event, text, records)
    started = datetime.now(UTC)
    result = await generate(settings=settings, system=system, history=[], user_message=cleaned, records=records, known=known_ids(records))
    latency = int((datetime.now(UTC) - started).total_seconds() * 1000)
    return {
        "answer": result.answer,
        "references": result.references,
        "followups": result.followups,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "latency_ms": latency,
        "model": result.model,
    }


async def usage(db: AsyncSession) -> dict:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (await db.scalars(select(AiMessage).where(AiMessage.role == "assistant", AiMessage.created_at >= start))).all()
    conversations = {row.conversation_id for row in rows}
    latencies = [row.latency_ms for row in rows if row.latency_ms is not None]
    errors = [row for row in rows if row.status != "ok"]
    tokens = sum((row.input_tokens or 0) + (row.output_tokens or 0) for row in rows)
    return {
        "messages_today": len(rows),
        "unique_users": len(conversations),
        "average_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
        "error_rate": round(len(errors) / len(rows), 3) if rows else 0,
        "tokens_used": tokens,
    }


async def list_faqs(db: AsyncSession) -> dict:
    event = await congress_service.get_current_event(db)
    rows = (await db.scalars(select(EventFaq).where(EventFaq.event_id == event.id).order_by(EventFaq.display_order, EventFaq.created_at))).all()
    return {"faqs": [_faq_payload(row) for row in rows]}


async def create_faq(db: AsyncSession, user: User, question: str, answer: str, display_order: int, visibility: str) -> dict:
    event = await congress_service.get_current_event(db)
    row = EventFaq(
        event_id=event.id,
        question=question.strip()[:300],
        answer=answer.strip()[:1000],
        display_order=display_order,
        visibility=visibility if visibility in {"draft", "published"} else "published",
        created_by=user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    invalidate(event.id)
    return _faq_payload(row)


async def update_faq(db: AsyncSession, faq_id: str, fields: dict) -> dict:
    row = await db.get(EventFaq, faq_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "FAQ not found.")
    if "question" in fields and fields["question"]:
        row.question = str(fields["question"]).strip()[:300]
    if "answer" in fields and fields["answer"]:
        row.answer = str(fields["answer"]).strip()[:1000]
    if "display_order" in fields and fields["display_order"] is not None:
        row.display_order = int(fields["display_order"])
    if fields.get("visibility") in {"draft", "published"}:
        row.visibility = fields["visibility"]
    await db.commit()
    invalidate(row.event_id)
    return _faq_payload(row)


async def delete_faq(db: AsyncSession, faq_id: str) -> None:
    row = await db.get(EventFaq, faq_id)
    if row is None:
        raise AppError(404, "NOT_FOUND", "FAQ not found.")
    event_id = row.event_id
    await db.delete(row)
    await db.commit()
    invalidate(event_id)


async def _system_prompt(db: AsyncSession, user: User, event: Event, text: str, records: dict) -> str:
    account = await account_context(db, user, event, records)
    return build_system_prompt(
        event_title=event.title or event.name,
        city=event.city,
        country=event.country,
        timezone=event.timezone,
        now_local=records["event"]["now_local"],
        weekday=records["event"]["weekday"],
        event_context=text,
        account_context=account,
    )


def _limit(user_id: str, limit: int, window: int, template: str) -> None:
    key = f"ai:{window}:{user_id}"
    try:
        limiter.hit(key, limit, window)
    except AppError as exc:
        wait = exc.retry_after or limiter.retry_after(key, window)
        message = template.format(n=wait)
        error = AppError(429, "RATE_LIMITED", message)
        error.retry_after = wait
        raise error from exc


async def _fallback(db: AsyncSession, event: Event, user: User, message: str, model: str) -> LLMResult:
    found = await congress_service.search_sessions(db, event, message, user.id)
    references = []
    for row in (found.get("sessions") or [])[:3]:
        references.append({"type": "session", "id": row["id"], "label": row["title"]})
    for row in (found.get("speakers") or [])[: 3 - len(references)]:
        references.append({"type": "speaker", "id": row["id"], "label": row["name"]})
    if not references:
        raise AppError(503, "AI_UNAVAILABLE", "The assistant is unavailable right now. Please try again.")
    return LLMResult(answer=FALLBACK, references=references, followups=[], model=model, input_tokens=None, output_tokens=None, failed=False)


async def _active(db: AsyncSession, user_id: str, event_id: str) -> AiConversation | None:
    return await db.scalar(
        select(AiConversation)
        .where(AiConversation.user_id == user_id, AiConversation.event_id == event_id, AiConversation.archived_at.is_(None))
        .order_by(AiConversation.created_at.desc())
    )


async def _conversation_for(db: AsyncSession, user: User, event: Event, conversation_id: str | None) -> AiConversation:
    if conversation_id:
        row = await db.get(AiConversation, conversation_id)
        if row is None or row.user_id != user.id or row.archived_at is not None:
            raise AppError(404, "NOT_FOUND", "Conversation not found.")
        return row
    row = await _active(db, user.id, event.id)
    if row is None:
        row = AiConversation(user_id=user.id, event_id=event.id)
        db.add(row)
        await db.flush()
    return row


async def _drop_expired(db: AsyncSession, conversation_id: str) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    old = (
        await db.scalars(select(AiMessage).where(AiMessage.conversation_id == conversation_id, AiMessage.created_at < cutoff))
    ).all()
    for row in old:
        await db.delete(row)
    if old:
        await db.commit()


def _message_payload(row: AiMessage) -> dict:
    return {
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "references": _loads(row.references_json) if row.role == "assistant" else [],
        "followups": _loads(row.followups_json) if row.role == "assistant" else [],
        "created_at": _iso(row.created_at),
    }


def _faq_payload(row: EventFaq) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.answer,
        "display_order": row.display_order,
        "visibility": row.visibility,
    }
