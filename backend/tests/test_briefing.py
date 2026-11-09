import json
from datetime import date

import httpx
import pytest

from app import briefing, tts
from app.config import Settings, get_settings
from app.main import app
from tests.fake_db import FakeDb

TODAY = date(2026, 11, 9)


@pytest.fixture
def db():
    d = FakeDb()
    d.create_client("Sharma Steels", "919800000001")
    d.create_client("Gupta Traders", "919800000002")
    d.add_order({"id": 1, "client_id": 1, "item": "MS sheet", "spec": "3mm", "quantity": 50, "unit": "pcs",
                 "delivery_date": "2026-11-09"})
    d.add_order({"id": 2, "client_id": 2, "item": "angle", "quantity": 1250, "unit": "kg",
                 "delivery_date": "2026-11-09"})
    d.add_order({"id": 3, "client_id": 1, "item": "bracket", "quantity": 300, "unit": "pcs",
                 "delivery_date": "2026-11-10"})
    d.add_order({"id": 4, "client_id": 2, "item": "channel", "quantity": 10, "unit": "pcs",
                 "delivery_date": "2026-11-12"})
    d.add_order({"id": 5, "client_id": 2, "item": "pipe", "quantity": 5, "status": "delivered",
                 "delivery_date": "2026-11-09"})
    d.insert_pending(call_id=None, client_id=1, extracted={}, question="q", options=["new"])
    return d


def test_build_lists_today_tomorrow_and_pending(db):
    b = briefing.build(db, TODAY)

    assert b.text.splitlines() == [
        "Good morning! 🌅",
        "Aaj 2 delivery:",
        "• Sharma Steels: MS sheet (3mm) 50 pcs",
        "• Gupta Traders: angle 1250 kg",
        "Kal 1 delivery:",
        "• Sharma Steels: bracket 300 pcs",
        "⏳ 1 item aapke confirm ka wait kar raha hai.",
    ]
    assert "Aaj two deliveries hain." in b.spoken
    assert "Sharma Steels ko fifty pieces 3mm MS sheet." in b.spoken
    assert "Gupta Traders ko one thousand two hundred fifty kilo angle." in b.spoken
    assert "Kal one delivery hai." in b.spoken
    assert "one item aapke confirmation ka wait kar raha hai" in b.spoken
    assert "channel" not in b.text and "pipe" not in b.text


def test_build_empty_day():
    b = briefing.build(FakeDb(), TODAY)

    assert "Aaj koi delivery nahi." in b.text and "Kal koi delivery nahi hai." in b.spoken
    assert "⏳" not in b.text


@pytest.mark.parametrize(("n", "said"), [
    (0, "zero"), (7, "seven"), (42, "forty two"), (300, "three hundred"), (1250, "one thousand two hundred fifty"),
    (150000, "one lakh fifty thousand"), (2.5, "two point five"), (45.0, "forty five"),
])
def test_words(n, said):
    assert briefing.words(n) == said


class FakeWa:
    def __init__(self, owner="919900000000"):
        self.settings = Settings(_env_file=None, owner_wa_number=owner, gnani_api_key="k")
        self.sent = []

    def send_audio(self, to, path):
        self.sent.append(("audio", to, path.read_bytes()))
        return "wamid.a"

    def send_text(self, to, text):
        self.sent.append(("text", to, text))
        return "wamid.t"


def test_send_voice_note(db, monkeypatch):
    seen = []
    monkeypatch.setattr(briefing.tts, "synthesize", lambda text, settings: seen.append(text) or b"OggS")
    wa = FakeWa()

    out = briefing.send(db, wa, TODAY)

    assert out["sent"] == "audio" and seen[0].startswith("Good morning.")
    assert wa.sent == [("audio", "919900000000", b"OggS")]


def test_send_falls_back_to_text(db, monkeypatch):
    monkeypatch.setattr(briefing.tts, "synthesize", lambda text, settings: 1 / 0)
    wa = FakeWa()

    out = briefing.send(db, wa, TODAY)

    assert out["sent"] == "text" and wa.sent[0][0] == "text" and "Aaj 2 delivery" in wa.sent[0][2]


def test_send_needs_owner(db):
    with pytest.raises(RuntimeError, match="OWNER_WA_NUMBER"):
        briefing.send(db, FakeWa(owner=""), TODAY)


def test_endpoint_requires_cron_secret(client, monkeypatch):
    monkeypatch.setattr(briefing, "send", lambda db, wa: pytest.fail("sent"))
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, cron_secret="s3cret")

    assert client.post("/briefing/send").status_code == 403
    assert client.post("/briefing/send", headers={"Authorization": "Bearer nope"}).status_code == 403

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    assert client.post("/briefing/send", headers={"Authorization": "Bearer "}).status_code == 403


def test_endpoint_sends(client, monkeypatch):
    monkeypatch.setattr("app.main.get_db", lambda: FakeDb())
    monkeypatch.setattr(briefing, "send", lambda db, wa: {"text": "hi", "sent": "audio"})
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, cron_secret="s3cret")

    r = client.post("/briefing/send", headers={"Authorization": "Bearer s3cret"})

    assert r.status_code == 200 and r.json() == {"text": "hi", "sent": "audio"}


# tts client

def tts_client(responses):
    requests = []

    def handler(request):
        requests.append(request)
        return responses[len(requests) - 1]

    return httpx.Client(transport=httpx.MockTransport(handler)), requests


def test_tts_request(monkeypatch):
    client, requests = tts_client([httpx.Response(200, content=b"OggS audio")])

    audio = tts.synthesize("Good morning", settings=Settings(_env_file=None, gnani_api_key="k"), client=client)

    assert audio == b"OggS audio"
    req = requests[0]
    assert str(req.url) == "https://api.vachana.ai/api/v1/tts/inference"
    assert req.headers["X-API-Key-ID"] == "k"
    assert json.loads(req.content) == {
        "text": "Good morning", "model": "timbre-v2.5", "voice": "Poorvi", "language": "hi-en", "speed": 1.0,
        "audio_config": {"sample_rate": 48000, "num_channels": 1, "container": "ogg"},
    }


def test_tts_retries_then_fails_on_4xx(monkeypatch):
    sleeps = []
    monkeypatch.setattr(tts, "_sleep", sleeps.append)
    client, requests = tts_client([httpx.Response(503), httpx.Response(200, content=b"OggS")])
    assert tts.synthesize("x", settings=Settings(_env_file=None, gnani_api_key="k"), client=client) == b"OggS"
    assert sleeps == [0.5]

    client, requests = tts_client([httpx.Response(400, json={"error": "bad voice"})])
    with pytest.raises(tts.TtsError, match="400"):
        tts.synthesize("x", settings=Settings(_env_file=None, gnani_api_key="k"), client=client)
    assert len(requests) == 1


def test_tts_needs_key():
    with pytest.raises(tts.TtsError, match="GNANI_API_KEY"):
        tts.synthesize("x", settings=Settings(_env_file=None))
