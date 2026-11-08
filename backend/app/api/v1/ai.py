from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.errors import ok
from app.models.entities import User
from app.services import ai_service

router = APIRouter()


class ChatBody(BaseModel):
    conversation_id: str | None = None
    message: str = Field(default="")


class FaqBody(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    answer: str = Field(min_length=1, max_length=1000)
    display_order: int = 0
    visibility: str = "published"


class FaqPatch(BaseModel):
    question: str | None = None
    answer: str | None = None
    display_order: int | None = None
    visibility: str | None = None


@router.get("/ai/suggestions")
async def suggestions(user: User = Depends(get_current_user)):
    return ok(await ai_service.suggestions())


@router.get("/ai/conversations/current")
async def current(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.current_conversation(db, user))


@router.delete("/ai/conversations/current", status_code=204)
async def clear(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await ai_service.clear_conversation(db, user)
    return Response(status_code=204)


@router.post("/ai/chat")
async def chat(body: ChatBody, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.chat(db, user, body.message, body.conversation_id))


@router.get("/admin/faqs")
async def admin_faqs(user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.list_faqs(db))


@router.post("/admin/faqs", status_code=201)
async def create_faq(body: FaqBody, user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.create_faq(db, user, body.question, body.answer, body.display_order, body.visibility))


@router.patch("/admin/faqs/{faq_id}")
async def patch_faq(faq_id: str, body: FaqPatch, user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.update_faq(db, faq_id, body.model_dump(exclude_unset=True)))


@router.delete("/admin/faqs/{faq_id}", status_code=204)
async def remove_faq(faq_id: str, user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    await ai_service.delete_faq(db, faq_id)
    return Response(status_code=204)


@router.post("/admin/ai/test")
async def try_ai(body: ChatBody, user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.admin_test(db, user, body.message))


@router.get("/admin/ai/usage")
async def ai_usage(user: User = Depends(require_roles("organizer", "admin")), db: AsyncSession = Depends(get_db)):
    return ok(await ai_service.usage(db))
