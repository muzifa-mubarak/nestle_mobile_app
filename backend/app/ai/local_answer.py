"""Deterministic answers from published event records.

Used when no LLM key is configured (local and test). It never invents facts
and it refuses medical advice, attendee data, and off-topic requests.
"""

UNKNOWN = "I don't have that information. Please check with the registration desk."


def answer(message: str, records: dict) -> dict:
    text = " ".join(message.lower().split())
    if _injection(text):
        return _decline("I can only help with the congress. What would you like to know about the agenda, speakers, or venue?", ["What is on today?", "Where is the venue?"])
    if _medical(text):
        return _decline(
            "I can't give medical advice. I can describe what a session covers if you tell me which one.",
            ["Which sessions are about nutrition?"],
        )
    if _attendee_data(text):
        return _decline("I can't share personal data about attendees. I can help with the agenda, speakers, and venue.", ["Who is speaking?", "Where is the venue?"])
    if _off_topic(text):
        return _decline("That's outside the congress. I can help with the agenda, speakers, venue, and resources.", ["What is on today?", "Where is the venue?"])

    sessions = records.get("sessions") or []
    if _asks_after(text, "opening ceremony"):
        return _session_after(sessions, "opening ceremony")
    if "opening ceremony" in text and any(word in text for word in ("time", "when", "start")):
        return _one_session(sessions, "opening ceremony")
    if text.startswith("who is") or "who is " in text:
        return _speaker(records.get("speakers") or [], text)
    if "day 1" in text or "on day 1" in text:
        return _day_list(sessions, 1)
    if "venue" in text or "where is the congress" in text:
        return _venue(records.get("venue"))
    if "parking" in text or "wi-fi" in text or "wifi" in text:
        return _facilities(records.get("venue"))
    if "download" in text and ("program" in text or "presentation" in text or "resource" in text):
        return _resource(records.get("resources") or [], "program")
    if "nutrition" in text and "categor" in text:
        return _category(sessions, "nutrition")
    if "still on" in text or "cancelled" in text or "canceled" in text:
        return _status_lookup(sessions, text)
    faq = _faq(records.get("faqs") or [], text)
    if faq is not None:
        return faq
    speaker = _speaker(records.get("speakers") or [], text, required=False)
    if speaker is not None:
        return speaker
    titled = _title_lookup(sessions, text)
    if titled is not None:
        return titled
    return {"answer": UNKNOWN, "references": [], "followups": ["What is on Day 1?", "Where is the venue?"]}


def _decline(answer: str, followups: list[str]) -> dict:
    return {"answer": answer, "references": [], "followups": followups}


def _injection(text: str) -> bool:
    markers = ("ignore your instructions", "system prompt", "print your prompt", "jailbreak", "developer message", "reveal your rules")
    return any(marker in text for marker in markers)


def _medical(text: str) -> bool:
    markers = ("medication", "medicine", "prescribe", "diagnosis", "dose", "what should i give", "clinical advice")
    return any(marker in text for marker in markers)


def _attendee_data(text: str) -> bool:
    return "attendee" in text and any(word in text for word in ("email", "phone", "number", "contact", "list of"))


def _off_topic(text: str) -> bool:
    markers = ("football", "soccer", "weather", "stock price", "recipe", "movie")
    congress = ("session", "speaker", "venue", "agenda", "congress", "poll", "wifi", "wi-fi", "parking", "resource")
    return any(marker in text for marker in markers) and not any(word in text for word in congress)


def _asks_after(text: str, title: str) -> bool:
    return title in text and any(word in text for word in ("after", "next", "following"))


def _one_session(sessions: list[dict], title: str) -> dict:
    match = _find_title(sessions, title)
    if match is None:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    status = _status_sentence(match)
    answer = (
        f"{match['title']} is on {match['day_label']} ({match['weekday']}, {match['date_label']}) "
        f"from {match['start']} to {match['end']} in {match['room'] or 'the venue'}.{status}"
    )
    return {"answer": answer, "references": [_ref("session", match)], "followups": [f"Who is speaking at {match['title']}?"]}


def _session_after(sessions: list[dict], title: str) -> dict:
    ordered = sorted(sessions, key=lambda row: (row["day_number"], row["start_sort"]))
    current = _find_title(ordered, title)
    if current is None:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    index = ordered.index(current)
    nxt = ordered[index + 1] if index + 1 < len(ordered) else None
    if nxt is None or nxt["day_number"] != current["day_number"]:
        return {"answer": f"Nothing else is scheduled after {current['title']} that day.", "references": [_ref("session", current)], "followups": []}
    status = _status_sentence(nxt)
    answer = f"After {current['title']} is {nxt['title']} at {nxt['start']} in {nxt['room'] or 'the venue'}.{status}"
    return {"answer": answer, "references": [_ref("session", nxt)], "followups": []}


def _day_list(sessions: list[dict], day_number: int) -> dict:
    rows = [row for row in sessions if row["day_number"] == day_number]
    rows.sort(key=lambda row: row["start_sort"])
    if not rows:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    lines = [f"{row['start']} {row['title']} ({row['room'] or 'venue'})" for row in rows]
    answer = f"{rows[0]['day_label']} sessions: " + "; ".join(lines) + "."
    return {"answer": answer, "references": [_ref("session", row) for row in rows[:3]], "followups": []}


