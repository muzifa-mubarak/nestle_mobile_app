"""Staff badge scan for the registration desk."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import sha256_hex
from app.models.entities import Badge, User
from app.services.congress_service import _as_utc, get_current_event


def _token(raw: str) -> str:
    text = raw.strip()
    prefix = "nmc://badge/"
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


def _card(user: User, badge: Badge, result: str) -> dict:
    checked = _as_utc(badge.checked_in_at).isoformat().replace("+00:00", "Z") if badge.checked_in_at else None
    return {
        "result": result,
        "full_name": user.full_name,
        "organization": user.organization,
        "badge_code": badge.badge_code,
        "checked_in_at": checked,
    }


async def verify(db: AsyncSession, raw: str) -> dict:
    token = _token(raw)
    if not token:
        return {"result": "invalid"}
    badge = await db.scalar(select(Badge).where(Badge.qr_token_hash == sha256_hex(token)))
    if badge is None:
        badge = await db.scalar(select(Badge).where(Badge.badge_code == token))
    if badge is None:
        return {"result": "invalid"}
    user = await db.get(User, badge.user_id)
    if user is None or user.deleted_at is not None:
        return {"result": "invalid"}
    if user.status == "suspended":
        return _card(user, badge, "suspended")
    if badge.status == "revoked":
        return _card(user, badge, "revoked")
    if badge.checked_in_at is not None:
        return _card(user, badge, "already_checked_in")
    badge.checked_in_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(badge)
    return _card(user, badge, "valid")


async def lookup(db: AsyncSession, query: str) -> dict:
    term = f"%{query.strip().lower()}%"
    if not query.strip():
        return {"matches": []}
    rows = (
        await db.execute(
            select(User, Badge)
            .join(Badge, Badge.user_id == User.id)
            .where(
                User.deleted_at.is_(None),
                or_(User.full_name.ilike(term), User.email.ilike(term), Badge.badge_code.ilike(term)),
            )
            .limit(8)
        )
    ).all()
    return {
        "matches": [
            {
                "full_name": user.full_name,
                "organization": user.organization,
                "badge_code": badge.badge_code,
                "status": user.status,
                "checked_in_at": _as_utc(badge.checked_in_at).isoformat().replace("+00:00", "Z") if badge.checked_in_at else None,
            }
            for user, badge in rows
        ]
    }


async def stats(db: AsyncSession) -> dict:
    event = await get_current_event(db)
    tz = ZoneInfo(event.timezone or "Asia/Dubai")
    start = datetime.now(UTC).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
    badges = list((await db.scalars(select(Badge).where(Badge.event_id == event.id))).all())
    today = [row for row in badges if row.checked_in_at is not None and _as_utc(row.checked_in_at) >= start]
    total = [row for row in badges if row.checked_in_at is not None]
    return {"today": len(today), "total": len(total)}
