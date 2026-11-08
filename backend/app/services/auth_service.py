import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    decrypt_token,
    encrypt_token,
    hash_password,
    new_otp_code,
    new_refresh_token,
    sha256_hex,
    verify_password,
)
from app.models.entities import Badge, EmailOtp, Event, RefreshToken, User

log = logging.getLogger("nmc.auth")
OTP_TTL = timedelta(minutes=15)
LOCK_AFTER = 10
LOCK_FOR = timedelta(minutes=15)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    shown = local[:1] if local else ""
    return f"{shown}***@{domain}"


async def _current_event(db: AsyncSession) -> Event | None:
    return await db.scalar(select(Event).where(Event.is_current.is_(True)))


async def _next_badge_code(db: AsyncSession, event: Event) -> str:
    year = _as_utc(event.start_at).year if event.start_at else datetime.now(UTC).year
    prefix = f"NMC-{year}-"
    count = await db.scalar(select(func.count()).select_from(Badge).where(Badge.event_id == event.id))
    return f"{prefix}{(count or 0) + 1:03d}"


async def _issue_badge(db: AsyncSession, user: User) -> Badge:
    existing = await db.scalar(select(Badge).where(Badge.user_id == user.id))
    if existing:
        return existing
    event = await _current_event(db)
    if event is None:
        raise AppError(503, "MAINTENANCE", "No active congress is configured yet.")
    token = secrets.token_urlsafe(32)
    badge = Badge(
        user_id=user.id,
        event_id=event.id,
        badge_code=await _next_badge_code(db, event),
        qr_token_hash=sha256_hex(token),
        qr_token_enc=encrypt_token(token),
    )
    db.add(badge)
    await db.flush()
    return badge


async def _store_otp(db: AsyncSession, user: User, purpose: str) -> str:
    code = new_otp_code()
    db.add(
        EmailOtp(
            user_id=user.id,
            purpose=purpose,
            code_hash=sha256_hex(code),
            expires_at=datetime.now(UTC) + OTP_TTL,
        )
    )
    await db.flush()
    log.info("OTP issued purpose=%s email=%s", purpose, mask_email(user.email))
    if get_settings().is_local:
        log.warning("LOCAL ONLY verification code for %s: %s", mask_email(user.email), code)
    return code


def _public_user(user: User, badge: Badge | None = None) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "organization": user.organization,
        "designation": user.designation,
        "attendee_type": user.attendee_type,
        "phone": user.phone,
        "location": user.location,
        "avatar_url": user.avatar_url,
        "badge_code": badge.badge_code if badge else None,
        "role": user.role,
        "status": user.status,
    }


async def _issue_tokens(db: AsyncSession, user: User, device_info: str | None, family_id: str | None = None) -> dict:
    settings = get_settings()
    refresh = new_refresh_token()
    family = family_id or str(__import__("uuid").uuid4())
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family,
            token_hash=sha256_hex(refresh),
            device_info=(device_info or "")[:200] or None,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    badge = await db.scalar(select(Badge).where(Badge.user_id == user.id))
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": refresh,
        "expires_in": settings.access_token_minutes * 60,
        "user": _public_user(user, badge),
    }


async def register_user(db: AsyncSession, full_name: str, email: str, organization: str, password: str, accepted_terms: bool) -> dict:
    if not accepted_terms:
        raise AppError(422, "VALIDATION_ERROR", "Please accept the terms to continue.", [{"field": "accepted_terms", "message": "Terms must be accepted."}])
    email = normalize_email(email)
    existing = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing:
        raise AppError(
            409,
            "EMAIL_EXISTS",
            "An account with this email already exists.",
            [{"field": "email", "message": "An account with this email already exists."}],
        )
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        organization=organization.strip(),
        role="attendee",
        status="pending_verification",
        auth_provider="password",
        terms_accepted_at=datetime.now(UTC),
    )
    db.add(user)
    await db.flush()
    await _issue_badge(db, user)
    code = await _store_otp(db, user, "verify_email")
    await db.commit()
    data = {"email": user.email, "masked_email": mask_email(user.email), "verification_required": True, "otp_expires_in": 900}
    if get_settings().is_local:
        data["dev_otp"] = code
        log.info("Verification code for %s: %s", user.email, code)
    return data


