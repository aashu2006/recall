"""The single LLM client. Every LLM call in the backend goes through here.

Groq is primary, Gemini Flash-Lite is the fallback. Model names come from env
(GROQ_MODEL, GEMINI_MODEL). Responses are JSON, validated against a pydantic model.

complete_json(system, user, Schema):
- tries Groq, then Gemini (a provider is skipped if its key or model is not set)
- a Groq 429 that says "try again in Xs" (X <= RATE_LIMIT_MAX_WAIT_S) is retried once
  after that wait, since free-tier tokens-per-minute limits clear in seconds
- other HTTP errors, rate limits and timeouts move on to the next provider
- invalid JSON or a schema mismatch gets one retry on the same provider, with the
  validation error sent back to the model, then moves on
"""

import json
import logging
import re
import time
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

RATE_LIMIT_MAX_WAIT_S = 30.0  # longer waits (daily limits) fall back right away
_TRY_AGAIN = re.compile(r"try again in (?:(\d+)h)?(?:(\d+)m(?!s))?(?:(\d+(?:\.\d+)?)(ms|s))?", re.I)


class LlmError(Exception):
    pass


class _ProviderError(Exception):
    """HTTP or transport failure from one provider. Triggers the fallback."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after  # seconds, for a 429 that says when to come back


def complete_json(
    system: str,
    user: str,
    schema: type[T],
    *,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> T:
    """Ask the LLM for a JSON object matching `schema` and return it validated."""
    settings = settings or get_settings()
    providers = _providers(settings)
    if not providers:
        raise LlmError("No LLM configured. Set GROQ_API_KEY + GROQ_MODEL or GEMINI_API_KEY + GEMINI_MODEL")

    system = (
        f"{system}\n\nSirf ek JSON object return karo, koi aur text nahi. "
        f"JSON schema:\n{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
    )
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.llm_timeout)
    errors: list[str] = []
    try:
        for name, call in providers:
            messages = [{"role": "user", "content": user}]
            for attempt in range(2):
                try:
                    raw = _call_once_more_if_rate_limited(name, call, client, settings, system, messages)
                except _ProviderError as e:
                    errors.append(f"{name}: {e}")
                    log.warning("LLM %s failed: %s", name, e)
                    break
                try:
                    return schema.model_validate_json(_strip_fences(raw))
                except ValidationError as e:
                    errors.append(f"{name} invalid JSON (attempt {attempt + 1}): {e}")
                    log.warning("LLM %s returned invalid JSON: %s", name, e)
                    messages += [
                        {"role": "assistant", "content": raw},
                        {
                            "role": "user",
                            "content": f"Ye JSON schema se match nahi karta:\n{e}\n"
                            "Galti theek karke poora JSON dobara bhejo.",
                        },
                    ]
    finally:
        if owns_client:
            client.close()
    raise LlmError("All LLM providers failed: " + " | ".join(errors))


def _call_once_more_if_rate_limited(name, call, client, settings, system, messages) -> str:
    try:
        return call(client, settings, system, messages)
    except _ProviderError as e:
        wait = e.retry_after
        if name != "groq" or wait is None or wait > RATE_LIMIT_MAX_WAIT_S:
            raise
        log.warning("Groq rate limited, retrying once in %.1fs", wait)
        time.sleep(wait + 0.5)
        return call(client, settings, system, messages)


def retry_after_seconds(text: str, header: str | None = None) -> float | None:
    """Wait time from a 429: "Please try again in 7.66s" / "1m2.5s" / "450ms", else Retry-After."""
    m = _TRY_AGAIN.search(text or "")
    if m and any(m.groups()[:3]):
        hours, minutes, num, unit = m.groups()
        secs = float(num or 0) / (1000 if unit == "ms" else 1)
        return int(hours or 0) * 3600 + int(minutes or 0) * 60 + secs
    try:
        return float(header) if header is not None else None
    except ValueError:
        return None


def _providers(settings: Settings):
    out = []
    if settings.groq_api_key and settings.groq_model:
        out.append(("groq", _call_groq))
    if settings.gemini_api_key and settings.gemini_model:
        out.append(("gemini", _call_gemini))
    return out


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else ""
        raw = raw.rsplit("```", 1)[0]
    return raw


def _post(client: httpx.Client, url: str, **kwargs) -> dict:
    try:
        r = client.post(url, **kwargs)
    except httpx.TransportError as e:
        raise _ProviderError(f"connection error: {e}") from e
    if r.status_code != 200:
        wait = retry_after_seconds(r.text, r.headers.get("retry-after")) if r.status_code == 429 else None
        raise _ProviderError(f"HTTP {r.status_code}: {r.text[:300]}", retry_after=wait)
    try:
        return r.json()
    except ValueError as e:
        raise _ProviderError(f"non-JSON response: {r.text[:300]}") from e


def _call_groq(client: httpx.Client, settings: Settings, system: str, messages: list[dict]) -> str:
    body = _post(
        client,
        f"{settings.groq_base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        json={
            "model": settings.groq_model,
            "messages": [{"role": "system", "content": system}, *messages],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        },
    )
    try:
        return body["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise _ProviderError(f"unexpected response shape: {str(body)[:300]}") from e


def _call_gemini(client: httpx.Client, settings: Settings, system: str, messages: list[dict]) -> str:
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    body = _post(
        client,
        f"{settings.gemini_base_url.rstrip('/')}/models/{settings.gemini_model}:generateContent",
        headers={"x-goog-api-key": settings.gemini_api_key},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        },
    )
    try:
        return "".join(p.get("text", "") for p in body["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError, TypeError) as e:
        raise _ProviderError(f"unexpected response shape: {str(body)[:300]}") from e
