from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models.entities import Category, Event, Session, User
from tests.db import Session as TestSession


async def _event_with_session(*, start_offset_hours: int, end_offset_hours: int) -> str:
    now = datetime.now(UTC)
    async with TestSession() as db:
        event = Event(
            name="The Next Era of Nutrition & Health",
            title="NESTLÉ MEDICAL CONGRESS 2026",
            tagline="The Next Era of Nutrition & Health",
            start_at=now + timedelta(hours=start_offset_hours),
            end_at=now + timedelta(hours=end_offset_hours),
            timezone="Asia/Dubai",
            city="Dubai",
            country="United Arab Emirates",
            is_current=True,
        )
        db.add(event)
        await db.flush()
        category = Category(event_id=event.id, type="session", name="Keynote", slug="keynote", color="#F5B942")
        db.add(category)
        await db.flush()
        db.add(
            Session(
                event_id=event.id,
                category_id=category.id,
                title="Opening Ceremony",
                start_at=now + timedelta(hours=1),
                end_at=now + timedelta(hours=2),
                room="Main Auditorium",
                status="scheduled",
                visibility="published",
            )
        )
        await db.commit()
        return event.id


@pytest.mark.asyncio
async def test_register_duplicate_and_verify(client):
    await _event_with_session(start_offset_hours=24, end_offset_hours=72)
    payload = {
        "full_name": "Huda Latheef",
        "email": "New.User@Example.com",
        "organization": "Dubai Hospital",
        "password": "Str0ngPass!",
        "accepted_terms": True,
    }
    created = await client.post("/api/v1/auth/register", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["success"] is True
    assert body["data"]["email"] == "new.user@example.com"
    assert "dev_otp" not in body["data"]

    again = await client.post("/api/v1/auth/register", json=payload)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "EMAIL_EXISTS"

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "new.user@example.com"))
        from app.models.entities import EmailOtp

        otp = await db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id))
        assert otp is not None
        # Recreate the known code by replacing the hash through the service helper path:
        from app.core.security import sha256_hex

        otp.code_hash = sha256_hex("123456")
        await db.commit()

    verified = await client.post("/api/v1/auth/verify-email", json={"email": "new.user@example.com", "code": "123456"})
    assert verified.status_code == 200
    token = verified.json()["data"]["access_token"]
    me = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["data"]["full_name"] == "Huda Latheef"
    assert me.json()["data"]["badge_code"].startswith("NMC-")


@pytest.mark.asyncio
async def test_social_signup_google_and_apple(client):
    await _event_with_session(start_offset_hours=24, end_offset_hours=72)
    google = await client.post(
        "/api/v1/auth/social",
        json={"provider": "google", "full_name": "Sara Google", "email": "sara.congress@gmail.com", "accepted_terms": True},
    )
    assert google.status_code == 200
    assert google.json()["data"]["user"]["email"] == "sara.congress@gmail.com"
    assert google.json()["data"]["access_token"]

    again = await client.post(
        "/api/v1/auth/social",
        json={"provider": "google", "full_name": "Sara Google", "email": "sara.congress@gmail.com", "accepted_terms": True},
    )
    assert again.status_code == 200

    rejected = await client.post(
        "/api/v1/auth/social",
        json={"provider": "google", "full_name": "Sara Google", "email": "sara@example.com", "accepted_terms": True},
    )
    assert rejected.status_code == 422

    apple = await client.post(
        "/api/v1/auth/social",
        json={"provider": "apple", "full_name": "Omar Apple", "email": "omar@icloud.com", "accepted_terms": True},
    )
    assert apple.status_code == 200
    assert apple.json()["data"]["user"]["status"] == "active"

    taken = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Sara Google", "email": "sara.congress@gmail.com", "organization": "Clinic", "password": "Str0ngPass!", "accepted_terms": True},
    )
    assert taken.status_code == 409


