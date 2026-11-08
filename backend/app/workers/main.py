"""Background jobs. Run with Redis: arq app.workers.main.WorkerSettings"""

from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.services.notify import session_reminders


async def remind(_ctx: dict) -> int:
    async with SessionLocal() as session:
        return await session_reminders(session)


class WorkerSettings:
    functions = [remind]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379/0")
    cron_jobs = [cron(remind, second=0)]