async def _latest_otp(db: AsyncSession, user_id: str, purpose: str) -> EmailOtp | None:
    return await db.scalar(
        select(EmailOtp)
        .where(EmailOtp.user_id == user_id, EmailOtp.purpose == purpose, EmailOtp.consumed_at.is_(None))
        .order_by(EmailOtp.created_at.desc())
    )


async def verify_email(db: AsyncSession, email: str, code: str, device_info: str | None = None) -> dict:
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        raise AppError(400, "INVALID_CODE", "That code is not valid.")
    otp = await _latest_otp(db, user.id, "verify_email")
    if otp is None:
        raise AppError(400, "INVALID_CODE", "That code is not valid.")
    if _as_utc(otp.expires_at) < datetime.now(UTC):
        raise AppError(400, "CODE_EXPIRED", "This code has expired. Request a new one.")
    if otp.attempts >= 5:
        raise AppError(400, "TOO_MANY_ATTEMPTS", "Too many attempts. Request a new code.")
    otp.attempts += 1
    if sha256_hex(code.strip()) != otp.code_hash:
        await db.commit()
        raise AppError(400, "INVALID_CODE", "That code is not valid.")
    otp.consumed_at = datetime.now(UTC)
    user.email_verified_at = datetime.now(UTC)
    user.status = "active"
    user.last_login_at = datetime.now(UTC)
    user.failed_login_count = 0
    tokens = await _issue_tokens(db, user, device_info)
    await db.commit()
    return tokens


_GOOGLE_DOMAINS = ("@gmail.com", "@googlemail.com")
_APPLE_DOMAINS = ("@icloud.com", "@me.com", "@mac.com", "@privaterelay.appleid.com")


async def social_sign_in(db: AsyncSession, provider: str, full_name: str, email: str, accepted_terms: bool, device_info: str | None) -> dict:
    if not accepted_terms:
        raise AppError(422, "VALIDATION_ERROR", "Please accept the terms to continue.", [{"field": "accepted_terms", "message": "Terms must be accepted."}])
    provider = provider.strip().lower()
    email = normalize_email(email)
    if provider == "google" and not email.endswith(_GOOGLE_DOMAINS):
        raise AppError(422, "VALIDATION_ERROR", "Use a Gmail address, like name@gmail.com.", [{"field": "email", "message": "Use a Gmail address."}])
    if provider == "apple" and not email.endswith(_APPLE_DOMAINS):
        raise AppError(422, "VALIDATION_ERROR", "Use the email on your Apple account (icloud.com, me.com, or mac.com).", [{"field": "email", "message": "Use an Apple account email."}])
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    now = datetime.now(UTC)
    if user is not None:
        if user.status == "suspended":
            raise AppError(403, "ACCOUNT_SUSPENDED", "This account is suspended.")
        if user.auth_provider != provider:
            raise AppError(409, "EMAIL_EXISTS", "This email already has an account. Sign in with your password.")
        user.status = "active"
        user.email_verified_at = user.email_verified_at or now
        user.last_login_at = now
        user.failed_login_count = 0
        user.locked_until = None
        tokens = await _issue_tokens(db, user, device_info)
        await db.commit()
        return tokens
    user = User(
        email=email,
        password_hash=None,
        full_name=full_name.strip(),
        organization="Google" if provider == "google" else "Apple",
        role="attendee",
        status="active",
        auth_provider=provider,
        email_verified_at=now,
        terms_accepted_at=now,
        last_login_at=now,
    )
    db.add(user)
    await db.flush()
    await _issue_badge(db, user)
    tokens = await _issue_tokens(db, user, device_info)
    await db.commit()
    return tokens


