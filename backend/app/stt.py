"""Prisma STT client (Gnani). See docs/gnani-api.md.

REST (POST /stt/v3) only, which takes clips up to 30 s. Voice notes of any length are split
with Silero VAD into <= 30 s chunks; our own chunk offsets become the segment timestamps for
audio proof. The Batch API (long calls, speaker labels) is not used in this build.

Chunks are sent sequentially (parallel requests can hit 429). Before calling Gnani, check
calls.audio_hash (SHA-256) and reuse the cached transcript. Never call this in tests.
"""

import json
import logging
import tempfile
import time
import uuid
from pathlib import Path

import httpx

from app import clips
from app.config import Settings, get_settings

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 503, 504}
BACKOFF_S = (0.5, 1.0, 2.0)  # first try + one retry per delay
PREVIOUS_TEXT_MAX = 600  # Prisma keeps only the last 600 chars
MAX_KEYTERMS = 200  # Prisma v3.0 limit

_sleep = time.sleep  # patched in tests


class SttError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        error_type: str | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.request_id = request_id


def transcribe(
    audio_path: str | Path,
    *,
    keyterms: list[str] | None = None,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
) -> dict:
    """Transcribe a voice note: VAD chunks -> Prisma REST, one chunk at a time.

    Returns {"transcript", "segments": [{start, end, text}], "model"}. Segment times are
    chunk offsets in the original audio, in seconds.

    keyterms: words to bias recognition for this note (client names, their open order items).
    None falls back to settings.gnani_stt_keyterms; [] sends no keyterms.
    """
    settings = settings or get_settings()
    if not settings.gnani_api_key:
        raise SttError("GNANI_API_KEY is not set")
    terms = _clean_keyterms(settings.gnani_stt_keyterms if keyterms is None else keyterms)

    owns_client = client is None
    client = client or httpx.Client(timeout=settings.gnani_stt_timeout)
    segments: list[dict] = []
    model = settings.gnani_stt_model
    try:
        with tempfile.TemporaryDirectory(prefix="recall-stt-") as tmp:
            chunks = clips.split_on_silence(
                audio_path, out_dir=tmp, max_len=settings.gnani_stt_max_chunk_s
            )
            previous_text = None
            for chunk in chunks:
                body = _post_chunk(client, settings, chunk.path, previous_text, terms)
                model = body.get("model") or model
                text = (body.get("transcript") or "").strip()
                if text:
                    segments.append({"start": chunk.start, "end": chunk.end, "text": text})
                    previous_text = text[-PREVIOUS_TEXT_MAX:]
    finally:
        if owns_client:
            client.close()

    return {
        "transcript": " ".join(s["text"] for s in segments),
        "segments": segments,
        "model": model,
    }


def client_keyterms(
    client: dict | None, open_orders: list[dict], settings: Settings | None = None
) -> list[str]:
    """Keyterms for one sender: client name + aliases + open order items/specs, then the
    global GNANI_STT_KEYTERMS. Cleaned and capped by transcribe()."""
    settings = settings or get_settings()
    terms: list[str] = []
    if client:
        terms += [client.get("name") or "", *(client.get("aliases") or [])]
    for order in open_orders:
        terms += [order.get("item") or "", order.get("spec") or ""]
    return _clean_keyterms(terms + list(settings.gnani_stt_keyterms))


def _clean_keyterms(terms: list[str]) -> list[str]:
    """Strip, drop blanks and duplicates (case-insensitive), cap at Prisma's limit."""
    seen: set[str] = set()
    out = []
    for term in terms:
        term = term.strip()
        if term and term.casefold() not in seen:
            seen.add(term.casefold())
            out.append(term)
    if len(out) > MAX_KEYTERMS:
        log.warning("Dropping %d keyterms over the limit of %d", len(out) - MAX_KEYTERMS, MAX_KEYTERMS)
    return out[:MAX_KEYTERMS]


def _post_chunk(
    client: httpx.Client,
    settings: Settings,
    path: Path,
    previous_text: str | None,
    keyterms: list[str],
) -> dict:
    """POST one <= 30 s chunk to Prisma REST, retrying 429/5xx and connection errors."""
    data = {
        "model": settings.gnani_stt_model,
        "language_code": settings.gnani_stt_language_code,
        "format": settings.gnani_stt_format,
    }
    if keyterms:
        data["keyterms"] = json.dumps(keyterms, ensure_ascii=False)
    if previous_text:
        data["previous_text"] = previous_text
    audio = Path(path).read_bytes()
    url = f"{settings.gnani_base_url.rstrip('/')}/stt/v3"

    for attempt in range(len(BACKOFF_S) + 1):
        request_id = str(uuid.uuid4())
        headers = {"X-API-Key-ID": settings.gnani_api_key, "X-API-Request-ID": request_id}
        try:
            r = client.post(
                url,
                headers=headers,
                data=data,
                files={"audio_file": (Path(path).name, audio, "audio/wav")},
            )
        except httpx.TransportError as e:
            error = SttError(f"connection error: {e}", request_id=request_id)
        else:
            if r.status_code == 200:
                return _parse_ok(r, request_id)
            error = _error_from(r, request_id)
            if r.status_code not in RETRY_STATUSES:
                raise error
        if attempt < len(BACKOFF_S):
            log.warning("Prisma attempt %d failed (%s), retrying", attempt + 1, error)
            _sleep(BACKOFF_S[attempt])
    raise error


def _parse_ok(r: httpx.Response, request_id: str) -> dict:
    body = r.json()
    request_id = body.get("request_id") or request_id
    if body.get("success") is False:
        raise SttError(f"Prisma returned success=false: {body}", status=200, request_id=request_id)
    if body.get("truncated"):
        log.warning("Prisma transcript truncated (request_id=%s)", request_id)
    log.info(
        "Prisma ok request_id=%s processing_time=%s", request_id, body.get("processing_time")
    )
    return body


def _error_from(r: httpx.Response, request_id: str) -> SttError:
    """Normalise the several Gnani error shapes into one SttError."""
    try:
        body = r.json()
    except ValueError:
        body = None
    if not isinstance(body, dict):
        body = {}
    err, detail = body.get("error"), body.get("detail")
    if isinstance(err, dict):  # {"success": false, "error": {"type", "message"}}
        error_type, message = err.get("type"), err.get("message")
    elif isinstance(detail, dict):  # auth / rate limit: {"detail": {"error_code", "message"}}
        error_type, message = detail.get("error_code"), detail.get("message")
    else:  # 504 {"error", "code"}, 422 {"detail": [...]}, or not JSON
        error_type = body.get("code") or (err if isinstance(err, str) else None)
        message = body.get("message") or str(detail or err or r.text[:200])
    return SttError(
        f"Prisma {r.status_code} {error_type}: {message}",
        status=r.status_code,
        error_type=error_type,
        request_id=request_id,
    )
