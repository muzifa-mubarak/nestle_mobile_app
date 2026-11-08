import hashlib
import hmac
import time
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_ROOT, get_settings
from app.core.errors import AppError
from app.models.entities import Bookmark, Resource, User
from app.services.congress_service import get_current_event

STORAGE = BACKEND_ROOT / "storage" / "resources"
TYPES = {"pdf", "slides", "video", "document", "link"}


def file_size_label(size: int | None) -> str:
    if not size:
        return ""
    megabytes = size / (1024 * 1024)
    if megabytes >= 1:
        text = f"{megabytes:.1f}".rstrip("0").rstrip(".")
        return f"{text} MB"
    kilobytes = max(size / 1024, 0.1)
    text = f"{kilobytes:.1f}".rstrip("0").rstrip(".")
    return f"{text} KB"


def _sign(resource_id: str, exp: int) -> str:
    raw = (get_settings().badge_token_enc_key or "nmc-local-badge-key").encode()
    return hmac.new(hashlib.sha256(raw).digest(), f"{resource_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def verify_download(resource_id: str, exp: int, signature: str) -> bool:
    if exp < int(time.time()):
        return False
    expected = _sign(resource_id, exp)
    return hmac.compare_digest(expected, signature)


def stored_path(resource: Resource) -> Path | None:
    if not resource.storage_key:
        return None
    path = (BACKEND_ROOT / "storage" / resource.storage_key).resolve()
    root = (BACKEND_ROOT / "storage").resolve()
    if root not in path.parents or not path.is_file():
        return None
    return path


async def _saved_ids(db: AsyncSession, user_id: str) -> set[str]:
    rows = await db.scalars(select(Bookmark.target_id).where(Bookmark.user_id == user_id, Bookmark.target_type == "resource"))
    return set(rows.all())


def _card(resource: Resource, saved: set[str]) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "description": resource.description or "",
        "type": resource.type,
        "file_size_bytes": resource.file_size,
        "file_size_label": file_size_label(resource.file_size),
        "is_bookmarked": resource.id in saved,
        "version": resource.version,
        "updated_at": resource.updated_at.isoformat().replace("+00:00", "Z") if resource.updated_at else None,
    }


async def list_resources(db: AsyncSession, user: User, resource_type: str | None, query: str | None, saved_only: bool, cursor: str | None, limit: int) -> dict:
    if resource_type and resource_type not in TYPES:
        raise AppError(422, "VALIDATION_ERROR", "Choose a resource type.")
    event = await get_current_event(db)
    try:
        offset = max(int(cursor or "0"), 0)
    except ValueError:
        offset = 0
    saved = await _saved_ids(db, user.id)
    stmt = select(Resource).where(Resource.event_id == event.id, Resource.visibility == "published", Resource.published_at.is_not(None))
    if resource_type:
        stmt = stmt.where(Resource.type == resource_type)
    if query and query.strip():
        needle = f"%{query.strip()}%"
        stmt = stmt.where(or_(Resource.title.ilike(needle), Resource.description.ilike(needle)))
    rows = list((await db.scalars(stmt.order_by(Resource.created_at.asc(), Resource.title.asc()))).all())
    if saved_only:
        rows = [row for row in rows if row.id in saved]
    page = rows[offset : offset + limit]
    next_offset = offset + limit
    return {
        "resources": [_card(row, saved) for row in page],
        "next_cursor": str(next_offset) if next_offset < len(rows) else None,
    }


async def get_resource(db: AsyncSession, resource_id: str, user: User) -> dict:
    event = await get_current_event(db)
    resource = await db.get(Resource, resource_id)
    if resource is None or resource.event_id != event.id or resource.visibility != "published" or resource.published_at is None:
        raise AppError(404, "NOT_FOUND", "Resource not found.")
    saved = await _saved_ids(db, user.id)
    return _card(resource, saved)


async def access_resource(db: AsyncSession, resource_id: str, base_url: str) -> dict:
    event = await get_current_event(db)
    resource = await db.get(Resource, resource_id)
    if resource is None or resource.event_id != event.id or resource.visibility != "published" or resource.published_at is None:
        raise AppError(404, "RESOURCE_UNAVAILABLE", "This resource is not available.")
    resource.download_count += 1
    await db.commit()
    if resource.external_url and resource.type in {"link", "video"}:
        return {"url": resource.external_url, "expires_in": 300, "kind": "external"}
    if resource.storage_key:
        from app.core.storage import presigned_url

        remote = presigned_url(resource.storage_key)
        if remote:
            return {"url": remote, "expires_in": 300, "kind": "download"}
    path = stored_path(resource)
    if path is None:
        raise AppError(404, "RESOURCE_UNAVAILABLE", "This resource is not available.")
    exp = int(time.time()) + 300
    signature = _sign(resource.id, exp)
    return {
        "url": f"{base_url.rstrip('/')}/api/v1/resources/{resource.id}/file?exp={exp}&sig={signature}",
        "expires_in": 300,
        "kind": "download",
    }


async def resource_file(db: AsyncSession, resource_id: str, exp: int, signature: str) -> tuple[Resource, Path]:
    if not verify_download(resource_id, exp, signature):
        raise AppError(403, "RESOURCE_UNAVAILABLE", "This download link has expired.")
    resource = await db.get(Resource, resource_id)
    path = stored_path(resource) if resource else None
    if resource is None or path is None:
        raise AppError(404, "RESOURCE_UNAVAILABLE", "This resource is not available.")
    return resource, path
