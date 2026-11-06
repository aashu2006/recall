import json
import re
from pathlib import Path

import httpx
import pytest

from app import clips, stt
from app.clips import Chunk
from app.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
OK_BODY = json.loads((FIXTURES / "prisma_v3_ok.json").read_text())


@pytest.fixture
def settings():
    return Settings(_env_file=None, gnani_api_key="test-key")


@pytest.fixture
def sleeps(monkeypatch):
    calls = []
    monkeypatch.setattr(stt, "_sleep", calls.append)
    return calls


@pytest.fixture
def fake_chunks(monkeypatch):
    """Replace VAD splitting with fixed (start, end) spans backed by dummy files."""

    def make(spans):
        def split(audio_path, out_dir=None, max_len=28.0):
            chunks = []
            for i, (start, end) in enumerate(spans):
                path = Path(out_dir) / f"chunk_{i}.wav"
                path.write_bytes(b"RIFF fake wav")
                chunks.append(Chunk(start, end, path))
            return chunks

        monkeypatch.setattr(clips, "split_on_silence", split)

    return make


def mock_client(responses):
    """Client whose Nth request gets responses[N] (an httpx.Response or an exception)."""
    requests = []

    def handler(request):
        request.read()
        requests.append(request)
        result = responses[len(requests) - 1]
        if isinstance(result, Exception):
            raise result
        return result

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def ok(transcript=OK_BODY["transcript"]):
    return httpx.Response(200, json={**OK_BODY, "transcript": transcript})


def form(request) -> dict[str, str]:
    """Plain (non-file) multipart fields of a request."""
    pairs = re.findall(rb'name="(\w+)"\r\n\r\n(.*?)\r\n--', request.content, re.S)
    return {k.decode(): v.decode() for k, v in pairs}


def test_transcribe_uses_chunk_offsets_as_segments(settings, fake_chunks, sleeps):
    fake_chunks([(0.4, 12.0), (13.5, 20.2)])
    client, _ = mock_client([ok(), ok("aur 20 bracket bhi chahiye")])

    result = stt.transcribe("note.ogg", settings=settings, client=client)

    assert result == {
        "transcript": f"{OK_BODY['transcript']} aur 20 bracket bhi chahiye",
        "segments": [
            {"start": 0.4, "end": 12.0, "text": OK_BODY["transcript"]},
            {"start": 13.5, "end": 20.2, "text": "aur 20 bracket bhi chahiye"},
        ],
        "model": "prisma-v3.0",
    }


def test_request_fields_and_previous_text(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 5.0), (6.5, 9.0), (10.5, 14.0)])
    client, requests = mock_client([ok(), ok(""), ok("angle 40 kg")])

    stt.transcribe("note.ogg", settings=settings, client=client)

    first, second, third = requests
    assert first.url == "https://api.vachana.ai/stt/v3"
    assert first.headers["X-API-Key-ID"] == "test-key"
    assert first.headers["X-API-Request-ID"]
    assert b'name="audio_file"; filename="chunk_0.wav"' in first.content
    fields = form(first)
    assert fields["model"] == "prisma-v3.0"
    assert fields["language_code"] == "hi-IN,en-IN"
    assert fields["format"] == "codemix"
    assert "MS sheet" in json.loads(fields["keyterms"])
    assert "previous_text" not in fields
    assert form(second)["previous_text"] == OK_BODY["transcript"]
    # Chunk 2 was empty, so chunk 3 still gets chunk 1's text.
    assert form(third)["previous_text"] == OK_BODY["transcript"]


def test_empty_chunk_is_not_a_segment(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 5.0), (6.5, 9.0)])
    client, _ = mock_client([ok(""), ok("channel 6 meter")])

    result = stt.transcribe("note.ogg", settings=settings, client=client)

    assert result["segments"] == [{"start": 6.5, "end": 9.0, "text": "channel 6 meter"}]
    assert result["transcript"] == "channel 6 meter"


def test_retries_503_then_succeeds(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 5.0)])
    unavailable = httpx.Response(
        503, json={"success": False, "error": {"type": "SERVICE_UNAVAILABLE", "message": "busy"}}
    )
    client, requests = mock_client([unavailable, ok()])

    result = stt.transcribe("note.ogg", settings=settings, client=client)

    assert result["transcript"] == OK_BODY["transcript"]
    assert len(requests) == 2
    assert sleeps == [0.5]


def test_retries_connection_error(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 5.0)])
    client, requests = mock_client([httpx.ConnectError("boom"), ok()])

    stt.transcribe("note.ogg", settings=settings, client=client)

    assert len(requests) == 2
    assert sleeps == [0.5]


def test_gives_up_after_retries_on_429(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 5.0)])
    limited = httpx.Response(
        429, json={"detail": {"error_code": "RATE_LIMITED", "message": "slow down", "status_code": 429}}
    )
    client, requests = mock_client([limited] * 4)

    with pytest.raises(stt.SttError) as exc:
        stt.transcribe("note.ogg", settings=settings, client=client)

    assert exc.value.status == 429
    assert exc.value.error_type == "RATE_LIMITED"
    assert len(requests) == 4
    assert sleeps == [0.5, 1.0, 2.0]


def test_does_not_retry_400(settings, fake_chunks, sleeps):
    fake_chunks([(0.0, 35.0)])
    too_long = httpx.Response(
        400,
        json={"success": False, "error": {"type": "MAX_AUDIO_DURATION_EXCEEDED", "message": "> 30 s"}},
    )
    client, requests = mock_client([too_long])

    with pytest.raises(stt.SttError) as exc:
        stt.transcribe("note.ogg", settings=settings, client=client)

    assert exc.value.error_type == "MAX_AUDIO_DURATION_EXCEEDED"
    assert len(requests) == 1
    assert sleeps == []


def test_no_speech_makes_no_calls(settings, fake_chunks, sleeps):
    fake_chunks([])
    client, requests = mock_client([])

    result = stt.transcribe("note.ogg", settings=settings, client=client)

    assert result == {"transcript": "", "segments": [], "model": "prisma-v3.0"}
    assert requests == []


def test_missing_api_key_fails_before_any_call(fake_chunks):
    fake_chunks([(0.0, 5.0)])
    client, requests = mock_client([ok()])

    with pytest.raises(stt.SttError, match="GNANI_API_KEY"):
        stt.transcribe("note.ogg", settings=Settings(_env_file=None), client=client)

    assert requests == []


def test_max_chunk_setting_is_passed_to_splitter(monkeypatch, settings):
    seen = {}

    def split(audio_path, out_dir=None, max_len=28.0):
        seen["max_len"] = max_len
        return []

    monkeypatch.setattr(clips, "split_on_silence", split)
    settings.gnani_stt_max_chunk_s = 8.0

    stt.transcribe("note.ogg", settings=settings, client=mock_client([])[0])

    assert seen["max_len"] == 8.0


def test_real_http_is_blocked():
    with pytest.raises(RuntimeError, match="Real HTTP call blocked"):
        httpx.post("https://api.vachana.ai/stt/v3")
