# Gnani Speech API notes (for Recall)

Source: https://docs.gnani.ai/api/introduction/introduction (checked 6 Nov 2026). Full docs index: https://docs.gnani.ai/llms.txt

## Basics
- Base URL: `https://api.vachana.ai`
- Auth header on every request: `X-API-Key-ID: <GNANI_API_KEY>`
- Optional header `X-API-Request-ID: <uuid>` is echoed back as `request_id`. Log it, support asks for it.
- Python SDK: `pip install -U "gnani-vachana>=0.8.1"` (Python 3.10+, reads `GNANI_API_KEY` from env). We call the REST APIs with `httpx` directly so tests are easy to mock, SDK is optional.
- Languages: `bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `ta-IN`, `te-IN`

## Important for Recall (differs from PRD)
1. **REST STT max audio is 30 s**, not 60 s. Longer audio returns `400 MAX_AUDIO_DURATION_EXCEEDED`.
2. **REST STT gives no segment timestamps.** Only Batch gives `start_time` / `end_time` per segment.
3. Plan for audio proof clips:
   - Default: split the voice note with Silero VAD into utterances (each <= 30 s), send each chunk to REST STT, keep our own start/end offsets per chunk. This gives timestamps and stays fast.
   - Batch is for long calls (> a few minutes) or when we need speaker labels (diarization). It is async with polling every 10 s, so too slow for the live voice note path.
4. Prisma v3.0 exists and fits Hinglish better: `model=prisma-v3.0`, `language_code=hi-IN,en-IN`, `format=codemix`, plus `keyterms` for factory words (MS sheet, bracket, angle, channel, mm, kg). Try v3.0 first, fall back to v2.5 if quality is worse.
5. Accounts can be one request at a time: a second parallel request may get `429 RATE_LIMITED`. Process chunks sequentially.

---

## 1. STT REST (Prisma), short clips

`POST https://api.vachana.ai/stt/v3`, `multipart/form-data`, synchronous.

| Field | Required | Values / notes |
|---|---|---|
| `audio_file` | yes | WAV, MP3, OGG, FLAC, AAC, M4A. Max 30 s. Min 0.1 s (shorter returns empty transcript). Converted to 16 kHz mono server side |
| `language_code` | yes | v2.5: one code, e.g. `hi-IN`. v3.0: also `indic-auto` or 1 to 4 codes comma separated, e.g. `hi-IN,en-IN` (hints, not a lock) |
| `model` | no | `prisma-v3.0`. Omit for Prisma v2.5 |
| `format` | no | `verbatim` (default), `transcribe` (ITN on, numbers as digits), `codemix` (v3.0), `transliterate` (v3.0) |
| `itn_native_numerals` | no | bool, only with `format=transcribe` |
| `keyterms` | no | v3.0. JSON array or comma separated, up to 200 terms |
| `topic` | no | v3.0. Max 1600 chars, context about the audio |
| `previous_text` | no | v3.0. Last 600 chars kept, context from previous chunk |
| `speaker_names` | no | v3.0. 1 to 4 names |
| `enable_substitution` / `substitution_map` | no | JSON list, max 10 rules: `{"patterns": [...], "replacement": "..."}` |
| `bias_list` / `bias_score` | no | v2.5 word boosting. Up to 100 single letters-only words. Score in `0.0, 0.5, 1.0, 1.5, 2.0` |

Response 200:
```json
{
  "success": true,
  "request_id": "...",
  "transcript": "<text, empty string if no speech>",
  "model": "prisma-v3.0",
  "detected_language_code": "hi-IN",
  "truncated": true,
  "processing_time": 0.6,
  "end_to_end_latency": 0.7
}
```
- `truncated` only appears when true: retry with shorter audio.
- v2.5 also returns `output.literal` (text before ITN).

Example:
```python
import httpx
with open("note.ogg", "rb") as f:
    r = httpx.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": API_KEY},
        files={"audio_file": ("note.ogg", f, "audio/ogg")},
        data={"model": "prisma-v3.0", "language_code": "hi-IN,en-IN", "format": "codemix"},
        timeout=60,
    )
body = r.json()
```

