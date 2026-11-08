"""Create tables and load the local congress seed."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, init_db
from app.services.seed import enrich_existing, seed_if_empty


async def main() -> None:
    await init_db()
    async with SessionLocal() as session:
        await seed_if_empty(session)
        await enrich_existing(session)


if __name__ == "__main__":
    asyncio.run(main())