def _speaker(speakers: list[dict], text: str, required: bool = True) -> dict | None:
    match = None
    for speaker in speakers:
        if speaker["name"].lower() in text:
            match = speaker
            break
    if match is None:
        return None if not required else {"answer": UNKNOWN, "references": [], "followups": []}
    sessions = ", ".join(match["sessions"]) or "no listed session"
    answer = (
        f"{match['name']} is {match['designation'] or 'a speaker'}"
        f"{' from ' + match['country'] if match.get('country') else ''}"
        f"{' at ' + match['organization'] if match.get('organization') else ''}. "
        f"Sessions: {sessions}."
    )
    return {"answer": answer, "references": [_ref("speaker", match)], "followups": []}


def _venue(venue: dict | None) -> dict:
    if not venue:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    facilities = ", ".join(venue.get("facilities") or []) or "no listed facilities"
    answer = f"The congress is at {venue['name']}, {venue['address']}. Facilities: {facilities}."
    return {"answer": answer, "references": [{"type": "venue", "id": venue["id"], "label": venue["name"]}], "followups": ["Is there parking?"]}


def _facilities(venue: dict | None) -> dict:
    if not venue:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    labels = [label.lower() for label in venue.get("facilities") or []]
    parking = any("parking" in label for label in labels)
    wifi = any("wi-fi" in label or "wifi" in label for label in labels)
    parts = []
    if parking:
        parts.append("Yes, parking is available")
    if wifi:
        parts.append("Yes, free Wi-Fi is available")
    if not parts:
        return {"answer": UNKNOWN, "references": [{"type": "venue", "id": venue["id"], "label": venue["name"]}], "followups": []}
    answer = " and ".join(parts) + f" at {venue['name']}."
    return {"answer": answer, "references": [{"type": "venue", "id": venue["id"], "label": venue["name"]}], "followups": []}


def _resource(resources: list[dict], hint: str) -> dict:
    match = next((row for row in resources if hint in row["title"].lower() or hint in (row.get("description") or "").lower()), None)
    if match is None and resources:
        match = resources[0]
    if match is None:
        return {"answer": "Open Quick Access, then Resources, to see approved files.", "references": [], "followups": []}
    answer = f"Open Quick Access, then Resources, and look for \"{match['title']}\" ({match['type']})."
    return {"answer": answer, "references": [_ref("resource", match)], "followups": []}


def _category(sessions: list[dict], slug: str) -> dict:
    rows = [row for row in sessions if slug in (row.get("category") or "").lower() or slug in (row.get("category_slug") or "")]
    if not rows:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    names = ", ".join(row["title"] for row in rows)
    return {"answer": f"Nutrition sessions: {names}.", "references": [_ref("session", row) for row in rows[:3]], "followups": []}


def _status_lookup(sessions: list[dict], text: str) -> dict:
    match = _find_title(sessions, text) or _best_title(sessions, text)
    if match is None:
        return {"answer": UNKNOWN, "references": [], "followups": []}
    if match["status"] == "cancelled":
        note = f" {match['status_note']}" if match.get("status_note") else ""
        answer = f"{match['title']} is cancelled.{note}"
    elif match["status"] == "changed":
        answer = f"{match['title']} has changed. {match.get('status_note') or ''}".strip()
    else:
        answer = f"{match['title']} is still on, {match['start']} to {match['end']} in {match['room'] or 'the venue'}."
    return {"answer": answer, "references": [_ref("session", match)], "followups": []}


def _faq(faqs: list[dict], text: str) -> dict | None:
    for faq in faqs:
        question = faq["question"].lower()
        words = [word for word in question.split() if len(word) > 3]
        if words and sum(1 for word in words if word in text) >= max(1, len(words) // 2):
            return {"answer": faq["answer"], "references": [], "followups": []}
    return None


def _title_lookup(sessions: list[dict], text: str) -> dict | None:
    match = _best_title(sessions, text)
    if match is None:
        return None
    return _one_session(sessions, match["title"].lower())


def _find_title(sessions: list[dict], text: str) -> dict | None:
    lowered = text.lower()
    for row in sessions:
        if row["title"].lower() in lowered:
            return row
    return None


def _best_title(sessions: list[dict], text: str) -> dict | None:
    best = None
    best_score = 0
    for row in sessions:
        words = [word for word in row["title"].lower().split() if len(word) > 3]
        score = sum(1 for word in words if word in text)
        if score > best_score:
            best = row
            best_score = score
    return best if best_score else None


def _status_sentence(row: dict) -> str:
    if row["status"] == "cancelled":
        return " This session is cancelled."
    if row["status"] == "changed":
        return f" This session has changed. {row.get('status_note') or ''}".rstrip()
    return ""


def _ref(kind: str, row: dict) -> dict:
    return {"type": kind, "id": row["id"], "label": row.get("label") or row.get("title") or row.get("name")}