Errors (`{"success": false, "error": {"type": ..., "message": ...}}`):
- 400: `INVALID_LANGUAGE_CODE`, `MODEL_UNSUPPORTED_LANGUAGE`, `INVALID_MODEL`, `INVALID_FORMAT`, `INVALID_CONTEXT`, `EMPTY_AUDIO`, `UNSUPPORTED_AUDIO_FORMAT`, `AUDIO_CONVERSION_ERROR`, `MAX_AUDIO_DURATION_EXCEEDED`
- 422: missing fields, body is `{"detail": [...]}`
- 500: `TRANSCRIPTION_FAILED` (already retried once internally), `INTERNAL_SERVER_ERROR`
- 503: `SERVICE_UNAVAILABLE`
- 504: `{"error": ..., "code": "UPSTREAM_TIMEOUT", ...}` (model took > 5 s)

---

## 2. STT Batch (Prisma), long calls + timestamps + speakers

All paths relative to `https://api.vachana.ai`.

| Step | Method + path | Result |
|---|---|---|
| Create | `POST /stt/v3/batch/jobs` | 201, `status: CREATED`, returns `job_id` |
| Start (required!) | `POST /stt/v3/batch/jobs/{job_id}/start` | 202, `status: STARTING` |
| Status | `GET /stt/v3/batch/jobs/{job_id}` | 200 (no transcript here) |
| Files | `GET /stt/v3/batch/jobs/{job_id}/files?status=COMPLETED` | each file has `transcript_url` |
| Transcript | `GET {transcript_url}` | transcript JSON. URL expires in 1 h, re-call `/files` if expired |
| List | `GET /stt/v3/batch/jobs` | |
| Cancel | `POST /stt/v3/batch/jobs/{job_id}/cancel` | |

Create request is `multipart/form-data` with:
- `config` part as JSON (`type=application/json`)
- `files` part, 1 to 100 files, max 10 MB each
- optional `callback_url` for a webhook on terminal state (best effort, polling is source of truth)

`config` fields:

| Field | Required | Default | Notes |
|---|---|---|---|
| `model` | yes | | `gnani-prisma-v2.5` |
| `language_code` | yes | | one code, or up to 3 comma separated for language ID (per file, first code is fallback) |
| `mode` | no | `transcribe` | |
| `with_diarization` | no | false | adds `speaker_id` per segment |
| `num_speakers` | no | 5 | 1 to 8, upper cap |
| `is_multi_channel` | no | false | |
| `with_denoise` | no | false | cleans audio first, slower. Useful for factory noise |
| `bias_list` / `bias_score` | no | | same as REST v2.5 |

No ITN on batch. `gu-IN` and `pa-IN` may not be supported on batch.

Statuses: `CREATED` -> `STARTING` -> `QUEUED` -> `IN_PROGRESS` -> `COMPLETED`. Terminal: `COMPLETED`, `PARTIAL_FAILURE`, `FAILED`, `START_FAILED`, `CANCELLED`. Poll every 10 s or more (tighter risks 429).

Transcript JSON:
```json
{
  "full_transcript": "...",
  "model": "gnani-prisma-v2.5",
  "language_code": "hi-IN",
  "duration_seconds": 6.01,
  "segments": [
    {"segment_id": 0, "start_time": 0.0, "end_time": 0.71, "text": "...", "speaker_id": 1,
     "confidence": null, "language_detected": null, "sentiment": null, "emotion": null}
  ]
}
```

Limits: max 4 h per file, min 0.1 s, max 5000 segments per file. Formats: wav, mp3, mp4, flac, ogg, opus, m4a, aac, webm, amr.

Example:
```bash
curl -X POST https://api.vachana.ai/stt/v3/batch/jobs \
  -H "X-API-Key-ID: $GNANI_API_KEY" \
  -F 'config={"model":"gnani-prisma-v2.5","language_code":"hi-IN,en-IN","with_diarization":true};type=application/json' \
  -F "files=@./call.wav"
curl -X POST https://api.vachana.ai/stt/v3/batch/jobs/$JOB_ID/start -H "X-API-Key-ID: $GNANI_API_KEY"
curl https://api.vachana.ai/stt/v3/batch/jobs/$JOB_ID -H "X-API-Key-ID: $GNANI_API_KEY"
curl "https://api.vachana.ai/stt/v3/batch/jobs/$JOB_ID/files?status=COMPLETED" -H "X-API-Key-ID: $GNANI_API_KEY"
```

Batch errors (`{"error": "CODE", "message": "..."}`): 400 `UNSUPPORTED_LANGUAGE`, `INVALID_CONFIG`, `NO_FILES_PROVIDED`, `FILE_TOO_LARGE`; 404 `JOB_NOT_FOUND`; 409 `JOB_ALREADY_STARTED`, `JOB_CANCELLED`, `JOB_ALREADY_COMPLETED`; 422 bad job_id; 500 if `config` is not valid JSON.

