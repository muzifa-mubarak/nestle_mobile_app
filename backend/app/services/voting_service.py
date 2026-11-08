import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.realtime import hub
from app.models.entities import Poll, PollOption, User, Vote, VoteIdempotency
from app.services.congress_service import _as_utc, get_current_event


def largest_remainder(counts: list[int]) -> list[int]:
    total = sum(counts)
    if total <= 0:
        return [0 for _ in counts]
    raw = [count * 100 / total for count in counts]
    floors = [int(value) for value in raw]
    leftover = 100 - sum(floors)
    order = sorted(range(len(counts)), key=lambda index: (raw[index] - floors[index], counts[index]), reverse=True)
    for index in order[:leftover]:
        floors[index] += 1
    return floors


def _status_at(poll: Poll, now: datetime) -> str:
    status = poll.status
    ended = poll.ends_at is not None and _as_utc(poll.ends_at) <= now
    started = poll.starts_at is None or _as_utc(poll.starts_at) <= now
    if status in {"active", "paused", "scheduled"} and ended:
        return "closed"
    if status == "scheduled" and started:
        return "active"
    return status


async def reconcile_polls(db: AsyncSession, polls: list[Poll]) -> None:
    now = datetime.now(UTC)
    changed = False
    for poll in polls:
        nxt = _status_at(poll, now)
        if nxt != poll.status:
            poll.status = nxt
            poll.updated_at = now
            changed = True
    if changed:
        await db.commit()


async def _options(db: AsyncSession, poll_id: str) -> list[PollOption]:
    return list(
        (await db.scalars(select(PollOption).where(PollOption.poll_id == poll_id).order_by(PollOption.display_order, PollOption.label))).all()
    )


async def _counts(db: AsyncSession, poll_id: str) -> tuple[dict[str, int], int]:
    rows = (
        await db.execute(select(Vote.option_id, func.count()).where(Vote.poll_id == poll_id).group_by(Vote.option_id))
    ).all()
    counts = {option_id: int(count) for option_id, count in rows}
    voters = await db.scalar(select(func.count(func.distinct(Vote.user_id))).where(Vote.poll_id == poll_id))
    return counts, int(voters or 0)


async def _my_options(db: AsyncSession, poll_id: str, user_id: str) -> list[str]:
    rows = await db.scalars(select(Vote.option_id).where(Vote.poll_id == poll_id, Vote.user_id == user_id))
    return list(rows.all())


def _results_visible(poll: Poll, has_voted: bool) -> bool:
    if poll.results_visibility == "live":
        return True
    if poll.results_visibility == "after_close":
        return poll.status == "closed"
    return has_voted


async def poll_payload(db: AsyncSession, poll: Poll, user_id: str) -> dict:
    options = await _options(db, poll.id)
    counts, total = await _counts(db, poll.id)
    mine = await _my_options(db, poll.id, user_id)
    visible = _results_visible(poll, bool(mine))
    percents = largest_remainder([counts.get(option.id, 0) for option in options]) if visible else []
    return {
        "id": poll.id,
        "label": poll.label,
        "question": poll.question,
        "status": poll.status,
        "type": poll.type,
        "max_choices": poll.max_choices,
        "results_visibility": poll.results_visibility,
        "has_voted": bool(mine),
        "my_option_ids": mine,
        "total_votes": total if visible else None,
        "closes_at": _as_utc(poll.ends_at).isoformat().replace("+00:00", "Z") if poll.ends_at else None,
        "results_message": None
        if visible
        else (
            "Results will be shown after the poll closes"
            if poll.results_visibility == "after_close"
            else "Results will be shown after you vote"
        ),
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "votes": counts.get(option.id, 0) if visible else None,
                "percent": percents[index] if visible else None,
            }
            for index, option in enumerate(options)
        ],
    }


