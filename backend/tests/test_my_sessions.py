from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.security import hash_password
from app.models.entities import Category, Event, Session, SessionSpeaker, Speaker, User
from tests.db import Session as TestSession


async def _speaker_day() -> tuple[str, str]:
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
        category = Category(event_id=event.id, type="session", name="Keynote", slug="keynote", display_order=1)
        db.add(category)
        await db.flush()
        opening = Session(
            event_id=event.id,
            category_id=category.id,
            title="Opening Ceremony",
            start_at=now + timedelta(hours=1),
            end_at=now + timedelta(hours=2),
            room="Main Auditorium",
            visibility="published",
            status="scheduled",
        )
        other = Session(
            event_id=event.id,
            category_id=category.id,
            title="Research Posters",
            start_at=now + timedelta(hours=3),
            end_at=now + timedelta(hours=4),
            room="Hall B",
            visibility="published",
            status="scheduled",
        )
        speaker_user = User(
            email="ahmed@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Dr. Ahmed",
            organization="Nestlé Medical Congress",
            role="speaker",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        attendee = User(
            email="huda@example.com",
            password_hash=hash_password("Passw0rd!"),
            full_name="Huda Latheef",
            organization="Dubai Hospital",
            role="attendee",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        db.add_all([opening, other, speaker_user, attendee])
        await db.flush()
        profile = Speaker(event_id=event.id, user_id=speaker_user.id, name="Dr. Ahmed", visibility="published")
        db.add(profile)
        await db.flush()
        db.add(SessionSpeaker(session_id=opening.id, speaker_id=profile.id))
        await db.commit()
        day = (now + timedelta(hours=1)).astimezone(ZoneInfo("Asia/Dubai")).date().isoformat()
        return event.id, day


async def _login(client, email: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": "Passw0rd!"})
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_speaker_my_sessions_filter(client):
    event_id, day = await _speaker_day()
    speaker = await _login(client, "ahmed@example.com")
    headers = {"Authorization": f"Bearer {speaker}"}
    full = await client.get(f"/api/v1/events/{event_id}/agenda", headers=headers, params={"date": day})
    assert full.json()["data"]["can_filter_mine"] is True
    assert len(full.json()["data"]["sessions"]) == 2
    mine = await client.get(f"/api/v1/events/{event_id}/agenda", headers=headers, params={"date": day, "mine": True})
    titles = [item["title"] for item in mine.json()["data"]["sessions"]]
    assert titles == ["Opening Ceremony"]
    assert mine.json()["data"]["heading"] == "My Sessions"

    attendee = await _login(client, "huda@example.com")
    hidden = await client.get(
        f"/api/v1/events/{event_id}/agenda",
        headers={"Authorization": f"Bearer {attendee}"},
        params={"date": day, "mine": True},
    )
    assert hidden.json()["data"]["sessions"] == []
    assert hidden.json()["data"]["can_filter_mine"] is False
