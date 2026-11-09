"""Timbre TTS client (Gnani). See docs/gnani-api.md.

Returns OGG/Opus bytes that WhatsApp plays directly as a voice note. Write numbers, dates
and money as words in the input text. Never call this in tests.
"""

import logging
import time
import uuid

import httpx

from app.config import Settings, get_settings

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 503, 504}
BACKOFF_S = (0.5, 1.0, 2.0)
_sleep = time.sleep  # patched in tests


class TtsError(Exception):
    pass


def synthesize(text: str, *, settings: Settings | None = None, client: httpx.Client | None = None) -> bytes:
    """Text -> OGG/Opus voice note bytes (Timbre, Hinglish voice from settings)."""
    settings = settings or get_settings()
    if not settings.gnani_api_key:
        raise TtsError("GNANI_API_KEY is not set")
    owns_client = client is None
    client = client or httpx.Client(timeout=settings.gnani_stt_timeout)
    body = {
        "text": text,
        "model": settings.gnani_tts_model,
        "voice": settings.gnani_tts_voice,
        "language": settings.gnani_tts_language,
        "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1, "container": "ogg"},
    }
    url = f"{settings.gnani_base_url.rstrip('/')}/api/v1/tts/inference"
    try:
        for attempt in range(len(BACKOFF_S) + 1):
            request_id = str(uuid.uuid4())
            try:
                r = client.post(url, json=body, headers={
                    "X-API-Key-ID": settings.gnani_api_key, "X-API-Request-ID": request_id})
            except httpx.TransportError as e:
                error = TtsError(f"connection error: {e} (request_id={request_id})")
            else:
                if r.status_code == 200 and r.content:
                    log.info("Timbre ok request_id=%s bytes=%d", request_id, len(r.content))
                    return r.content
                error = TtsError(f"Timbre {r.status_code}: {r.text[:300]} (request_id={request_id})")
                if r.status_code not in RETRY_STATUSES:
                    raise error
            if attempt < len(BACKOFF_S):
                log.warning("Timbre attempt %d failed (%s), retrying", attempt + 1, error)
                _sleep(BACKOFF_S[attempt])
        raise error
    finally:
        if owns_client:
            client.close()