async def _event_polls(db: AsyncSession) -> tuple[str, list[Poll]]:
    event = await get_current_event(db)
    polls = list((await db.scalars(select(Poll).where(Poll.event_id == event.id).order_by(Poll.display_order, Poll.created_at))).all())
    await reconcile_polls(db, polls)
    return event.id, polls


async def active_polls(db: AsyncSession, user: User) -> list[dict]:
    _, polls = await _event_polls(db)
    now = datetime.now(UTC)
    visible = []
    for poll in polls:
        if poll.status in {"active", "paused"}:
            visible.append(poll)
        elif poll.status == "closed" and poll.updated_at and _as_utc(poll.updated_at) >= now - timedelta(minutes=10):
            visible.append(poll)
    return [await poll_payload(db, poll, user.id) for poll in visible]


async def poll_history(db: AsyncSession, user: User) -> list[dict]:
    _, polls = await _event_polls(db)
    closed = [poll for poll in polls if poll.status == "closed"]
    return [await poll_payload(db, poll, user.id) for poll in closed]


async def get_poll(db: AsyncSession, poll_id: str, user: User) -> dict:
    poll = await db.get(Poll, poll_id)
    if poll is None:
        raise AppError(404, "NOT_FOUND", "Poll not found.")
    await reconcile_polls(db, [poll])
    return await poll_payload(db, poll, user.id)


async def cast_vote(db: AsyncSession, poll_id: str, user: User, option_ids: list[str], idempotency_key: str | None) -> dict:
    if idempotency_key:
        stored = await db.scalar(select(VoteIdempotency).where(VoteIdempotency.user_id == user.id, VoteIdempotency.key == idempotency_key))
        if stored is not None:
            return json.loads(stored.body)
    poll = await db.get(Poll, poll_id)
    if poll is None:
        raise AppError(404, "NOT_FOUND", "Poll not found.")
    await reconcile_polls(db, [poll])
    now = datetime.now(UTC)
    if poll.status == "closed" or (poll.ends_at and _as_utc(poll.ends_at) <= now):
        raise AppError(409, "POLL_CLOSED", "This poll is closed.")
    if poll.status != "active" or (poll.starts_at and _as_utc(poll.starts_at) > now):
        raise AppError(409, "POLL_NOT_ACTIVE", "This poll is not accepting votes.")
    chosen = list(dict.fromkeys(option_ids))
    if not chosen or len(chosen) > poll.max_choices or (poll.type == "single" and len(chosen) != 1):
        raise AppError(422, "TOO_MANY_CHOICES", "Select the allowed number of options.")
    options = {row.id: row for row in await _options(db, poll.id)}
    if any(option_id not in options for option_id in chosen):
        raise AppError(422, "INVALID_OPTION", "That option is not part of this poll.")
    existing = await _my_options(db, poll.id, user.id)
    if poll.type == "single" and existing:
        raise AppError(409, "ALREADY_VOTED", "You have already voted in this poll.")
    if existing and len(set(existing + chosen)) > poll.max_choices:
        raise AppError(422, "TOO_MANY_CHOICES", "Select the allowed number of options.")
    for option_id in chosen:
        if option_id in existing:
            continue
        db.add(Vote(poll_id=poll.id, option_id=option_id, user_id=user.id, idempotency_key=idempotency_key))
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(409, "ALREADY_VOTED", "You have already voted in this poll.") from exc
    payload = await poll_payload(db, poll, user.id)
    body = {"accepted": True, "has_voted": True, "results_visible": _results_visible(poll, True), "poll": payload}
    if idempotency_key:
        db.add(VoteIdempotency(user_id=user.id, key=idempotency_key[:80], body=json.dumps(body)))
    await db.commit()
    await hub.broadcast(
        {
            "type": "poll.results_updated",
            "poll_id": poll.id,
            "total_votes": payload["total_votes"],
            "options": [{"id": option["id"], "votes": option["votes"], "percent": option["percent"]} for option in payload["options"]],
        }
    )
    return body
