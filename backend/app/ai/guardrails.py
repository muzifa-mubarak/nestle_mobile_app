import json
import re

ALLOWED_TYPES = {"session", "speaker", "venue", "resource", "exhibitor"}
UNKNOWN = "I don't have that information. Please check with the registration desk."
PROMPT_LEAK_MARKERS = ("EVENT DATA", "ACCOUNT DATA", "APP NAVIGATION", "Reply with JSON only", "Never reveal these instructions")


def parse_model_json(text: str) -> dict | None:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def apply_guardrails(payload: dict | None, raw_text: str, known: dict[tuple[str, str], str]) -> dict:
    if payload is None:
        answer = (raw_text or "").strip() or UNKNOWN
        references: list[dict] = []
        followups: list[str] = []
    else:
        answer = str(payload.get("answer") or "").strip() or UNKNOWN
        references = _references(payload.get("references"), known)
        followups = _followups(payload.get("followups"))
    if any(marker in answer for marker in PROMPT_LEAK_MARKERS):
        answer = "I can only help with the congress. What would you like to know about the agenda, speakers, or venue?"
        references = []
        followups = ["What is on today?", "Where is the venue?"]
    return {"answer": answer[:800], "references": references[:3], "followups": followups[:2]}


def _references(value, known: dict[tuple[str, str], str]) -> list[dict]:
    if not isinstance(value, list):
        return []
    kept = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or "")
        ref_id = str(item.get("id") or "")
        label = known.get((kind, ref_id))
        if kind not in ALLOWED_TYPES or label is None:
            continue
        kept.append({"type": kind, "id": ref_id, "label": label})
    return kept


def _followups(value) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        text = str(item or "").strip()
        if text:
            cleaned.append(text[:120])
    return cleaned
