import os
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

_tmp = Path(tempfile.mkdtemp(prefix="nmc-test-"))
os.environ["APP_ENV"] = "test"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_tmp / 'test.db'}")
os.environ.setdefault("JWT_PRIVATE_KEY_PATH", str(_tmp / "jwt_private.pem"))
os.environ.setdefault("JWT_PUBLIC_KEY_PATH", str(_tmp / "jwt_public.pem"))

engine = create_async_engine(
    f"sqlite+aiosqlite:///{_tmp / 'test.db'}",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = async_sessionmaker(engine, expire_on_commit=False)
TMP_DIR = _tmp
