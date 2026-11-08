"""Dev seed based on PRD Appendix A, limited to the login, register, and home screens."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BACKEND_ROOT
from app.core.security import encrypt_token, hash_password, sha256_hex
from app.models.entities import (
    Badge,
    Category,
    Event,
    Notification,
    Poll,
    PollOption,
    Session,
    SessionSpeaker,
    Speaker,
    SpeakerCategory,
    User,
    Venue,
    VenueFacility,
    Vote,
    Question,
    QuestionUpvote,
    Answer,
    Resource,
    Bookmark,
    Certificate,
    EventFaq,
    Exhibitor,
)

DUBAI = ZoneInfo("Asia/Dubai")
DEV_PASSWORD = "Passw0rd!"


def _at(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=DUBAI).astimezone(UTC)


async def seed_if_empty(db: AsyncSession) -> None:
    existing = await db.scalar(select(func.count()).select_from(Event))
    if existing:
        return

    event = Event(
        name="The Next Era of Nutrition & Health",
        title="NESTLÉ MEDICAL CONGRESS 2026",
        tagline="The Next Era of Nutrition & Health",
        description="A two-day gathering of pediatric nutrition, research, and clinical leaders in Dubai.",
        start_at=_at(2026, 5, 22, 0, 0),
        end_at=_at(2026, 5, 23, 23, 59),
        timezone="Asia/Dubai",
        city="Dubai",
        country="United Arab Emirates",
        is_current=True,
        qna_moderation_enabled=False,
        google_signin_enabled=True,
        apple_signin_enabled=True,
    )
    db.add(event)
    await db.flush()

    categories = {
        "keynote": Category(event_id=event.id, type="session", name="Keynote", slug="keynote", color="#F5B942", display_order=1),
        "nutrition": Category(event_id=event.id, type="session", name="Nutrition", slug="nutrition", color="#2F6BFF", display_order=2),
        "research": Category(event_id=event.id, type="session", name="Research", slug="research", color="#7C5CFF", display_order=3),
    }
    db.add_all(categories.values())
    await db.flush()

    sessions = [
        ("Opening Ceremony", "keynote", _at(2026, 5, 22, 8, 30), _at(2026, 5, 22, 9, 30), "Main Auditorium", None, 1),
        ("Welcome & Introduction", "keynote", _at(2026, 5, 22, 9, 30), _at(2026, 5, 22, 10, 30), "Main Auditorium", "Dr. Hassan Ali", 2),
        ("Future of Pediatric Nutrition", "nutrition", _at(2026, 5, 22, 10, 30), _at(2026, 5, 22, 11, 30), "Hall B", "Dr. Sarah Johnson", 3),
        ("Research Poster Session", "research", _at(2026, 5, 23, 9, 0), _at(2026, 5, 23, 10, 30), "Poster Hall", "Dr. Ahmed Khalid", 1),
        ("Clinical Nutrition Panel", "nutrition", _at(2026, 5, 23, 11, 0), _at(2026, 5, 23, 12, 30), "Hall B", "Dr. Sarah Johnson", 2),
        ("Closing Remarks", "keynote", _at(2026, 5, 23, 16, 0), _at(2026, 5, 23, 17, 0), "Main Auditorium", "Dr. Ahmed", 3),
    ]
    for title, slug, start, end, room, speaker, order in sessions:
        db.add(
            Session(
                event_id=event.id,
                category_id=categories[slug].id,
                title=title,
                summary=title,
                start_at=start,
                end_at=end,
                room=room,
                speaker_name=speaker,
                status="scheduled",
                visibility="published",
                display_order=order,
            )
        )

    huda = User(
        email="huda@example.com",
        password_hash=hash_password(DEV_PASSWORD),
        full_name="Huda Latheef",
        organization="Dubai Hospital",
        designation="Flutter Developer",
        attendee_type="Medical Congress Attendee",
        phone="+971562834212",
        location="Dubai, UAE",
        role="attendee",
        status="active",
        email_verified_at=_at(2026, 5, 1, 9, 0),
        terms_accepted_at=_at(2026, 5, 1, 9, 0),
    )
    db.add(huda)
    await db.flush()
    token = "seed-badge-token-huda-latheef"
    db.add(
        Badge(
            user_id=huda.id,
            event_id=event.id,
            badge_code="NMC-2026-001",
            qr_token_hash=sha256_hex(token),
            qr_token_enc=encrypt_token(token),
        )
    )
    await _describe_sessions(db)
    db.add(
        Notification(
            user_id=huda.id,
            type="event_update",
            title="Congress agenda published",
            body="Day 1 and Day 2 sessions are now available in the app.",
            deep_link="nmc://session",
        )
    )
    await db.commit()


SESSION_COPY = {
    "Opening Ceremony": ("Official opening of the congress in the main auditorium.", "scheduled", None),
    "Welcome & Introduction": ("Programme overview and welcome from the clinical research team.", "scheduled", None),
    "Future of Pediatric Nutrition": ("How nutrition plans are changing for children with different growth patterns.", "scheduled", None),
    "Research Poster Session": ("Poster walk-through of current nutrition research.", "scheduled", None),
    "Clinical Nutrition Panel": ("Panel discussion with the featured speakers.", "changed", "Moved to Hall A."),
    "Closing Remarks": ("Closing of the congress.", "cancelled", "Combined with the afternoon panel."),
}


async def _describe_sessions(db: AsyncSession) -> None:
    rows = (await db.scalars(select(Session))).all()
    for row in rows:
        copy = SESSION_COPY.get(row.title)
        if copy is None:
            continue
        row.description, row.status, row.status_note = copy
        row.summary = copy[0][:300]


SPEAKERS = [
    {
        "name": "Dr. Sarah Johnson",
        "designation": "Pediatric Nutrition Specialist",
        "organization": "Royal Children's Nutrition Centre",
        "country": "United Kingdom",
        "biography": "Pediatric nutrition specialist focused on growth, feeding plans, and clinical care for children.",
        "is_featured": True,
        "display_order": 1,
        "categories": ["nutrition", "pediatric"],
        "sessions": ["Future of Pediatric Nutrition", "Clinical Nutrition Panel"],
    },
    {
        "name": "Dr. Hassan Ali",
        "designation": "Clinical Research Director",
        "organization": "Dubai Clinical Research Centre",
        "country": "UAE",
        "biography": "Clinical research director working on nutrition studies and the congress science programme.",
        "is_featured": False,
        "display_order": 2,
        "categories": ["research"],
        "sessions": ["Welcome & Introduction"],
    },
    {
        "name": "Dr. Ahmed Khalid",
        "designation": "Pediatric Research Lead",
        "organization": "Gulf Nutrition Institute",
        "country": "UAE",
        "biography": "Clinician presenting current pediatric nutrition research and the poster sessions.",
        "is_featured": False,
        "display_order": 3,
        "categories": ["nutrition"],
        "sessions": ["Research Poster Session"],
    },
    {
        "name": "Dr. Ahmed",
        "designation": "Session Moderator",
        "organization": "Nestlé Medical Congress",
        "country": "UAE",
        "biography": "Host and moderator for the opening and closing of the congress.",
        "is_featured": False,
        "display_order": 4,
        "categories": ["research"],
        "sessions": ["Opening Ceremony", "Closing Remarks"],
    },
]


async def _ensure_speakers(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    huda = await db.scalar(select(User).where(User.email == "huda@example.com"))
    if huda is not None and huda.attendee_type in {"", "Attendee"}:
        huda.attendee_type = "Medical Congress Attendee"
    speaker_categories = {
        "nutrition": ("Nutrition", "#2F6BFF", 1),
        "research": ("Research", "#7C5CFF", 2),
        "pediatric": ("Pediatric", "#4FC3F7", 3),
    }
    existing_categories = {
        row.slug: row
        for row in (await db.scalars(select(Category).where(Category.event_id == event.id, Category.type == "speaker"))).all()
    }
    for slug, (name, color, order) in speaker_categories.items():
        if slug not in existing_categories:
            row = Category(event_id=event.id, type="speaker", name=name, slug=slug, color=color, display_order=order)
            db.add(row)
            existing_categories[slug] = row
    await db.flush()
    already = await db.scalar(select(func.count()).select_from(Speaker).where(Speaker.event_id == event.id))
    if already:
        return
    sessions = {row.title: row for row in (await db.scalars(select(Session).where(Session.event_id == event.id))).all()}
    for item in SPEAKERS:
        speaker = Speaker(
            event_id=event.id,
            name=item["name"],
            designation=item["designation"],
            organization=item["organization"],
            country=item["country"],
            biography=item["biography"],
            is_featured=item["is_featured"],
            display_order=item["display_order"],
            visibility="published",
        )
        db.add(speaker)
        await db.flush()
        for slug in item["categories"]:
            db.add(SpeakerCategory(speaker_id=speaker.id, category_id=existing_categories[slug].id))
        for index, title in enumerate(item["sessions"]):
            session = sessions.get(title)
            if session is None:
                continue
            db.add(SessionSpeaker(session_id=session.id, speaker_id=speaker.id, display_order=index))
            if not session.speaker_name:
                session.speaker_name = speaker.name


async def _ensure_venue_and_polls(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    venue = await db.scalar(select(Venue).where(Venue.event_id == event.id))
    if venue is None:
        venue = Venue(
            event_id=event.id,
            name="Dubai International Convention & Exhibition Center",
            address="World Trade Centre, Dubai, United Arab Emirates",
            latitude=25.2285,
            longitude=55.2867,
            notices="[]",
        )
        db.add(venue)
        await db.flush()
        for order, key, label, icon in (
            (1, "wifi", "Free Wi-Fi", "wifi"),
            (2, "parking", "Parking", "parking"),
            (3, "catering", "Catering", "catering"),
            (4, "accessible", "Accessible", "accessible"),
        ):
            db.add(VenueFacility(venue_id=venue.id, key=key, label=label, icon=icon, enabled=True, display_order=order))
    existing_polls = await db.scalar(select(func.count()).select_from(Poll).where(Poll.event_id == event.id))
    if existing_polls:
        return
    rating = Poll(
        event_id=event.id,
        question="How would you rate the current session?",
        label="Audience Feedback",
        type="single",
        max_choices=1,
        status="active",
        results_visibility="after_vote",
        display_order=1,
    )
    follow = Poll(
        event_id=event.id,
        question="Which topic should the next session explore?",
        label="Audience Feedback",
        type="single",
        max_choices=1,
        status="active",
        results_visibility="after_vote",
        display_order=2,
    )
    closed = Poll(
        event_id=event.id,
        question="Did the opening session meet your expectations?",
        label="Audience Feedback",
        type="single",
        max_choices=1,
        status="closed",
        results_visibility="after_close",
        display_order=3,
        ends_at=_at(2026, 5, 22, 9, 0),
        updated_at=_at(2026, 5, 22, 9, 0),
    )
    db.add_all([rating, follow, closed])
    await db.flush()
    rating_labels = [("Excellent", 55), ("Very Good", 31), ("Good", 10), ("Fair", 3), ("Poor", 2)]
    rating_options = []
    for index, (label, _count) in enumerate(rating_labels, start=1):
        option = PollOption(poll_id=rating.id, label=label, display_order=index)
        db.add(option)
        rating_options.append(option)
    for index, label in enumerate(("Nutrition", "Research", "Clinical"), start=1):
        db.add(PollOption(poll_id=follow.id, label=label, display_order=index))
    yes = PollOption(poll_id=closed.id, label="Yes", display_order=1)
    no = PollOption(poll_id=closed.id, label="No", display_order=2)
    db.add_all([yes, no])
    await db.flush()
    huda = await db.scalar(select(User).where(User.email == "huda@example.com"))
    very_good = next(option for option in rating_options if option.label == "Very Good")
    pending: list[tuple[User, PollOption]] = []
    cursor = 0
    for option, count in zip(rating_options, [count for _label, count in rating_labels], strict=True):
        seats = count - (1 if option is very_good else 0)
        for offset in range(seats):
            voter = User(
                email=f"seed-voter-{cursor + offset}@example.com",
                full_name=f"Seed Voter {cursor + offset}",
                organization="Congress",
                status="active",
                terms_accepted_at=_at(2026, 5, 1, 9, 0),
            )
            db.add(voter)
            pending.append((voter, option))
        cursor += seats
    await db.flush()
    for voter, option in pending:
        db.add(Vote(poll_id=rating.id, option_id=option.id, user_id=voter.id))
    if huda is not None:
        db.add(Vote(poll_id=rating.id, option_id=very_good.id, user_id=huda.id))
        db.add(Vote(poll_id=closed.id, option_id=yes.id, user_id=huda.id))


async def _ensure_questions(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    existing = await db.scalar(select(func.count()).select_from(Question).where(Question.event_id == event.id))
    if existing:
        return
    names = [("general", "General", 1), ("nutrition", "Nutrition", 2), ("research", "Research", 3), ("clinical", "Clinical", 4)]
    categories = {
        row.slug: row
        for row in (await db.scalars(select(Category).where(Category.event_id == event.id, Category.type == "question"))).all()
    }
    for slug, name, order in names:
        if slug not in categories:
            row = Category(event_id=event.id, type="question", name=name, slug=slug, display_order=order)
            db.add(row)
            categories[slug] = row
    await db.flush()
    ahmed = await db.scalar(select(User).where(User.email == "ahmed@example.com"))
    if ahmed is None:
        ahmed = User(
            email="ahmed@example.com",
            password_hash=hash_password(DEV_PASSWORD),
            full_name="Dr. Ahmed",
            organization="Nestlé Medical Congress",
            designation="Session Moderator",
            role="speaker",
            status="active",
            email_verified_at=_at(2026, 5, 1, 9, 0),
            terms_accepted_at=_at(2026, 5, 1, 9, 0),
        )
        db.add(ahmed)
        await db.flush()
    speaker = await db.scalar(select(Speaker).where(Speaker.event_id == event.id, Speaker.name == "Dr. Ahmed"))
    if speaker is not None and speaker.user_id is None:
        speaker.user_id = ahmed.id
    voters = list((await db.scalars(select(User).where(User.email.like("seed-voter-%")).limit(30))).all())
    author = voters[0] if voters else ahmed
    featured = Question(
        event_id=event.id,
        user_id=author.id,
        category_id=categories["nutrition"].id,
        text="How can pediatric nutrition plans be personalized for children with different growth patterns?",
        status="answered",
        upvote_count=0,
        created_at=_at(2026, 5, 22, 12, 0),
    )
    others = [
        ("What evidence supports early nutrition screening in clinics?", "research", "published", _at(2026, 5, 22, 10, 0)),
        ("Can you share the practical steps from the opening session?", "general", "published", _at(2026, 5, 22, 10, 30)),
        ("Which growth charts should we use for mixed feeding?", "clinical", "published", _at(2026, 5, 22, 11, 0)),
    ]
    db.add(featured)
    await db.flush()
    db.add(
        Answer(
            question_id=featured.id,
            author_user_id=ahmed.id,
            answer_text="Review the growth chart with the feeding history, then adjust the plan for that child's pattern.",
            created_at=_at(2026, 5, 22, 12, 20),
        )
    )
    upvoters = [voter for voter in voters if voter.id != author.id][:24]
    featured.upvote_count = len(upvoters)
    for voter in upvoters:
        db.add(QuestionUpvote(question_id=featured.id, user_id=voter.id))
    for text, slug, status, created in others:
        db.add(
            Question(
                event_id=event.id,
                user_id=author.id,
                category_id=categories[slug].id,
                text=text,
                status=status,
                created_at=created,
            )
        )
    huda = await db.scalar(select(User).where(User.email == "huda@example.com"))
    if huda is not None:
        db.add(
            Question(
                event_id=event.id,
                user_id=huda.id,
                category_id=categories["general"].id,
                text="Could the slides from the nutrition session be shared after the talk?",
                status="pending",
                created_at=_at(2026, 5, 22, 13, 0),
            )
        )
    if len(voters) > 1:
        db.add(
            Question(
                event_id=event.id,
                user_id=voters[1].id,
                category_id=categories["research"].id,
                text="This draft question is waiting for the moderator to approve it.",
                status="pending",
                created_at=_at(2026, 5, 22, 13, 10),
            )
        )


def _placeholder(resource_id: str, kind: str) -> str:
    from app.core.config import BACKEND_ROOT

    folder = BACKEND_ROOT / "storage" / "resources"
    folder.mkdir(parents=True, exist_ok=True)
    suffix = "pdf" if kind == "pdf" else "pptx"
    path = folder / f"{resource_id}.{suffix}"
    if kind == "pdf":
        path.write_bytes(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
    else:
        path.write_bytes(b"PK\x03\x04nmc-slides")
    return f"resources/{resource_id}.{suffix}"


async def _ensure_resources(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    existing = await db.scalar(select(func.count()).select_from(Resource).where(Resource.event_id == event.id))
    if existing:
        return
    owner = await db.scalar(select(User).where(User.email == "huda@example.com"))
    items = [
        ("Congress Scientific Program", "Complete schedule and session details", "pdf", int(4.2 * 1024 * 1024), "application/pdf", _at(2026, 5, 20, 9, 0)),
        ("Pediatric Nutrition Guidelines", "Clinical reference material", "pdf", int(2.8 * 1024 * 1024), "application/pdf", _at(2026, 5, 20, 9, 1)),
        ("Keynote Presentation Slides", "The Next Era of Nutrition & Health", "slides", int(8.6 * 1024 * 1024), "application/vnd.openxmlformats-officedocument.presentationml.presentation", _at(2026, 5, 20, 9, 2)),
        ("Opening Session Recording", "Watch the opening session", "video", None, "video/mp4", _at(2026, 5, 20, 9, 3)),
        ("Internal briefing notes", "Unpublished organizer draft", "pdf", 120000, "application/pdf", None),
    ]
    for title, description, kind, size, mime, published_at in items:
        row = Resource(
            event_id=event.id,
            title=title,
            description=description,
            type=kind,
            mime_type=mime,
            file_size=size,
            version=1,
            visibility="published" if published_at else "draft",
            published_at=published_at,
            created_by=owner.id if owner else None,
            created_at=published_at or _at(2026, 5, 20, 10, 0),
        )
        if kind == "video":
            row.external_url = "https://example.com/nmc-opening"
        else:
            db.add(row)
            await db.flush()
            row.storage_key = _placeholder(row.id, kind)
            continue
        db.add(row)


def _certificate_pdf(number: str, name: str) -> bytes:
    lines = [
        "%PDF-1.4",
        "1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj",
        "2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj",
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 300]/Contents 4 0 R>>endobj",
        f"4 0 obj<</Length 68>>stream\nBT /F1 12 Tf 40 180 Td ({number} {name}) Tj ET\nendstream endobj",
        "trailer<</Root 1 0 R>>",
        "%%EOF",
    ]
    return "\n".join(lines).encode()


async def _ensure_profile(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    huda = await db.scalar(select(User).where(User.email == "huda@example.com"))
    if event is None or huda is None:
        return
    if huda.attendee_type in {"", "Attendee"}:
        huda.attendee_type = "Medical Congress Attendee"
    issued = await db.scalar(select(func.count()).select_from(Certificate).where(Certificate.user_id == huda.id))
    if issued:
        return
    category = await db.scalar(select(Category).where(Category.event_id == event.id, Category.type == "session"))
    extras = [
        ("Infant Feeding Workshop", _at(2026, 5, 22, 13, 0), _at(2026, 5, 22, 14, 0)),
        ("Growth Chart Review", _at(2026, 5, 22, 14, 30), _at(2026, 5, 22, 15, 30)),
        ("Sponsor Symposium", _at(2026, 5, 22, 16, 0), _at(2026, 5, 22, 17, 0)),
        ("Case Discussion", _at(2026, 5, 23, 13, 0), _at(2026, 5, 23, 14, 0)),
        ("Research Roundtable", _at(2026, 5, 23, 14, 30), _at(2026, 5, 23, 15, 15)),
        ("Faculty Networking", _at(2026, 5, 23, 15, 15), _at(2026, 5, 23, 16, 0)),
    ]
    if category is not None:
        for title, start, end in extras:
            found = await db.scalar(select(Session).where(Session.event_id == event.id, Session.title == title))
            if found is None:
                db.add(
                    Session(
                        event_id=event.id,
                        category_id=category.id,
                        title=title,
                        summary=title,
                        start_at=start,
                        end_at=end,
                        room="Hall B",
                        status="scheduled",
                        visibility="published",
                    )
                )
        await db.flush()
    sessions = (await db.scalars(select(Session).where(Session.event_id == event.id, Session.visibility == "published"))).all()
    for row in sessions:
        mark = await db.scalar(
            select(Bookmark).where(Bookmark.user_id == huda.id, Bookmark.target_type == "session", Bookmark.target_id == row.id)
        )
        if mark is None:
            db.add(Bookmark(user_id=huda.id, target_type="session", target_id=row.id))
    handbook = await db.scalar(select(Resource).where(Resource.event_id == event.id, Resource.title == "Congress Handbook"))
    if handbook is None:
        handbook = Resource(
            event_id=event.id,
            title="Congress Handbook",
            description="Attendee guide and venue notes",
            type="document",
            mime_type="application/pdf",
            file_size=900000,
            visibility="published",
            published_at=_at(2026, 5, 20, 9, 4),
            created_by=huda.id,
            created_at=_at(2026, 5, 20, 9, 4),
        )
        db.add(handbook)
        await db.flush()
        handbook.storage_key = _placeholder(handbook.id, "pdf")
    resources = (
        await db.scalars(
            select(Resource)
            .where(Resource.event_id == event.id, Resource.visibility == "published")
            .order_by(Resource.created_at.asc())
        )
    ).all()
    for row in resources[:5]:
        mark = await db.scalar(
            select(Bookmark).where(Bookmark.user_id == huda.id, Bookmark.target_type == "resource", Bookmark.target_id == row.id)
        )
        if mark is None:
            db.add(Bookmark(user_id=huda.id, target_type="resource", target_id=row.id))
    folder = BACKEND_ROOT / "storage" / "certificates"
    folder.mkdir(parents=True, exist_ok=True)
    for index, title in enumerate(("Attendance", "Scientific Sessions", "Workshop Completion"), start=1):
        number = f"NMC-CERT-2026-{index:05d}"
        row = Certificate(
            event_id=event.id,
            user_id=huda.id,
            certificate_number=number,
            file_key=f"certificates/{number}.pdf",
            status="issued",
            issued_by=huda.id,
            issued_at=_at(2026, 5, 23, 18, index),
        )
        db.add(row)
        (folder / f"{number}.pdf").write_bytes(_certificate_pdf(number, huda.full_name))
        del title


FAQS = [
    ("Where do I collect my badge?", "Show the QR code in the My Name Tag screen at the registration desk.", 1),
    ("Is Wi-Fi available at the venue?", "Yes, free Wi-Fi is available throughout the venue.", 2),
    ("Can I download the presentations?", "Yes, open Quick Access → Resources.", 3),
]


async def _ensure_faqs(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    existing = await db.scalar(select(func.count()).select_from(EventFaq).where(EventFaq.event_id == event.id))
    if existing:
        return
    for question, answer, order in FAQS:
        db.add(EventFaq(event_id=event.id, question=question, answer=answer, display_order=order, visibility="published"))


async def _demo_publish_questions(db: AsyncSession) -> None:
    """The attendee demo has no admin portal, so new questions publish immediately."""
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is not None:
        event.qna_moderation_enabled = False


async def _ensure_organizer(db: AsyncSession) -> None:
    existing = await db.scalar(select(User).where(User.email == "organizer@example.com"))
    now = datetime.now(UTC)
    if existing is not None:
        existing.role = "organizer"
        existing.status = "active"
        if existing.email_verified_at is None:
            existing.email_verified_at = now
        return
    db.add(
        User(
            email="organizer@example.com",
            password_hash=hash_password(DEV_PASSWORD),
            full_name="Congress Organizer",
            organization="Nestlé Health Science",
            designation="Event Organizer",
            role="organizer",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
    )


async def _ensure_speaker_account(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    now = datetime.now(UTC)
    ahmed = await db.scalar(select(User).where(User.email == "ahmed@example.com"))
    if ahmed is None:
        ahmed = User(
            email="ahmed@example.com",
            password_hash=hash_password(DEV_PASSWORD),
            full_name="Dr. Ahmed",
            organization="Nestlé Medical Congress",
            designation="Session Moderator",
            role="speaker",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
        db.add(ahmed)
        await db.flush()
    else:
        ahmed.role = "speaker"
        ahmed.status = "active"
    speaker = await db.scalar(select(Speaker).where(Speaker.event_id == event.id, Speaker.name == "Dr. Ahmed"))
    if speaker is not None:
        speaker.user_id = ahmed.id


async def _ensure_desk(db: AsyncSession) -> None:
    existing = await db.scalar(select(User).where(User.email == "desk@example.com"))
    now = datetime.now(UTC)
    if existing is not None:
        existing.role = "checkin_staff"
        existing.status = "active"
        return
    db.add(
        User(
            email="desk@example.com",
            password_hash=hash_password(DEV_PASSWORD),
            full_name="Registration Desk",
            organization="Nestlé Health Science",
            designation="Check-in staff",
            role="checkin_staff",
            status="active",
            email_verified_at=now,
            terms_accepted_at=now,
        )
    )


async def _ensure_exhibitors(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    existing = await db.scalar(select(func.count()).select_from(Exhibitor).where(Exhibitor.event_id == event.id))
    if existing:
        return
    categories = {}
    for name, slug, order in (("Nutrition", "nutrition", 1), ("Research", "research", 2), ("Devices", "devices", 3)):
        row = Category(event_id=event.id, type="exhibitor", name=name, slug=slug, display_order=order)
        db.add(row)
        categories[slug] = row
    await db.flush()
    partners = [
        ("Nestlé Health Science", "A12", "nutrition", "Pediatric nutrition products and clinical education.", "https://www.nestlehealthscience.com", "partners@example.com"),
        ("Danone Research", "B04", "research", "Infant and child nutrition research.", "https://www.danone.com", "research@example.com"),
        ("Abbott Nutrition", "C07", "nutrition", "Clinical nutrition for growth and recovery.", "https://www.abbott.com", "booth@example.com"),
        ("MedDevice Lab", "D02", "devices", "Measurement tools used in pediatric clinics.", "https://example.com", "devices@example.com"),
    ]
    for order, (name, booth, slug, description, website, email) in enumerate(partners, start=1):
        db.add(
            Exhibitor(
                event_id=event.id,
                category_id=categories[slug].id,
                name=name,
                booth=booth,
                description=description,
                website=website,
                contact_email=email,
                display_order=order,
                visibility="published",
            )
        )


async def _ensure_inbox(db: AsyncSession) -> None:
    huda = await db.scalar(select(User).where(User.email == "huda@example.com"))
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if huda is None or event is None:
        return
    session = await db.scalar(select(Session).where(Session.event_id == event.id, Session.visibility == "published").order_by(Session.start_at))
    agenda = await db.scalar(select(Notification).where(Notification.user_id == huda.id, Notification.title == "Congress agenda published"))
    if agenda is not None and session is not None and agenda.deep_link == "nmc://session":
        agenda.deep_link = f"nmc://session/{session.id}"
    titles = set((await db.scalars(select(Notification.title).where(Notification.user_id == huda.id))).all())
    resource = await db.scalar(select(Resource).where(Resource.event_id == event.id, Resource.visibility == "published"))
    if "Your name tag is ready" not in titles:
        db.add(
            Notification(
                user_id=huda.id,
                type="event_update",
                title="Your name tag is ready",
                body="Open your digital badge before you arrive at the venue.",
                deep_link="nmc://home",
            )
        )
    if resource is not None and "New congress resource" not in titles:
        db.add(
            Notification(
                user_id=huda.id,
                type="resource",
                title="New congress resource",
                body=resource.title,
                deep_link=f"nmc://resource/{resource.id}",
            )
        )


async def _enable_social_signin(db: AsyncSession) -> None:
    event = await db.scalar(select(Event).where(Event.is_current.is_(True)))
    if event is None:
        return
    event.google_signin_enabled = True
    event.apple_signin_enabled = True


async def enrich_existing(db: AsyncSession) -> None:
    await _enable_social_signin(db)
    await _ensure_organizer(db)
    await _ensure_desk(db)
    await _demo_publish_questions(db)
    await _describe_sessions(db)
    await _ensure_speakers(db)
    await _ensure_speaker_account(db)
    await _ensure_venue_and_polls(db)
    await _ensure_questions(db)
    await _ensure_resources(db)
    await _ensure_profile(db)
    await _ensure_faqs(db)
    await _ensure_exhibitors(db)
    await _ensure_inbox(db)
    await db.commit()