---

## 3. TTS REST (Timbre)

`POST https://api.vachana.ai/api/v1/tts/inference`, JSON body, response is **raw binary audio** (not base64).

| Field | Required | Values |
|---|---|---|
| `text` | yes | Write numbers, dates and money as words for natural speech. No documented length limit, very long text can 500, so keep briefing under ~60 s of speech or split |
| `model` | yes | `timbre-v2.5` (recommended) or `timbre-v3.0` |
| `voice` | yes | from that model's catalog (voices are not shared across models) |
| `language` | yes | `auto`, `hi-IN`, `en-IN`, ..., `hi-en` (Hinglish) |
| `speed` | no | 0.85 to 1.15, default 1.0 |
| `audio_config` | yes | see below |

`audio_config`: `sample_rate` (8000, 16000, 22050, 24000, 44100, 48000; default 48000), `num_channels` (default 1), `sample_width` (default 2), `encoding` (`linear_pcm`, `pcm_s16le`, `pcm_mulaw`, `pcm_alaw`, `oggopus`), `container` (`wav`, `raw`, `mp3`, `ogg`, `mulaw`, `alaw`), `bitrate` (mp3 only).

**For WhatsApp voice notes:** `container: "ogg"` gives OGG Opus (`audio/ogg`), mono. Upload to WhatsApp media as `audio/ogg` and send as type `audio`.

```python
r = httpx.post(
    "https://api.vachana.ai/api/v1/tts/inference",
    headers={"X-API-Key-ID": API_KEY, "Content-Type": "application/json"},
    json={
        "text": "Good morning. Aaj teen delivery hain.",
        "model": "timbre-v2.5",
        "voice": "Poorvi",
        "language": "hi-en",
        "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1, "container": "ogg"},
    },
    timeout=60,
)
open("briefing.ogg", "wb").write(r.content)
```

Errors (`{"success": false, "error": {"type": ..., "message": ...}}`): 400 `INVALID_REQUEST_ERROR` (bad params or voice not in model; the error lists valid voices), 403 `FORBIDDEN` (key or credits), 429 `RATE_LIMIT_ERROR`, 500 `API_ERROR`, 503 `SERVICE_UNAVAILABLE`.

### Voices to use
Timbre v2.5 (one preferred language each):
- Hinglish: **Poorvi** (F, conversational, bilingual). Best pick for briefings and replies.
- Hindi: Ambuja (F), Bhavna (F), Chitra (F), Jwala (F), Nalini (F), Urmila (F), Yashvi (F), Deepak (M), Hemraj (M), Jalaj (M), Omkar (M), Roopesh (M), Vikrant (M)
- English (India): Devika (F), Kaveri (F), Trupti (F), Girish (M), Pranav (M), Shlok (M)
- Full list of 42: https://docs.gnani.ai/api/TTS/available-voices.md

Timbre v3.0 (all 13 voices speak all 10 languages, supports tags like `<pauses>`, `<laugh>`): Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash, Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika, Harshad.

For the eval set (two Hinglish client voices): use Poorvi + one male Hindi voice on v2.5 (e.g. Vikrant), or two v3.0 voices with `language: "hi-en"`.

---

## 4. Auth and rate limit errors (all services)
Shape: `{"detail": {"error_code": "...", "message": "...", "status_code": ...}}`
- 401 `MISSING_API_KEY`, `INVALID_API_KEY`
- 402 insufficient credit
- 403 `SCOPE_NOT_ALLOWED` (key lacks STT or TTS scope)
- 429 `RATE_LIMITED` (no `Retry-After` header)

## 5. Retry rules
- Retry connection errors and 429, 500, 503, 504 with backoff: 0.5 s, 1 s, 2 s, max 3 attempts.
- Never retry other 4xx.
- Transcription is safe to retry (no side effects). Cache by audio hash anyway to save credits.

## Other pages (if needed later)
- STT realtime WebSocket: https://docs.gnani.ai/api/STT/stt-websocket.md
- TTS streaming SSE: https://docs.gnani.ai/api/TTS/tts-sse.md
- Prisma v3.0 details: https://docs.gnani.ai/api/STT/models/prisma-v3.md
- Call analytics use case: https://docs.gnani.ai/api/use-cases/call-analytics.md