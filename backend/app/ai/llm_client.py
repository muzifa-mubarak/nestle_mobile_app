import time
from collections import deque
from dataclasses import dataclass

import httpx

from app.ai.guardrails import apply_guardrails, parse_model_json
from app.ai.local_answer import answer as local_answer
from app.core.config import Settings


@dataclass
class LLMResult:
    answer: str
    references: list[dict]
    followups: list[str]
    model: str
    input_tokens: int | None
    output_tokens: int | None
    failed: bool = False


class CircuitBreaker:
    def __init__(self) -> None:
        self._calls: deque[tuple[float, bool]] = deque()
        self._open_until = 0.0

    def allow(self) -> bool:
        return time.monotonic() >= self._open_until

    def record(self, ok: bool) -> None:
        now = time.monotonic()
        self._calls.append((now, ok))
        while self._calls and now - self._calls[0][0] > 60:
            self._calls.popleft()
        if len(self._calls) < 4:
            return
        failures = sum(1 for _, success in self._calls if not success)
        if failures / len(self._calls) > 0.5:
            self._open_until = now + 30


breaker = CircuitBreaker()


def groq_api_key(settings: Settings) -> str:
    return (settings.groq_api_key or settings.ai_api_key).strip()


def resolve_provider(settings: Settings) -> str:
    if settings.app_env == "test" or settings.ai_provider == "local":
        return "local"
    if groq_api_key(settings):
        return "groq"
    if settings.app_env == "local":
        return "local"
    return "groq"


async def generate(*, settings: Settings, system: str, history: list[dict], user_message: str, records: dict, known: dict[tuple[str, str], str]) -> LLMResult:
    provider = resolve_provider(settings)
    if provider == "local":
        drafted = local_answer(user_message, records)
        guarded = apply_guardrails(drafted, drafted["answer"], known)
        return LLMResult(
            answer=guarded["answer"],
            references=guarded["references"],
            followups=guarded["followups"],
            model="local-grounded",
            input_tokens=None,
            output_tokens=None,
        )
    if not breaker.allow():
        return LLMResult("", [], [], settings.ai_model, None, None, failed=True)
    last_error = True
    raw = ""
    usage_in = None
    usage_out = None
    for attempt in range(2):
        try:
            raw, usage_in, usage_out = await _groq(settings, system, history, user_message)
            last_error = False
            break
        except (httpx.TimeoutException, httpx.HTTPError):
            last_error = True
            if attempt == 1:
                break
    breaker.record(not last_error)
    if last_error:
        return LLMResult("", [], [], settings.ai_model, usage_in, usage_out, failed=True)
    parsed = parse_model_json(raw)
    guarded = apply_guardrails(parsed, raw if parsed is None else "", known)
    return LLMResult(
        answer=guarded["answer"],
        references=guarded["references"],
        followups=guarded["followups"],
        model=settings.ai_model,
        input_tokens=usage_in,
        output_tokens=usage_out,
    )


async def _groq(settings: Settings, system: str, history: list[dict], user_message: str) -> tuple[str, int | None, int | None]:
    messages = [{"role": "system", "content": system}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in history if item["role"] in {"user", "assistant"})
    messages.append({"role": "user", "content": user_message})
    timeout = httpx.Timeout(settings.ai_timeout_seconds)
    payload = {
        "model": settings.ai_model,
        "messages": messages,
        "max_tokens": settings.ai_max_output_tokens,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {groq_api_key(settings)}", "content-type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 400:
            payload.pop("response_format", None)
            response = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    choice = (body.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = message.get("content") or ""
    usage = body.get("usage") or {}
    return text, usage.get("prompt_tokens"), usage.get("completion_tokens")
