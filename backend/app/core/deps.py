from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.models.entities import User

bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue.")
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        message = str(exc).lower()
        code = "TOKEN_EXPIRED" if "expired" in message else "UNAUTHORIZED"
        raise AppError(401, code, "Your session has expired. Please sign in again.") from exc
    user = await db.get(User, payload.get("sub"))
    if user is None or user.deleted_at is not None:
        raise AppError(401, "UNAUTHORIZED", "Sign in to continue.")
    if user.status == "suspended":
        raise AppError(403, "ACCOUNT_SUSPENDED", "This account is suspended.")
    return user


def require_roles(*roles: str):
    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise AppError(403, "FORBIDDEN", "You do not have access to this action.")
        return user

    return _checker


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        return None
    return await db.scalar(select(User).where(User.id == payload.get("sub"), User.deleted_at.is_(None)))
