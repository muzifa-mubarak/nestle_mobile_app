from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


settings = get_settings()
engine = create_async_engine(settings.database_url, **_engine_kwargs(settings.database_url))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _add_missing_columns(sync_conn) -> None:
    from sqlalchemy import inspect, text

    inspector = inspect(sync_conn)
    if "sessions" not in inspector.get_table_names():
        return
    present = {column["name"] for column in inspector.get_columns("sessions")}
    if "description" not in present:
        sync_conn.execute(text("ALTER TABLE sessions ADD COLUMN description TEXT"))
    if "status_note" not in present:
        sync_conn.execute(text("ALTER TABLE sessions ADD COLUMN status_note VARCHAR(300)"))
    if "speakers" in inspector.get_table_names():
        speaker_columns = {column["name"] for column in inspector.get_columns("speakers")}
        additions = {
            "user_id": "VARCHAR(36)",
            "organization": "VARCHAR(160)",
            "biography": "TEXT",
            "photo_url": "TEXT",
            "is_featured": "BOOLEAN DEFAULT 0",
            "display_order": "INTEGER DEFAULT 0",
            "visibility": "VARCHAR(20) DEFAULT 'published'",
        }
        for name, ddl in additions.items():
            if name not in speaker_columns:
                sync_conn.execute(text(f"ALTER TABLE speakers ADD COLUMN {name} {ddl}"))
    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "notification_preferences" not in user_columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN notification_preferences TEXT"))
        if "auth_provider" not in user_columns:
            sync_conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(20)"))
    if "notifications" in inspector.get_table_names():
        note_columns = {column["name"] for column in inspector.get_columns("notifications")}
        if "push_status" not in note_columns:
            sync_conn.execute(text("ALTER TABLE notifications ADD COLUMN push_status VARCHAR(20) DEFAULT 'pending'"))
        if "attempts" not in note_columns:
            sync_conn.execute(text("ALTER TABLE notifications ADD COLUMN attempts INTEGER DEFAULT 0"))


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