@pytest.mark.asyncio
async def test_login_errors_and_refresh_reuse(client):
    await _event_with_session(start_offset_hours=-1, end_offset_hours=5)
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Layla Noor",
            "email": "layla@example.com",
            "organization": "City Clinic",
            "password": "Str0ngPass!",
            "accepted_terms": True,
        },
    )
    unverified = await client.post("/api/v1/auth/login", json={"email": "layla@example.com", "password": "Str0ngPass!"})
    assert unverified.status_code == 403
    assert unverified.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"

    wrong = await client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "Str0ngPass!"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == "layla@example.com"))
        user.status = "active"
        user.email_verified_at = datetime.now(UTC)
        from app.core.security import sha256_hex
        from app.models.entities import EmailOtp

        otp = await db.scalar(select(EmailOtp).where(EmailOtp.user_id == user.id))
        otp.code_hash = sha256_hex("000000")
        otp.consumed_at = datetime.now(UTC)
        await db.commit()

    logged = await client.post("/api/v1/auth/login", json={"email": "layla@example.com", "password": "Str0ngPass!"})
    assert logged.status_code == 200
    refresh = logged.json()["data"]["refresh_token"]
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert reused.status_code == 401
    newest = rotated.json()["data"]["refresh_token"]
    family_revoked = await client.post("/api/v1/auth/refresh", json={"refresh_token": newest})
    assert family_revoked.status_code == 401


@pytest.mark.asyncio
async def test_upcoming_sessions_follow_event_window(client):
    event_id = await _event_with_session(start_offset_hours=-2, end_offset_hours=6)
    async with TestSession() as db:
        user = User(
            email="huda@example.com",
            password_hash="x",
            full_name="Huda Latheef",
            organization="Dubai Hospital",
            status="active",
            terms_accepted_at=datetime.now(UTC),
        )
        from app.core.security import hash_password

        user.password_hash = hash_password("Passw0rd!")
        db.add(user)
        await db.commit()

    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    token = logged.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    current = await client.get("/api/v1/events/current")
    assert current.status_code == 200
    assert current.json()["data"]["city"] == "Dubai"
    upcoming = await client.get(f"/api/v1/events/{event_id}/sessions/upcoming", headers=headers)
    assert upcoming.status_code == 200
    assert upcoming.json()["data"]["sessions"][0]["title"] == "Opening Ceremony"
    assert upcoming.json()["data"]["sessions"][0]["room"] == "Main Auditorium"

    async with TestSession() as db:
        event = await db.get(Event, event_id)
        event.end_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()
    ended = await client.get(f"/api/v1/events/{event_id}/sessions/upcoming", headers=headers)
    assert ended.json()["data"]["empty_reason"] == "ended"
    assert "ended" in ended.json()["data"]["message"].lower() or "Thank you" in ended.json()["data"]["message"]


@pytest.mark.asyncio
async def test_agenda_filters_and_bookmarks(client):
    event_id = await _event_with_session(start_offset_hours=-1, end_offset_hours=8)
    async with TestSession() as db:
        from app.core.security import hash_password

        db.add(
            User(
                email="huda@example.com",
                password_hash=hash_password("Passw0rd!"),
                full_name="Huda Latheef",
                organization="Dubai Hospital",
                status="active",
                terms_accepted_at=datetime.now(UTC),
            )
        )
        await db.commit()
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    day = (datetime.now(UTC) + timedelta(hours=1)).astimezone(ZoneInfo("Asia/Dubai")).date().isoformat()
    agenda = await client.get(f"/api/v1/events/{event_id}/agenda", params={"date": day}, headers=headers)
    assert agenda.status_code == 200
    session = agenda.json()["data"]["sessions"][0]
    assert session["title"] == "Opening Ceremony"
    assert agenda.json()["data"]["weekday"]
    empty = await client.get(f"/api/v1/events/{event_id}/agenda", params={"date": day, "q": "missing"}, headers=headers)
    assert empty.json()["data"]["sessions"] == []
    saved = await client.put(f"/api/v1/me/bookmarks/session/{session['id']}", headers=headers)
    assert saved.json()["data"]["bookmarked"] is True
    again = await client.put(f"/api/v1/me/bookmarks/session/{session['id']}", headers=headers)
    assert again.status_code == 200
    only_saved = await client.get(f"/api/v1/events/{event_id}/agenda", params={"date": day, "saved": True}, headers=headers)
    assert len(only_saved.json()["data"]["sessions"]) == 1
    detail = await client.get(f"/api/v1/sessions/{session['id']}", headers=headers)
    assert detail.json()["data"]["is_bookmarked"] is True
    removed = await client.delete(f"/api/v1/me/bookmarks/session/{session['id']}", headers=headers)
    assert removed.json()["data"]["bookmarked"] is False
    me = await client.get("/api/v1/me", headers=headers)
    assert me.json()["data"]["counts"]["sessions"] == 0


