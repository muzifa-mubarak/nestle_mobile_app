import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.routes import router
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.errors import register_exception_handlers
from app.services.notify import session_reminders
from app.services.seed import enrich_existing, seed_if_empty

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("nmc")
ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DIR = ROOT / "preview"
ADMIN_DIR = ROOT / "admin_portal"
CHECKIN_DIR = ROOT / "checkin"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.app_env != "test":
        await init_db()
        async with SessionLocal() as session:
            await seed_if_empty(session)
            await enrich_existing(session)
        log.info("API ready at /api/v1  preview at /  admin at /admin/  check-in at /checkin/")
        if settings.redis_url:
            log.info("Reminders run in the worker because REDIS_URL is set.")
            yield
            return

        async def reminders() -> None:
            while True:
                await asyncio.sleep(60)
                try:
                    async with SessionLocal() as session:
                        await session_reminders(session)
                except Exception:
                    log.exception("Session reminder pass failed")

        task = asyncio.create_task(reminders())
        yield
        task.cancel()
        return
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Nestlé Medical Congress API", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        return await call_next(request)

    @app.get("/health/live")
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        return {"status": "ok"}

    app.include_router(router)

    if PREVIEW_DIR.exists():
        app.mount("/preview", StaticFiles(directory=PREVIEW_DIR, html=True), name="preview")

        @app.get("/")
        async def root():
            return FileResponse(PREVIEW_DIR / "index.html")

    if ADMIN_DIR.exists():
        app.mount("/admin", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")

    if CHECKIN_DIR.exists():
        app.mount("/checkin", StaticFiles(directory=CHECKIN_DIR, html=True), name="checkin")

    return app


app = create_app()
