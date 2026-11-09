"""HTTP endpoints used without WhatsApp: briefing preview, resolving a pending item, CORS."""

import pytest

from app import briefing, pipeline
from app.config import Settings, get_settings
from app.extract import Item
from app.main import app
from tests.fake_db import FakeDb
from tests.fakes import BRACKET_ORDER, SHARMA

AUTH = {"Authorization": "Bearer s3cret"}
ITEM = Item(kind="update", item="bracket", quantity=300, changed_fields=["quantity"],
            evidence="bracket वाला order तीन सौ कर दो", confidence=0.6)


@pytest.fixture
def db(monkeypatch):
    d = FakeDb()
    d.create_client(SHARMA["name"], SHARMA["phone"], SHARMA["aliases"])
    d.add_order(BRACKET_ORDER)  # id 12, 200 pcs
    d.insert_pending(call_id=7, client_id=1, question="Sharma Steels: kaunsa order?", options=[12, "new"],
                     extracted={"item": ITEM.model_dump(mode="json"), "clip": {"start": 0.4, "end": 5.0}})
    monkeypatch.setattr("app.main.get_db", lambda: d)
    return d


@pytest.fixture
def api(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, cron_secret="s3cret", owner_wa_number="919900000000", gnani_api_key="k")
    return client


@pytest.mark.parametrize("method,path,body", [
    ("post", "/briefing/send", None),
    ("post", "/briefing/preview", None),
    ("post", "/pending/1/resolve", {"choice": "12"}),
])
def test_endpoints_need_cron_secret(api, db, method, path, body):
    assert api.request(method, path, json=body).status_code == 403
    assert api.request(method, path, json=body, headers={"Authorization": "Bearer nope"}).status_code == 403
    assert db.pending[0]["status"] == "pending" and db.sends == []


def test_briefing_preview_endpoint(api, db, monkeypatch):
    monkeypatch.setattr(briefing.tts, "synthesize", lambda text, settings: b"OggS")

    r = api.post("/briefing/preview", headers=AUTH)

    assert r.status_code == 200
    assert r.json()["path"].startswith("briefings/") and "Good morning" in r.json()["text"]
    assert db.sends[0]["status"] == "preview" and db.sends[0]["media_path"] == r.json()["path"]


def test_briefing_preview_endpoint_reports_timbre_failure(api, db, monkeypatch):
    monkeypatch.setattr(briefing.tts, "synthesize", lambda text, settings: 1 / 0)

    r = api.post("/briefing/preview", headers=AUTH)

    assert r.status_code == 502 and r.json()["path"] is None and r.json()["text"]


def test_resolve_with_order_id_updates_the_order(api, db):
    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": "12"})

    assert r.status_code == 200
    assert r.json() == {"pending_id": 1, "choice": "12", "status": "confirmed",
                        "message": r.json()["message"]}
    assert "Order #12 update ho gaya" in r.json()["message"]
    assert db.get_order(12)["quantity"] == 300
    [change] = [c for c in db.changes if c["field"] == "quantity"]
    assert (change["old_value"], change["new_value"], change["call_id"], change["confidence"]) == (200, 300, 7, 1.0)


def test_resolve_new_creates_an_order(api, db):
    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": "new"})

    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    [new] = [o for o in db.orders if o["id"] != 12]
    assert (new["item"], new["quantity"]) == ("bracket", 300)
    assert any(c["order_id"] == new["id"] and c["field"] == "created" for c in db.changes)


def test_resolve_no_rejects_and_saves_nothing(api, db):
    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": "no"})

    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert db.get_order(12)["quantity"] == 200 and db.changes == []


def test_resolve_twice_is_a_conflict(api, db):
    assert api.post("/pending/1/resolve", headers=AUTH, json={"choice": "12"}).status_code == 200

    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": "new"})

    assert r.status_code == 409 and "already confirmed" in r.json()["detail"]
    assert len(db.orders) == 1


@pytest.mark.parametrize("choice,status", [("99", 422), ("maybe", 422), ("", 422), ("12; drop", 422)])
def test_resolve_rejects_bad_choices(api, db, choice, status):
    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": choice})

    assert r.status_code == status
    assert db.pending[0]["status"] == "pending" and db.changes == []


def test_resolve_unknown_pending_is_404(api, db):
    assert api.post("/pending/42/resolve", headers=AUTH, json={"choice": "no"}).status_code == 404


def test_resolve_save_failure_reopens_and_returns_500(api, db, monkeypatch):
    monkeypatch.setattr(db, "update_order", lambda *a, **k: 1 / 0)

    r = api.post("/pending/1/resolve", headers=AUTH, json={"choice": "12"})

    assert r.status_code == 500 and r.json()["status"] == "pending" and "save nahi hua" in r.json()["message"]
    assert db.pending[0]["status"] == "pending"


def test_resolve_uses_the_same_path_as_the_whatsapp_button(api, db, monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline, "resolve_pending", lambda pid, choice, db=None: seen.append((pid, choice)) or "ok")

    api.post("/pending/1/resolve", headers=AUTH, json={"choice": "new"})

    assert seen == [(1, "new")]


def test_cors_allows_the_local_dashboard_only(client):
    def preflight(origin):
        return client.options("/pending/1/resolve", headers={
            "Origin": origin, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type"})

    ok = preflight("http://localhost:3000")
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "authorization" in ok.headers["access-control-allow-headers"].lower()

    other = preflight("https://evil.example")
    assert "access-control-allow-origin" not in other.headers
