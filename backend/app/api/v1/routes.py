from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from jwt import InvalidTokenError
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError, ok
from app.core.rate_limit import limiter
from app.core.realtime import hub
from app.core.security import decode_access_token
from app.models.entities import User
from app.schemas.auth import (
    EmailRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SocialRequest,
    VerifyEmailRequest,
)
from app.api.v1.admin import router as admin_router
from app.api.v1.ai import router as ai_router
from app.services import ai_service, auth_service, congress_service, notify as notify_service, profile_service, qna_service, resource_service, voting_service

router = APIRouter(prefix="/api/v1")
router.include_router(ai_router)
router.include_router(admin_router)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/app/config")
async def app_config(db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    event = None
    try:
        event = await congress_service.get_current_event(db)
    except AppError:
        event = None
    return ok(
        {
            "min_app_version": "1.0.0",
            "maintenance": False,
            "google_signin_enabled": bool(event.google_signin_enabled) if event else settings.feature_google_signin,
            "apple_signin_enabled": bool(event.apple_signin_enabled) if event else settings.feature_apple_signin,
        }
    )


@router.post("/auth/register", status_code=201)
async def register(body: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"register:{_client_ip(request)}", 5, 60)
    data = await auth_service.register_user(db, body.full_name, body.email, body.organization, body.password, body.accepted_terms)
    return ok(data)


@router.post("/auth/social")
async def social(body: SocialRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"social:{_client_ip(request)}", 10, 60)
    data = await auth_service.social_sign_in(db, body.provider, body.full_name, body.email, body.accepted_terms, body.device_info)
    return ok(data)


@router.post("/auth/verify-email")
async def verify_email(body: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"verify:{body.email.lower()}", 10, 60)
    return ok(await auth_service.verify_email(db, body.email, body.code, body.device_info))


@router.post("/auth/resend-verification")
async def resend(body: EmailRequest, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"resend:{body.email.lower()}", 5, 60)
    return ok(await auth_service.resend_verification(db, body.email))


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"login-ip:{_client_ip(request)}", 10, 60)
    limiter.hit(f"login-email:{body.email.lower()}", 5, 60)
    return ok(await auth_service.login(db, body.email, body.password, body.device_info))


@router.post("/auth/refresh")
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return ok(await auth_service.refresh(db, body.refresh_token))


@router.post("/auth/logout")
async def logout(body: LogoutRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, body.refresh_token, user)
    return ok({"logged_out": True})


@router.post("/auth/forgot-password")
async def forgot(body: EmailRequest, db: AsyncSession = Depends(get_db)):
    limiter.hit(f"forgot:{body.email.lower()}", 3, 60)
    return ok(await auth_service.forgot_password(db, body.email))


@router.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await auth_service.reset_password(db, body.email, body.code, body.new_password)
    return ok({"reset": True})


@router.get("/events/current")
async def current_event(db: AsyncSession = Depends(get_db)):
    event = await congress_service.get_current_event(db)
    return ok(congress_service.event_payload(event))


@router.get("/events/{event_id}/sessions/upcoming")
async def upcoming(event_id: str, limit: int = Query(default=5, ge=1, le=20), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok(await congress_service.upcoming_sessions(db, event, limit, user.id))


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=80), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await congress_service.get_current_event(db)
    return ok(await congress_service.search_sessions(db, event, q, user.id))


