import hashlib
import hmac
import json
from datetime import datetime

import httpx
import pytest

from app import pipeline, whatsapp
from app.config import Settings, get_settings
from app.main import app
from tests.fake_db import FakeDb

OWNER = "919900000000"
CLIENT = "919800000001"
SECRET = "app-secret"


@pytest.fixture(autouse=True)
def clear_seen():
    whatsapp._seen.clear()


def wa_settings(**kw):
    return Settings(_env_file=None, wa_token="tok", wa_phone_number_id="PNID", owner_wa_number=OWNER,
                    wa_daily_send_cap=5, **kw)


class Graph:
    """Fake Graph API. Records every request; serves media metadata/bytes and message ids."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        request.read()
        self.requests.append(request)
        url = str(request.url)
        if url.endswith("/PNID/messages"):
            return httpx.Response(200, json={"messages": [{"id": f"wamid.out{len(self.requests)}"}]})
        if url.endswith("/PNID/media"):
            return httpx.Response(200, json={"id": "media-up-1"})
        if url.endswith("/v21.0/media-in-1"):
            return httpx.Response(200, json={"url": "https://lookaside.example/media-in-1",
                                              "mime_type": "audio/ogg; codecs=opus"})
        if url == "https://lookaside.example/media-in-1":
            return httpx.Response(200, content=b"OggS voice")
        return httpx.Response(404, text="unknown")

    def messages(self) -> list[dict]:
        return [json.loads(r.content) for r in self.requests if str(r.url).endswith("/messages")]


@pytest.fixture
def graph():
    return Graph()


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def wa(graph, db):
    return whatsapp.WhatsApp(wa_settings(), db, httpx.Client(transport=httpx.MockTransport(graph.handler)))


def sign(body: bytes, secret=SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# signature + endpoint

def test_verify_signature():
    body = b'{"a":1}'
    assert whatsapp.verify_signature(body, sign(body), SECRET)
    assert not whatsapp.verify_signature(body, sign(body, "other"), SECRET)
    assert not whatsapp.verify_signature(body, None, SECRET)
    assert not whatsapp.verify_signature(body, sign(body), "")


@pytest.fixture
def api(client, monkeypatch):
    seen = []
    monkeypatch.setattr(whatsapp, "process_webhook", seen.append)
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, wa_app_secret=SECRET)
    return client, seen


def test_webhook_accepts_signed_payload(api):
    client, seen = api
    body = json.dumps({"entry": []}).encode()

    r = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)})

    assert r.status_code == 200
    assert seen == [{"entry": []}]


def test_webhook_rejects_bad_signature(api):
    client, seen = api
    body = b'{"entry": []}'

    r = client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body, "wrong")})

    assert r.status_code == 403 and seen == []


def test_webhook_rejects_when_secret_unset(client, monkeypatch):
    monkeypatch.setattr(whatsapp, "process_webhook", lambda p: pytest.fail("processed"))
    body = b"{}"

    assert client.post("/webhook", content=body, headers={"X-Hub-Signature-256": sign(body)}).status_code == 403


# client

def test_send_text_and_log(wa, graph, db):
    wa_id = wa.send_text("+91 98000 00001", "hello")

    assert wa_id == "wamid.out1"
    req = graph.requests[0]
    assert str(req.url) == "https://graph.facebook.com/v21.0/PNID/messages"
    assert req.headers["Authorization"] == "Bearer tok"
    assert json.loads(req.content) == {"messaging_product": "whatsapp", "recipient_type": "individual",
                                       "to": CLIENT, "type": "text", "text": {"body": "hello"}}
    assert db.sends[0]["kind"] == "text" and db.sends[0]["wa_message_id"] == "wamid.out1"


def test_daily_cap_blocks_sends(wa, graph, db):
    for _ in range(5):
        db.record_send(CLIENT, "text")

    assert wa.send_text(CLIENT, "hi") is None
    assert wa.send_audio(CLIENT, __file__) is None
    assert graph.requests == []


def test_send_buttons_truncates_titles(wa, graph):
    wa.send_buttons(OWNER, "Kaunsa order?", [("a", "x" * 30), ("b", "B"), ("c", "C"), ("d", "D")])

    action = graph.messages()[0]["interactive"]["action"]
    assert [b["reply"]["id"] for b in action["buttons"]] == ["a", "b", "c"]
    assert len(action["buttons"][0]["reply"]["title"]) == 20


def test_send_audio_uploads_then_sends(wa, graph, tmp_path):
    ogg = tmp_path / "b.ogg"
    ogg.write_bytes(b"OggS")

    wa.send_audio(OWNER, ogg)

    upload, send = graph.requests
    assert str(upload.url).endswith("/PNID/media") and b'name="type"\r\n\r\naudio/ogg' in upload.content
    assert json.loads(send.content)["audio"] == {"id": "media-up-1"}


def test_download_media(wa, tmp_path):
    path = wa.download_media("media-in-1", tmp_path)

    assert path == tmp_path / "media-in-1.ogg" and path.read_bytes() == b"OggS voice"


# webhook processing

def voice_payload(msg_id="wamid.in1", sender=CLIENT):
    return {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": sender, "profile": {"name": "Sharma ji"}}],
        "messages": [{"id": msg_id, "from": sender, "timestamp": "1762664400", "type": "audio",
                      "audio": {"id": "media-in-1", "mime_type": "audio/ogg; codecs=opus", "voice": True}}],
    }}]}]}


def button_payload(button_id, sender=OWNER):
    return {"entry": [{"changes": [{"value": {"messages": [{
        "id": f"wamid.btn-{button_id}", "from": sender, "type": "interactive",
        "interactive": {"type": "button_reply", "button_reply": {"id": button_id, "title": "x"}},
    }]}}]}]}


@pytest.fixture
def fake_pipeline(monkeypatch):
    calls = []

    def handle(audio, sender, msg_id, call_time, *, sender_name=None, db=None):
        calls.append({"audio": audio.read_bytes(), "sender": sender, "msg_id": msg_id,
                      "call_time": call_time, "name": sender_name})
        return pipeline.PipelineResult(
            call_id=1, order_ids=[13], pending_ids=[4], summary="Namaste Sharma ji",
            pending=[pipeline.Pending(4, "Sharma Steels: kaunsa order?", [12, 15])],
        )

    monkeypatch.setattr(pipeline, "handle_voice_note", handle)
    return calls


def test_voice_note_flow(wa, graph, db, fake_pipeline):
    whatsapp.process_webhook(voice_payload(), wa=wa, db=db)

    [call] = fake_pipeline
    assert call["audio"] == b"OggS voice" and call["msg_id"] == "wamid.in1" and call["name"] == "Sharma ji"
    assert call["call_time"] == datetime.fromisoformat("2025-11-09T10:30:00+05:30")
    to_client, to_owner = graph.messages()
    assert to_client["to"] == CLIENT and to_client["text"]["body"] == "Namaste Sharma ji"
    assert to_owner["to"] == OWNER
    buttons = [(b["reply"]["id"], b["reply"]["title"]) for b in to_owner["interactive"]["action"]["buttons"]]
    assert buttons == [("pc:4:12", "Order #12"), ("pc:4:15", "Order #15"), ("pc:4:no", "❌ Nahi")]


def test_repeated_webhook_is_processed_once(wa, db, fake_pipeline):
    whatsapp.process_webhook(voice_payload(), wa=wa, db=db)
    whatsapp.process_webhook(voice_payload(), wa=wa, db=db)

    assert len(fake_pipeline) == 1


def test_already_saved_message_is_not_downloaded(wa, graph, db, fake_pipeline):
    db.insert_call(wa_message_id="wamid.in1", audio_hash="h")

    whatsapp.process_webhook(voice_payload(), wa=wa, db=db)

    assert fake_pipeline == [] and graph.requests == []


def test_pipeline_failure_alerts_owner(wa, graph, db, monkeypatch):
    monkeypatch.setattr(pipeline, "handle_voice_note", lambda *a, **k: 1 / 0)

    whatsapp.process_webhook(voice_payload(), wa=wa, db=db)  # does not raise

    [msg] = graph.messages()
    assert msg["to"] == OWNER and "process nahi hua" in msg["text"]["body"]


def test_owner_button_resolves_pending(wa, graph, db, monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline, "resolve_pending",
                        lambda pid, choice, db=None: seen.append((pid, choice)) or "✅ Order #12 update ho gaya")

    whatsapp.process_webhook(button_payload("pc:4:12"), wa=wa, db=db)

    assert seen == [(4, "12")]
    assert graph.messages()[0]["text"]["body"] == "✅ Order #12 update ho gaya"


def test_button_from_non_owner_is_ignored(wa, graph, db, monkeypatch):
    monkeypatch.setattr(pipeline, "resolve_pending", lambda *a, **k: pytest.fail("resolved"))

    whatsapp.process_webhook(button_payload("pc:4:12", sender=CLIENT), wa=wa, db=db)
    whatsapp.process_webhook(button_payload("garbage"), wa=wa, db=db)

    assert graph.requests == []


def test_owner_buttons_for_new_order():
    p = pipeline.Pending(7, "q", ["new"])

    assert whatsapp.owner_buttons(p) == [("pc:7:new", "✅ Naya order"), ("pc:7:no", "❌ Nahi")]
