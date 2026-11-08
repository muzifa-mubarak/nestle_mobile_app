from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.entities import Category, Event, User
from tests.db import Session as TestSession


async def _staff_event() -> None:
    now = datetime.now(UTC)
    async with TestSession() as db:
        event = Event(
            name="The Next Era of Nutrition & Health",
            title="NESTLÉ MEDICAL CONGRESS 2026",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=2),
            timezone="Asia/Dubai",
            city="Dubai",
            country="United Arab Emirates",
            is_current=True,
            qna_moderation_enabled=True,
        )
        db.add(event)
        await db.flush()
        db.add(Category(event_id=event.id, type="session", name="Keynote", slug="keynote", display_order=1))
        db.add(Category(event_id=event.id, type="question", name="Clinical", slug="clinical", display_order=1))
        db.add(
            User(
                email="organizer@example.com",
                password_hash=hash_password("Passw0rd!"),
                full_name="Congress Organizer",
                organization="Nestlé Health Science",
                role="organizer",
                status="active",
                email_verified_at=now,
                terms_accepted_at=now,
            )
        )
        db.add(
            User(
                email="huda@example.com",
                password_hash=hash_password("Passw0rd!"),
                full_name="Huda Latheef",
                organization="Dubai Hospital",
                role="attendee",
                status="active",
                email_verified_at=now,
                terms_accepted_at=now,
            )
        )
        await db.commit()


async def _login(client, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_attendee_cannot_open_admin(client):
    await _staff_event()
    token = await _login(client, "huda@example.com")
    response = await client.get("/api/v1/admin/overview", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_organizer_manages_content(client):
    await _staff_event()
    token = await _login(client, "organizer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    overview = await client.get("/api/v1/admin/overview", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["data"]["counts"]["attendees"] == 1

    sessions = await client.get("/api/v1/admin/sessions", headers=headers)
    category_id = sessions.json()["data"]["categories"][0]["id"]
    start = datetime.now(UTC) + timedelta(hours=3)
    created = await client.post(
        "/api/v1/admin/sessions",
        headers=headers,
        json={
            "title": "Closing remarks",
            "category_id": category_id,
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
            "room": "Hall A",
            "visibility": "draft",
        },
    )
    assert created.status_code == 201
    session_id = created.json()["data"]["id"]
    published = await client.post(f"/api/v1/admin/sessions/{session_id}/publish", headers=headers)
    assert published.json()["data"]["visibility"] == "published"

    poll = await client.post(
        "/api/v1/admin/polls",
        headers=headers,
        json={"question": "Was this session useful?", "options": ["Yes", "No"]},
    )
    assert poll.status_code == 201
    activated = await client.post(
        f"/api/v1/admin/polls/{poll.json()['data']['id']}/status",
        headers=headers,
        json={"status": "active"},
    )
    assert activated.json()["data"]["status"] == "active"

    resource = await client.post(
        "/api/v1/admin/resources",
        headers=headers,
        json={"title": "Slides", "type": "link", "external_url": "https://example.com/slides"},
    )
    assert resource.status_code == 201
    visible = await client.post(
        f"/api/v1/admin/resources/{resource.json()['data']['id']}/visibility",
        headers=headers,
        json={"visibility": "published"},
    )
    assert visible.json()["data"]["visibility"] == "published"

    async with TestSession() as db:
        question_category = await db.scalar(select(Category).where(Category.type == "question"))
        question_category_id = question_category.id
    attendee_token = await _login(client, "huda@example.com")
    asked = await client.post(
        "/api/v1/questions",
        headers={"Authorization": f"Bearer {attendee_token}"},
        json={"text": "How long is the lunch break?", "category_id": question_category_id},
    )
    assert asked.status_code == 201
    assert asked.json()["data"]["status"] == "pending"
    approved = await client.post(
        f"/api/v1/admin/questions/{asked.json()['data']['id']}/moderate",
        headers=headers,
        json={"action": "approve"},
    )
    assert approved.json()["data"]["status"] == "published"

    attendees = await client.get("/api/v1/admin/attendees", headers=headers)
    attendee = attendees.json()["data"]["attendees"][0]
    suspended = await client.post(f"/api/v1/admin/attendees/{attendee['id']}/status", headers=headers, json={"status": "suspended"})
    assert suspended.json()["data"]["status"] == "suspended"