async def resend_verification(db: AsyncSession, email: str) -> dict:
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    data = {"sent": True, "masked_email": mask_email(email)}
    if user is None or user.status != "pending_verification":
        return data
    latest = await _latest_otp(db, user.id, "verify_email")
    if latest and _as_utc(latest.created_at) and datetime.now(UTC) - _as_utc(latest.created_at) < timedelta(seconds=60):
        raise AppError(429, "RATE_LIMITED", "Please wait before requesting another code.")
    code = await _store_otp(db, user, "verify_email")
    await db.commit()
    if get_settings().is_local:
        data["dev_otp"] = code
    return data


def _assert_login_allowed(user: User) -> None:
    locked = _as_utc(user.locked_until)
    if locked and locked > datetime.now(UTC):
        raise AppError(429, "RATE_LIMITED", "Too many sign-in attempts. Try again in a few minutes.")
    if user.status == "pending_verification":
        raise AppError(403, "EMAIL_NOT_VERIFIED", "Verify your email before signing in.")
    if user.status == "pending_approval":
        raise AppError(403, "ACCOUNT_PENDING_APPROVAL", "Your account is waiting for organizer approval.")
    if user.status == "suspended":
        raise AppError(403, "ACCOUNT_SUSPENDED", "This account is suspended.")
    if user.status != "active":
        raise AppError(403, "FORBIDDEN", "This account cannot sign in.")


async def login(db: AsyncSession, email: str, password: str, device_info: str | None) -> dict:
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= LOCK_AFTER:
                user.locked_until = datetime.now(UTC) + LOCK_FOR
            await db.commit()
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
    _assert_login_allowed(user)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    tokens = await _issue_tokens(db, user, device_info)
    await db.commit()
    return tokens


async def refresh(db: AsyncSession, refresh_token: str) -> dict:
    token_hash = sha256_hex(refresh_token)
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue.")
    if row.revoked_at is not None or row.replaced_by is not None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()
        raise AppError(401, "UNAUTHORIZED", "This session is no longer valid. Please sign in again.")
    if _as_utc(row.expires_at) < datetime.now(UTC):
        raise AppError(401, "TOKEN_EXPIRED", "Your session has expired. Please sign in again.")
    user = await db.get(User, row.user_id)
    if user is None or user.deleted_at is not None or user.status != "active":
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue.")
    tokens = await _issue_tokens(db, user, row.device_info, family_id=row.family_id)
    new_row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(tokens["refresh_token"])))
    row.replaced_by = new_row.id if new_row else None
    row.revoked_at = datetime.now(UTC)
    await db.commit()
    return tokens


async def logout(db: AsyncSession, refresh_token: str | None, user: User) -> None:
    if refresh_token:
        row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(refresh_token)))
        if row and row.user_id == user.id:
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.family_id == row.family_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
    else:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
    await db.commit()


async def forgot_password(db: AsyncSession, email: str) -> dict:
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None), User.status != "suspended"))
    message = "If this email exists, a code has been sent."
    data = {"message": message}
    if user is None:
        return data
    code = await _store_otp(db, user, "reset_password")
    await db.commit()
    if get_settings().is_local:
        data["dev_otp"] = code
    return data


async def reset_password(db: AsyncSession, email: str, code: str, new_password: str) -> None:
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None:
        raise AppError(400, "INVALID_CODE", "That code is not valid.")
    otp = await _latest_otp(db, user.id, "reset_password")
    if otp is None or _as_utc(otp.expires_at) < datetime.now(UTC):
        raise AppError(400, "CODE_EXPIRED" if otp else "INVALID_CODE", "That code is not valid.")
    otp.attempts += 1
    if otp.attempts > 5 or sha256_hex(code.strip()) != otp.code_hash:
        await db.commit()
        raise AppError(400, "INVALID_CODE", "That code is not valid.")
    otp.consumed_at = datetime.now(UTC)
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


def qr_payload_for(badge: Badge) -> str:
    return f"nmc://badge/{decrypt_token(badge.qr_token_enc)}"