@pytest.mark.asyncio
async def test_speakers_and_badge(client):
    from app.services.seed import enrich_existing, seed_if_empty

    async with TestSession() as db:
        await seed_if_empty(db)
        await enrich_existing(db)
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    current = (await client.get("/api/v1/events/current")).json()["data"]
    listed = await client.get(f"/api/v1/events/{current['id']}/speakers", headers=headers)
    assert listed.status_code == 200
    speakers = listed.json()["data"]["speakers"]
    assert speakers[0]["name"] == "Dr. Sarah Johnson"
    assert speakers[0]["is_featured"] is True
    assert speakers[0]["initials"] == "SJ"
    assert speakers[0]["session"]["title"] == "Future of Pediatric Nutrition"
    assert "United Kingdom" in listed.json()["data"]["countries"]
    featured = await client.get(f"/api/v1/events/{current['id']}/speakers", params={"featured": True}, headers=headers)
    assert [item["name"] for item in featured.json()["data"]["speakers"]] == ["Dr. Sarah Johnson"]
    pediatric = next(item for item in (await client.get(f"/api/v1/events/{current['id']}/categories", params={"type": "speaker"}, headers=headers)).json()["data"]["categories"] if item["slug"] == "pediatric")
    filtered = await client.get(f"/api/v1/events/{current['id']}/speakers", params={"category_id": pediatric["id"], "q": "sarah"}, headers=headers)
    assert [item["name"] for item in filtered.json()["data"]["speakers"]] == ["Dr. Sarah Johnson"]
    detail = await client.get(f"/api/v1/speakers/{speakers[0]['id']}", headers=headers)
    assert "nutrition" in detail.json()["data"]["biography"].lower()
    assert any(item["title"] == "Future of Pediatric Nutrition" for item in detail.json()["data"]["sessions"])
    missing = await client.get("/api/v1/me/badge")
    assert missing.status_code == 401
    badge = await client.get("/api/v1/me/badge", headers=headers)
    body = badge.json()["data"]
    assert body["badge_code"] == "NMC-2026-001"
    assert body["full_name"] == "Huda Latheef"
    assert body["designation"] == "Flutter Developer"
    assert body["attendee_type"] == "Attendee"
    assert body["location"] == "Dubai, UAE"
    assert body["event_dates_label"] == "22 - 23 May 2026"
    assert body["qr_payload"].startswith("nmc://badge/")
    assert body["status"] == "active"
    assert body["qr_modules"][0].startswith("0000")
    assert "1" in "".join(body["qr_modules"])