@router.get("/events/{event_id}/categories")
async def categories(event_id: str, type: str = Query(default="session"), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok({"categories": await congress_service.categories_for(db, event.id, type)})


@router.get("/events/{event_id}/agenda")
async def agenda(
    event_id: str,
    date: str | None = None,
    category_id: str | None = None,
    q: str | None = None,
    saved: bool = False,
    mine: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok(await congress_service.agenda(db, event, user.id, date, category_id, q, saved, mine))


@router.get("/events/{event_id}/exhibitors")
async def exhibitors(
    event_id: str,
    q: str | None = None,
    category_id: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok(await congress_service.list_exhibitors(db, event, q, category_id))


@router.get("/exhibitors/{exhibitor_id}")
async def exhibitor(exhibitor_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.get_exhibitor(db, exhibitor_id))


@router.get("/events/{event_id}/speakers")
async def speakers(
    event_id: str,
    q: str | None = None,
    category_id: str | None = None,
    featured: bool = False,
    country: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok(await congress_service.list_speakers(db, event, q, category_id, featured, country, cursor, limit))


@router.get("/speakers/{speaker_id}")
async def speaker(speaker_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.speaker_detail(db, speaker_id, user.id))


class VoteBody(BaseModel):
    option_ids: list[str]


class QuestionBody(BaseModel):
    text: str
    category_id: str
    session_id: str | None = None
    speaker_id: str | None = None


class AnswerBody(BaseModel):
    answer_text: str


@router.get("/events/{event_id}/venue")
async def venue(event_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    event = await congress_service.get_current_event(db)
    if event.id != event_id:
        raise AppError(404, "NOT_FOUND", "Event not found.")
    return ok(await congress_service.venue_payload(db, event))


@router.get("/polls/active")
async def active_polls(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await voting_service.active_polls(db, user))


@router.get("/polls/history")
async def poll_history(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await voting_service.poll_history(db, user))


@router.get("/polls/{poll_id}")
async def poll_detail(poll_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await voting_service.get_poll(db, poll_id, user))


@router.get("/polls/{poll_id}/results")
async def poll_results(poll_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    poll = await voting_service.get_poll(db, poll_id, user)
    if poll["total_votes"] is None:
        return ok({"results": None, "message": poll["results_message"]})
    return ok({"results": {"total_votes": poll["total_votes"], "options": poll["options"]}, "message": None})


@router.post("/polls/{poll_id}/votes", status_code=201)
async def cast_vote(
    poll_id: str,
    body: VoteBody,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    limiter.hit(f"vote:{user.id}", 30, 60)
    return ok(await voting_service.cast_vote(db, poll_id, user, body.option_ids, idempotency_key))


@router.websocket("/ws")
async def realtime(socket: WebSocket, token: str = ""):
    await socket.accept()
    try:
        decode_access_token(token)
    except InvalidTokenError:
        await socket.close(code=4401)
        return
    hub._clients.add(socket)
    try:
        while True:
            message = await socket.receive_json()
            if isinstance(message, dict) and message.get("type") == "ping":
                await socket.send_json({"type": "pong"})
            elif isinstance(message, dict) and message.get("type") == "subscribe":
                await socket.send_json({"type": "subscribed", "topics": message.get("topics") or []})
    except WebSocketDisconnect:
        hub.disconnect(socket)
    except Exception:
        hub.disconnect(socket)


@router.get("/questions")
async def questions(
    tab: str = Query(default="recent"),
    category_id: str | None = None,
    session_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if tab not in {"popular", "recent", "answered"}:
        raise AppError(422, "VALIDATION_ERROR", "Choose Popular, Recent, or Answered.")
    return ok(await qna_service.list_questions(db, user, tab, category_id, session_id, cursor, limit))


@router.get("/questions/mine")
async def my_questions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await qna_service.my_questions(db, user))


@router.get("/questions/sessions-today")
async def question_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok({"sessions": await qna_service.today_sessions(db)})


@router.post("/questions", status_code=201)
async def ask_question(body: QuestionBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    limiter.hit(f"question:{user.id}", 10, 60)
    return ok(await qna_service.ask_question(db, user, body.text, body.category_id, body.session_id, body.speaker_id))


@router.get("/questions/{question_id}")
async def question_detail(question_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await qna_service.get_question(db, question_id, user))


@router.put("/questions/{question_id}/upvote")
async def upvote(question_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await qna_service.set_upvote(db, question_id, user, True))


@router.delete("/questions/{question_id}/upvote")
async def remove_upvote(question_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await qna_service.set_upvote(db, question_id, user, False))


@router.post("/questions/{question_id}/answer", status_code=201)
async def answer(question_id: str, body: AnswerBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await qna_service.answer_question(db, question_id, user, body.answer_text))


@router.get("/resources")
async def resources(
    type: str | None = None,
    q: str | None = None,
    saved: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return ok(await resource_service.list_resources(db, user, type, q, saved, cursor, limit))


@router.get("/resources/{resource_id}")
async def resource_detail(resource_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await resource_service.get_resource(db, resource_id, user))


@router.get("/resources/{resource_id}/access")
async def resource_access(resource_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await resource_service.access_resource(db, resource_id, str(request.base_url)))


@router.get("/resources/{resource_id}/file")
async def resource_file(resource_id: str, exp: int, sig: str, db: AsyncSession = Depends(get_db)):
    resource, path = await resource_service.resource_file(db, resource_id, exp, sig)
    return FileResponse(path, media_type=resource.mime_type or "application/octet-stream", filename=path.name)


@router.get("/me/badge")
async def my_badge(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.badge_payload(db, user))


@router.get("/sessions/{session_id}")
async def session_detail(session_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.session_detail(db, session_id, user.id))


@router.put("/me/bookmarks/{target_type}/{target_id}")
async def add_bookmark(target_type: str, target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.set_bookmark(db, user.id, target_type, target_id, True))


@router.delete("/me/bookmarks/{target_type}/{target_id}")
async def remove_bookmark(target_type: str, target_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.set_bookmark(db, user.id, target_type, target_id, False))


class ProfileBody(BaseModel):
    full_name: str | None = None
    organization: str | None = None
    designation: str | None = None
    phone: str | None = None
    location: str | None = None
    notification_preferences: dict | None = None


class PasswordBody(BaseModel):
    current_password: str
    new_password: str


@router.get("/me")
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.profile_payload(db, user))


@router.patch("/me")
async def update_me(body: ProfileBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fields = body.model_dump(exclude_unset=True)
    return ok(await profile_service.update_profile(db, user, fields))


@router.post("/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    content = await file.read()
    return ok(await profile_service.save_avatar(db, user, content, file.content_type or ""))


@router.get("/me/avatar/{filename}")
async def avatar_file(filename: str):
    path = profile_service.avatar_path(filename)
    media = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(path.suffix.lstrip("."), "application/octet-stream")
    return FileResponse(path, media_type=media)


@router.patch("/me/password")
async def update_password(body: PasswordBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await profile_service.change_password(db, user, body.current_password, body.new_password))


@router.delete("/me")
async def delete_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await profile_service.request_deletion(db, user))


@router.get("/me/certificates")
async def my_certificates(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await profile_service.list_certificates(db, user))


@router.get("/me/certificates/{certificate_id}/access")
async def certificate_access(certificate_id: str, request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await profile_service.certificate_access(db, user, certificate_id, str(request.base_url)))


@router.get("/me/certificates/{certificate_id}/file")
async def certificate_file(certificate_id: str, exp: int, sig: str, db: AsyncSession = Depends(get_db)):
    row, path = await profile_service.certificate_file(db, certificate_id, exp, sig)
    return FileResponse(path, media_type="application/pdf", filename=f"{row.certificate_number}.pdf")


class DeviceTokenBody(BaseModel):
    token: str
    platform: str
    app_version: str | None = None


@router.put("/me/device-token")
async def device_token(body: DeviceTokenBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await notify_service.register_device(db, user, body.token, body.platform, body.app_version))


@router.get("/notifications")
async def notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.list_notifications(db, user.id))


@router.get("/notifications/unread-count")
async def unread(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok({"count": await congress_service.unread_count(db, user.id)})


@router.post("/notifications/read-all")
async def read_all_notifications(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.mark_all_notifications_read(db, user.id))


@router.patch("/notifications/{notification_id}")
async def read_notification(notification_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await congress_service.mark_notification_read(db, user.id, notification_id))


@router.get("/cms/faqs")
async def cms_faqs(db: AsyncSession = Depends(get_db)):
    data = await ai_service.list_faqs(db)
    published = [row for row in data["faqs"] if row["visibility"] == "published"]
    return ok({"faqs": published})


@router.get("/cms/{key}")
async def cms(key: str):
    pages = {
        "terms": {"title": "Congress terms", "body_markdown": "Attendees agree to use this app for congress information only."},
        "privacy": {
            "title": "Privacy policy",
            "body_markdown": (
                "We store your name, email, organization, and badge so you can attend the congress. "
                "Questions you send to the Congress Assistant are processed on our server to answer from published event information. "
                "Do not include medical details or personal data about other people in the chat."
            ),
        },
        "guidelines": {"title": "Attendee guidelines", "body_markdown": "Be respectful in polls and questions. Organizers may moderate submissions."},
    }
    page = pages.get(key)
    if page is None:
        raise AppError(404, "NOT_FOUND", "Page not found.")
    return ok(page)
