from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_roles
from app.core.errors import ok
from app.models.entities import User
from app.services import admin_service, checkin_service
from app.services import notify as notify_service

router = APIRouter(prefix="/admin", tags=["admin"])
staff = require_roles("organizer", "admin")
desk = require_roles("organizer", "admin", "checkin_staff")


class SessionBody(BaseModel):
    title: str
    summary: str | None = None
    category_id: str
    start_at: str
    end_at: str
    room: str | None = None
    speaker_name: str | None = None
    visibility: str = "draft"


class PollBody(BaseModel):
    question: str
    label: str | None = None
    options: list[str] = Field(default_factory=list)
    results_visibility: str = "after_vote"


class StatusBody(BaseModel):
    status: str


class ModerateBody(BaseModel):
    action: str
    reason: str | None = None
    answer_text: str | None = None


class ResourceBody(BaseModel):
    title: str
    description: str | None = None
    type: str = "link"
    external_url: str | None = None


class VisibilityBody(BaseModel):
    visibility: str


class ModerationToggle(BaseModel):
    enabled: bool


class ExhibitorBody(BaseModel):
    name: str
    booth: str | None = None
    description: str | None = None
    website: str | None = None
    contact_email: str | None = None
    category_id: str | None = None
    visibility: str = "published"


class AnnouncementBody(BaseModel):
    title: str
    body: str
    deep_link: str | None = None
    audience: str = "all"


class CheckinBody(BaseModel):
    token: str


class ExhibitorPatch(BaseModel):
    name: str | None = None
    booth: str | None = None
    description: str | None = None
    website: str | None = None
    contact_email: str | None = None
    category_id: str | None = None
    visibility: str | None = None


@router.get("/overview")
async def overview(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.overview(db))


@router.patch("/moderation")
async def moderation(body: ModerationToggle, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.set_moderation(db, body.enabled))


@router.get("/sessions")
async def sessions(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_sessions(db))


@router.post("/sessions", status_code=201)
async def create_session(body: SessionBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.create_session(db, body.model_dump()))


@router.post("/sessions/{session_id}/{action}")
async def session_action(session_id: str, action: str, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.set_session_state(db, session_id, action))


@router.get("/polls")
async def polls(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_polls(db))


@router.post("/polls", status_code=201)
async def create_poll(body: PollBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.create_poll(db, body.model_dump()))


@router.post("/polls/{poll_id}/status")
async def poll_status(poll_id: str, body: StatusBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.set_poll_status(db, poll_id, body.status))


@router.get("/questions")
async def questions(status: str | None = Query(default=None), user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_questions(db, status))


@router.post("/questions/{question_id}/moderate")
async def moderate(question_id: str, body: ModerateBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.moderate_question(db, question_id, body.action, user, body.reason, body.answer_text))


@router.get("/resources")
async def resources(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_resources(db))


@router.post("/resources", status_code=201)
async def create_resource(body: ResourceBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.create_resource(db, user, body.model_dump()))


@router.post("/resources/{resource_id}/visibility")
async def resource_visibility(resource_id: str, body: VisibilityBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.set_resource_visibility(db, resource_id, body.visibility))


@router.get("/exhibitors")
async def exhibitors(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_exhibitors(db))


@router.post("/exhibitors", status_code=201)
async def create_exhibitor(body: ExhibitorBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.create_exhibitor(db, body.model_dump()))


@router.patch("/exhibitors/{exhibitor_id}")
async def update_exhibitor(exhibitor_id: str, body: ExhibitorPatch, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.update_exhibitor(db, exhibitor_id, body.model_dump(exclude_unset=True)))


@router.delete("/exhibitors/{exhibitor_id}")
async def delete_exhibitor(exhibitor_id: str, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.delete_exhibitor(db, exhibitor_id))


@router.post("/announcements", status_code=201)
async def announcement(body: AnnouncementBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await notify_service.send_announcement(db, body.title, body.body, body.deep_link, body.audience))


@router.get("/deliveries")
async def deliveries(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await notify_service.recent_deliveries(db))


@router.post("/checkin/verify")
async def checkin_verify(body: CheckinBody, user: User = Depends(desk), db: AsyncSession = Depends(get_db)):
    return ok(await checkin_service.verify(db, body.token))


@router.get("/checkin/lookup")
async def checkin_lookup(q: str = "", user: User = Depends(desk), db: AsyncSession = Depends(get_db)):
    return ok(await checkin_service.lookup(db, q))


@router.get("/checkin/stats")
async def checkin_stats(user: User = Depends(desk), db: AsyncSession = Depends(get_db)):
    return ok(await checkin_service.stats(db))


@router.get("/attendees")
async def attendees(user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.list_attendees(db))


@router.post("/attendees/{user_id}/status")
async def attendee_status(user_id: str, body: StatusBody, user: User = Depends(staff), db: AsyncSession = Depends(get_db)):
    return ok(await admin_service.set_attendee_status(db, user_id, body.status))