@pytest.mark.asyncio
async def test_venue_and_voting(client):
    from app.services.seed import enrich_existing, seed_if_empty

    async with TestSession() as db:
        await seed_if_empty(db)
        await enrich_existing(db)
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    event_id = (await client.get("/api/v1/events/current")).json()["data"]["id"]
    venue = await client.get(f"/api/v1/events/{event_id}/venue", headers=headers)
    assert venue.status_code == 200
    place = venue.json()["data"]
    assert place["name"] == "Dubai International Convention & Exhibition Center"
    assert place["address"] == "World Trade Centre, Dubai, United Arab Emirates"
    assert place["dates_label"] == "22 - 23 May 2026"
    assert place["latitude"] == 25.2285
    assert [item["label"] for item in place["facilities"]] == ["Free Wi-Fi", "Parking", "Catering", "Accessible"]
    active = await client.get("/api/v1/polls/active", headers=headers)
    polls = active.json()["data"]
    assert [item["question"] for item in polls] == [
        "How would you rate the current session?",
        "Which topic should the next session explore?",
    ]
    rating = polls[0]
    assert rating["has_voted"] is True
    assert rating["total_votes"] == 101
    assert sum(option["percent"] for option in rating["options"]) == 100
    assert rating["options"][0]["percent"] == 54
    assert rating["options"][1]["label"] == "Very Good"
    assert rating["options"][1]["id"] in rating["my_option_ids"]
    fresh = polls[1]
    assert fresh["has_voted"] is False
    assert fresh["options"][0]["percent"] is None
    option_id = fresh["options"][0]["id"]
    key = "vote-key-1"
    cast = await client.post(
        f"/api/v1/polls/{fresh['id']}/votes",
        headers={**headers, "Idempotency-Key": key},
        json={"option_ids": [option_id]},
    )
    assert cast.status_code == 201
    assert cast.json()["data"]["poll"]["has_voted"] is True
    assert sum(option["percent"] for option in cast.json()["data"]["poll"]["options"]) == 100
    again = await client.post(
        f"/api/v1/polls/{fresh['id']}/votes",
        headers={**headers, "Idempotency-Key": key},
        json={"option_ids": [option_id]},
    )
    assert again.status_code == 201
    duplicate = await client.post(
        f"/api/v1/polls/{fresh['id']}/votes",
        headers={**headers, "Idempotency-Key": "vote-key-2"},
        json={"option_ids": [option_id]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ALREADY_VOTED"
    closed = await client.post(
        f"/api/v1/polls/{rating['id']}/votes",
        headers=headers,
        json={"option_ids": [rating["options"][0]["id"]]},
    )
    assert closed.status_code == 409
    history = await client.get("/api/v1/polls/history", headers=headers)
    assert history.json()["data"][0]["status"] == "closed"
    assert history.json()["data"][0]["options"][0]["votes"] == 1


@pytest.mark.asyncio
async def test_questions(client):
    from app.core.security import hash_password
    from app.services.seed import enrich_existing, seed_if_empty

    async with TestSession() as db:
        await seed_if_empty(db)
        await enrich_existing(db)
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    recent = await client.get("/api/v1/questions", params={"tab": "recent"}, headers=headers)
    assert recent.status_code == 200
    first = recent.json()["data"]["questions"][0]
    assert first["text"].startswith("How can pediatric nutrition plans")
    assert first["status"] == "answered"
    assert first["upvote_count"] == 24
    assert first["category"]["name"] == "Nutrition"
    assert first["answer"]["author_name"] == "Dr. Ahmed"
    popular = await client.get("/api/v1/questions", params={"tab": "popular"}, headers=headers)
    assert popular.json()["data"]["questions"][0]["id"] == first["id"]
    answered = await client.get("/api/v1/questions", params={"tab": "answered"}, headers=headers)
    assert all(item["status"] == "answered" for item in answered.json()["data"]["questions"])
    categories = await client.get(f"/api/v1/events/{(await client.get('/api/v1/events/current')).json()['data']['id']}/categories", params={"type": "question"}, headers=headers)
    general = next(item for item in categories.json()["data"]["categories"] if item["slug"] == "general")
    short = await client.post("/api/v1/questions", headers=headers, json={"text": "Too short", "category_id": general["id"]})
    assert short.status_code == 422
    created = await client.post(
        "/api/v1/questions",
        headers=headers,
        json={"text": "Could the team explain how the panel chose these growth examples?", "category_id": general["id"]},
    )
    assert created.status_code == 201
    assert created.json()["data"]["status"] == "published"
    again = await client.get("/api/v1/questions", params={"tab": "recent"}, headers=headers)
    assert any(item["id"] == created.json()["data"]["id"] for item in again.json()["data"]["questions"])
    async with TestSession() as db:
        current = await db.scalar(select(Event).where(Event.is_current.is_(True)))
        current.qna_moderation_enabled = True
        await db.commit()
    held = await client.post(
        "/api/v1/questions",
        headers=headers,
        json={"text": "Could the team hold this question until a moderator reviews it?", "category_id": general["id"]},
    )
    assert held.status_code == 201
    assert held.json()["data"]["status"] == "pending"
    mine = await client.get("/api/v1/questions/mine", headers=headers)
    assert any(item["status"] == "pending" for item in mine.json()["data"]["questions"])
    own = await client.put(f"/api/v1/questions/{created.json()['data']['id']}/upvote", headers=headers)
    assert own.status_code == 403
    voted = await client.put(f"/api/v1/questions/{first['id']}/upvote", headers=headers)
    assert voted.json()["data"]["upvote_count"] == 25
    removed = await client.delete(f"/api/v1/questions/{first['id']}/upvote", headers=headers)
    assert removed.json()["data"]["upvote_count"] == 24
    forbidden = await client.post(f"/api/v1/questions/{first['id']}/answer", headers=headers, json={"answer_text": "Not allowed."})
    assert forbidden.status_code == 403
    async with TestSession() as db:
        db.add(
            User(
                email="moderator@example.com",
                password_hash=hash_password("Passw0rd!"),
                full_name="Moderator",
                organization="Congress",
                role="moderator",
                status="active",
                email_verified_at=datetime.now(UTC),
                terms_accepted_at=datetime.now(UTC),
            )
        )
        await db.commit()
    mod = await client.post("/api/v1/auth/login", json={"email": "moderator@example.com", "password": "Passw0rd!"})
    mod_headers = {"Authorization": f"Bearer {mod.json()['data']['access_token']}"}
    published = next(item for item in again.json()["data"]["questions"] if item["status"] == "published")
    reply = await client.post(f"/api/v1/questions/{published['id']}/answer", headers=mod_headers, json={"answer_text": "The opening notes are in the session detail."})
    assert reply.status_code == 201
    assert reply.json()["data"]["status"] == "answered"


@pytest.mark.asyncio
async def test_resources(client):
    from app.services.seed import enrich_existing, seed_if_empty

    async with TestSession() as db:
        await seed_if_empty(db)
        await enrich_existing(db)
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    listed = await client.get("/api/v1/resources", headers=headers)
    assert listed.status_code == 200
    titles = [item["title"] for item in listed.json()["data"]["resources"]]
    assert titles[:3] == ["Congress Scientific Program", "Pediatric Nutrition Guidelines", "Keynote Presentation Slides"]
    assert listed.json()["data"]["resources"][0]["file_size_label"] == "4.2 MB"
    assert listed.json()["data"]["resources"][2]["type"] == "slides"
    assert "Internal briefing notes" not in titles
    slides = await client.get("/api/v1/resources", params={"type": "slides"}, headers=headers)
    assert [item["title"] for item in slides.json()["data"]["resources"]] == ["Keynote Presentation Slides"]
    found = await client.get("/api/v1/resources", params={"q": "pediatric"}, headers=headers)
    assert found.json()["data"]["resources"][0]["file_size_label"] == "2.8 MB"
    target = listed.json()["data"]["resources"][0]["id"]
    await client.delete(f"/api/v1/me/bookmarks/resource/{target}", headers=headers)
    cleared = await client.get("/api/v1/resources", params={"saved": "true"}, headers=headers)
    assert all(item["id"] != target for item in cleared.json()["data"]["resources"])
    marked = await client.put(f"/api/v1/me/bookmarks/resource/{target}", headers=headers)
    assert marked.json()["data"]["bookmarked"] is True
    saved = await client.get("/api/v1/resources", params={"saved": "true"}, headers=headers)
    assert saved.json()["data"]["resources"][0]["is_bookmarked"] is True
    removed = await client.delete(f"/api/v1/me/bookmarks/resource/{target}", headers=headers)
    assert removed.json()["data"]["bookmarked"] is False
    access = await client.get(f"/api/v1/resources/{target}/access", headers=headers)
    assert access.status_code == 200
    assert access.json()["data"]["kind"] == "download"
    assert access.json()["data"]["expires_in"] == 300
    downloaded = await client.get(access.json()["data"]["url"].replace("http://test", ""))
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    hidden = next(item for item in (await client.get("/api/v1/resources", headers=headers)).json()["data"]["resources"] if item["type"] == "video")
    external = await client.get(f"/api/v1/resources/{hidden['id']}/access", headers=headers)
    assert external.json()["data"]["kind"] == "external"
    missing = await client.get("/api/v1/resources/missing/access", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RESOURCE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_profile(client):
    from app.services.seed import enrich_existing, seed_if_empty

    async with TestSession() as db:
        await seed_if_empty(db)
        await enrich_existing(db)
    logged = await client.post("/api/v1/auth/login", json={"email": "huda@example.com", "password": "Passw0rd!"})
    headers = {"Authorization": f"Bearer {logged.json()['data']['access_token']}"}
    me = await client.get("/api/v1/me", headers=headers)
    body = me.json()["data"]
    assert body["full_name"] == "Huda Latheef"
    assert body["attendee_type"] == "Medical Congress Attendee"
    assert body["phone_display"] == "+971 56 283 4212"
    assert body["location"] == "Dubai, UAE"
    assert body["badge_code"] == "NMC-2026-001"
    assert body["counts"] == {"sessions": 12, "saved": 5, "certificates": 3}
    bad = await client.patch("/api/v1/me", headers=headers, json={"phone": "0562834212"})
    assert bad.status_code == 422
    updated = await client.patch("/api/v1/me", headers=headers, json={"location": "Dubai, UAE", "designation": "Flutter Developer"})
    assert updated.json()["data"]["designation"] == "Flutter Developer"
    certs = await client.get("/api/v1/me/certificates", headers=headers)
    assert len(certs.json()["data"]["certificates"]) == 3
    assert certs.json()["data"]["certificates"][0]["certificate_number"].startswith("NMC-CERT-2026-")
    access = await client.get(f"/api/v1/me/certificates/{certs.json()['data']['certificates'][0]['id']}/access", headers=headers)
    downloaded = await client.get(access.json()["data"]["url"].replace("http://test", ""))
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    prefs = await client.patch("/api/v1/me", headers=headers, json={"notification_preferences": {"qna": False}})
    assert prefs.json()["data"]["notification_preferences"]["qna"] is False
