import hashlib
import hmac
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_ROOT, get_settings
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models.entities import Certificate, User
from app.services.congress_service import get_current_event, profile_payload

AVATARS = BACKEND_ROOT / "storage" / "avatars"
PHONE = re.compile(r"^\+[1-9]\d{7,14}$")
PREFS = ("event_updates", "session_reminders", "qna", "resources")
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _sign(certificate_id: str, exp: int) -> str:
    raw = (get_settings().badge_token_enc_key or "nmc-local-badge-key").encode()
    return hmac.new(hashlib.sha256(raw).digest(), f"cert:{certificate_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def _verify(certificate_id: str, exp: int, signature: str) -> bool:
    if exp < int(time.time()):
        return False
    return hmac.compare_digest(_sign(certificate_id, exp), signature)


async def update_profile(db: AsyncSession, user: User, fields: dict) -> dict:
    if "full_name" in fields:
        name = (fields["full_name"] or "").strip()
        if not 2 <= len(name) <= 100:
            raise AppError(422, "VALIDATION_ERROR", "Enter your full name.", [{"field": "full_name", "message": "Enter your full name."}])
        user.full_name = name
    if "organization" in fields:
        organization = (fields["organization"] or "").strip()
        if not 2 <= len(organization) <= 150:
            raise AppError(422, "VALIDATION_ERROR", "Enter your organization.", [{"field": "organization", "message": "Enter your organization."}])
        user.organization = organization
    if "designation" in fields:
        designation = (fields["designation"] or "").strip()
        if len(designation) > 120:
            raise AppError(422, "VALIDATION_ERROR", "Designation is too long.", [{"field": "designation", "message": "Designation is too long."}])
        user.designation = designation or None
    if "phone" in fields:
        phone = (fields["phone"] or "").strip().replace(" ", "")
        if phone and not PHONE.fullmatch(phone):
            raise AppError(422, "VALIDATION_ERROR", "Enter a phone number in international format, like +971562834212.", [{"field": "phone", "message": "Enter a phone number in international format."}])
        user.phone = phone or None
    if "location" in fields:
        location = (fields["location"] or "").strip()
        if len(location) > 120:
            raise AppError(422, "VALIDATION_ERROR", "Location is too long.", [{"field": "location", "message": "Location is too long."}])
        user.location = location or None
    if "notification_preferences" in fields and isinstance(fields["notification_preferences"], dict):
        current = json.loads(user.notification_preferences or "{}")
        for key in PREFS:
            if key in fields["notification_preferences"]:
                current[key] = bool(fields["notification_preferences"][key])
        user.notification_preferences = json.dumps(current)
    await db.commit()
    await db.refresh(user)
    return await profile_payload(db, user)


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> dict:
    if not user.password_hash or not verify_password(current_password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "Current password is incorrect.", [{"field": "current_password", "message": "Current password is incorrect."}])
    if not (8 <= len(new_password) <= 72) or not re.search(r"[A-Z]", new_password) or not re.search(r"[a-z]", new_password) or not re.search(r"\d", new_password):
        raise AppError(422, "VALIDATION_ERROR", "Use 8–72 characters with an uppercase letter, a lowercase letter, and a digit.", [{"field": "new_password", "message": "Use 8–72 characters with an uppercase letter, a lowercase letter, and a digit."}])
    user.password_hash = hash_password(new_password)
    await db.commit()
    return {"updated": True}


async def request_deletion(db: AsyncSession, user: User) -> dict:
    user.deleted_at = datetime.now(UTC)
    user.status = "deleted"
    await db.commit()
    return {"deleted": True}


async def save_avatar(db: AsyncSession, user: User, content: bytes, content_type: str) -> dict:
    extension = IMAGE_TYPES.get(content_type)
    if extension is None:
        raise AppError(422, "UNSUPPORTED_FORMAT", "Use a JPG, PNG, or WebP photo.")
    if not content or len(content) > 5 * 1024 * 1024:
        raise AppError(422, "VALIDATION_ERROR", "Photo must be 5 MB or smaller.")
    AVATARS.mkdir(parents=True, exist_ok=True)
    for old in AVATARS.glob(f"{user.id}.*"):
        old.unlink(missing_ok=True)
    (AVATARS / f"{user.id}.{extension}").write_bytes(content)
    user.avatar_url = f"/api/v1/me/avatar/{user.id}.{extension}"
    await db.commit()
    await db.refresh(user)
    return await profile_payload(db, user)


def avatar_path(filename: str) -> Path:
    if not re.fullmatch(r"[0-9a-f-]{36}\.(jpg|png|webp)", filename):
        raise AppError(404, "NOT_FOUND", "Photo not found.")
    path = (AVATARS / filename).resolve()
    if AVATARS.resolve() not in path.parents or not path.is_file():
        raise AppError(404, "NOT_FOUND", "Photo not found.")
    return path


async def list_certificates(db: AsyncSession, user: User) -> dict:
    event = await get_current_event(db)
    rows = (
        await db.scalars(
            select(Certificate)
            .where(Certificate.user_id == user.id, Certificate.status == "issued")
            .order_by(Certificate.issued_at.desc())
        )
    ).all()
    return {
        "certificates": [
            {
                "id": row.id,
                "event_name": event.title,
                "certificate_number": row.certificate_number,
                "issued_at": row.issued_at.isoformat().replace("+00:00", "Z") if row.issued_at else None,
                "status": row.status,
            }
            for row in rows
        ]
    }


async def certificate_access(db: AsyncSession, user: User, certificate_id: str, base_url: str) -> dict:
    row = await db.get(Certificate, certificate_id)
    if row is None or row.user_id != user.id or row.status != "issued":
        raise AppError(404, "NOT_FOUND", "Certificate not found.")
    path = (BACKEND_ROOT / "storage" / row.file_key).resolve()
    if not path.is_file():
        raise AppError(404, "NOT_FOUND", "Certificate file is not available.")
    exp = int(time.time()) + 300
    return {
        "url": f"{base_url.rstrip('/')}/api/v1/me/certificates/{row.id}/file?exp={exp}&sig={_sign(row.id, exp)}",
        "expires_in": 300,
        "kind": "download",
    }


async def certificate_file(db: AsyncSession, certificate_id: str, exp: int, signature: str) -> tuple[Certificate, Path]:
    if not _verify(certificate_id, exp, signature):
        raise AppError(403, "NOT_FOUND", "This download link has expired.")
    row = await db.get(Certificate, certificate_id)
    path = (BACKEND_ROOT / "storage" / row.file_key).resolve() if row else None
    if row is None or path is None or not path.is_file():
        raise AppError(404, "NOT_FOUND", "Certificate not found.")
    return row, path
