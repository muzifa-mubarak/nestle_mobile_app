from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_password
from app.models.entities import Category, Event, Exhibitor, Notification, User
from tests.db import Session as TestSession


async def _world() -> None:
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
        )
        db.add(event)
        await db.flush()
        category = Category(event_id=event.id, type="exhibitor", name="Nutrition", slug="nutrition", display_order=1)
        db.add(category)
        await db.flush()
        db.add(
            Exhibitor(
                event_id=event.id,
                category_id=category.id,
                name="Nestlé Health Science",
                booth="A12",
                description="Pediatric nutrition products.",
                website="https://example.com",
                visibility="published",
            )
        )
        db.add(Exhibitor(event_id=event.id, name="Hidden Booth", booth="Z9", visibility="draft"))
        user = User(
            email="huda@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Huda Latheef",
            organization="Dubai Hospital",
            role="attendee",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        db.add(user)
        await db.flush()
        db.add(
            Notification(
                user_id=user.id,
                type="event_update",
                title="Congress agenda published",
                body="Day 1 is ready.",
                deep_link="nmc://home",
            )
        )
        await db.commit()


async def _token(client) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_exhibitors_are_public_and_searchable(client):
    await _world()
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    event = await client.get("/api/v1/events/current")
    event_id = event.json()["data"]["id"]
    listed = await client.get(f"/api/v1/events/{event_id}/exhibitors", headers=headers)
    assert listed.status_code == 200
    names = [item["name"] for item in listed.json()["data"]["exhibitors"]]
    assert names == ["Nestlé Health Science"]
    exhibitor_id = listed.json()["data"]["exhibitors"][0]["id"]
    detail = await client.get(f"/api/v1/exhibitors/{exhibitor_id}", headers=headers)
    assert detail.json()["data"]["booth"] == "A12"
    found = await client.get("/api/v1/search", headers=headers, params={"q": "Health Science"})
    assert found.json()["data"]["exhibitors"][0]["name"] == "Nestlé Health Science"


@pytest.mark.asyncio
async def test_notification_inbox_marks_read(client):
    await _world()
    token = await _token(client)
    headers = {"Authorization": f"Bearer {token}"}
    inbox = await client.get("/api/v1/notifications", headers=headers)
    assert inbox.status_code == 200
    item = inbox.json()["data"]["notifications"][0]
    assert item["is_read"] is False
    assert inbox.json()["data"]["unread_count"] == 1
    marked = await client.patch(f"/api/v1/notifications/{item['id']}", headers=headers)
    assert marked.json()["data"]["unread_count"] == 0
    again = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert again.json()["data"]["unread_count"] == 0
