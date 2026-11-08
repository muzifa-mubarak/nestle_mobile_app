from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from tests.db import Session, engine
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.main import create_app
from app.models import entities  # noqa: F401

get_settings.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    limiter.reset()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async def override_db():
        async with Session() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
