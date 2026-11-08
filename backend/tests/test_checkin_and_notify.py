from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import encrypt_token, hash_password, sha256_hex
from app.models.entities import Badge, Event, Notification, User
from tests.db import Session as TestSession


async def _people() -> None:
    now = datetime.now(UTC)
    async with TestSession() as db:
        event = Event(
            name="Congress",
            title="NESTLÉ MEDICAL CONGRESS 2026",
            start_at=now,
            end_at=now + timedelta(days=1),
            timezone="Asia/Dubai",
            city="Dubai",
            country="United Arab Emirates",
            is_current=True,
        )
        db.add(event)
        await db.flush()
        huda = User(
            email="huda@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Huda Latheef",
            organization="Dubai Hospital",
            role="attendee",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        desk = User(
            email="desk@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Registration Desk",
            organization="Nestlé Health Science",
            role="checkin_staff",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        organizer = User(
            email="organizer@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Congress Organizer",
            organization="Nestlé Health Science",
            role="organizer",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        db.add_all([huda, desk, organizer])
        await db.flush()
        token = "desk-scan-token"
        db.add(
            Badge(
                user_id=huda.id,
                event_id=event.id,
                badge_code="NMC-2026-001",
                qr_token_hash=sha256_hex(token),
                qr_token_enc=encrypt_token(token),
            )
        )
        await db.commit()


async def _login(client, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_staff_checks_in_a_badge(client):
    await _people()
    attendee = await _login(client, "huda@example.com")
    denied = await client.post("/api/v1/admin/checkin/verify", headers={"Authorization": f"Bearer {attendee}"}, json={"token": "NMC-2026-001"})
    assert denied.status_code == 403

    desk = await _login(client, "desk@example.com")
    headers = {"Authorization": f"Bearer {desk}"}
    invalid = await client.post("/api/v1/admin/checkin/verify", headers=headers, json={"token": "nope"})
    assert invalid.json()["data"]["result"] == "invalid"
    first = await client.post("/api/v1/admin/checkin/verify", headers=headers, json={"token": "nmc://badge/desk-scan-token"})
    assert first.json()["data"]["result"] == "valid"
    assert first.json()["data"]["badge_code"] == "NMC-2026-001"
    again = await client.post("/api/v1/admin/checkin/verify", headers=headers, json={"token": "NMC-2026-001"})
    assert again.json()["data"]["result"] == "already_checked_in"
    stats = await client.get("/api/v1/admin/checkin/stats", headers=headers)
    assert stats.json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_announcement_reaches_the_inbox(client):
    await _people()
    organizer = await _login(client, "organizer@example.com")
    sent = await client.post(
        "/api/v1/admin/announcements",
        headers={"Authorization": f"Bearer {organizer}"},
        json={"title": "Doors open", "body": "Registration is open at the main hall.", "audience": "all"},
    )
    assert sent.status_code == 201
    assert sent.json()["data"]["recipients"] == 1
    attendee = await _login(client, "huda@example.com")
    inbox = await client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {attendee}"})
    titles = [item["title"] for item in inbox.json()["data"]["notifications"]]
    assert "Doors open" in titles

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "huda@example.com"))
        user.notification_preferences = '{"event_updates": false}'
        await db.commit()
    again = await client.post(
        "/api/v1/admin/announcements",
        headers={"Authorization": f"Bearer {organizer}"},
        json={"title": "Quiet update", "body": "This one stays off.", "audience": "all"},
    )
    assert again.json()["data"]["recipients"] == 0
    rows = await client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {attendee}"})
    assert all(item["title"] != "Quiet update" for item in rows.json()["data"]["notifications"])


@pytest.mark.asyncio
async def test_device_token_registers(client):
    await _people()
    attendee = await _login(client, "huda@example.com")
    saved = await client.put(
        "/api/v1/me/device-token",
        headers={"Authorization": f"Bearer {attendee}"},
        json={"token": "device-token-demo-123", "platform": "android", "app_version": "1.0.0"},
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["registered"] is True
    async with TestSession() as db:
        note = await db.scalar(select(Notification))
        assert note is None
