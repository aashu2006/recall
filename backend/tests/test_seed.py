import re
from datetime import date

from app import extract, pipeline, whatsapp
from app.extract import Item
from app.matcher import LlmMatch
from scripts import seed
from tests.fake_db import FakeDb
from tests.fakes import CALL_TIME

TODAY = date(2026, 11, 9)


def test_seed_creates_sharma_bracket_order_and_deliveries():
    db = FakeDb()

    out = seed.seed(db, TODAY, {"sharma": "+91 99999 11111"})

    assert len(db.clients) == 3
    sharma = db.client_by_phone("919999911111")
    assert sharma["name"] == "Sharma Steels" and "Sharma ji" in sharma["aliases"]
    [bracket] = [o for o in db.open_orders(sharma["id"]) if o["item"] == "bracket"]
    assert (bracket["quantity"], bracket["rate"], bracket["unit"]) == (200, 45, "pcs")
    assert len(db.deliveries_between(TODAY, TODAY)) == 2
    assert len(db.deliveries_between(date(2026, 11, 10), date(2026, 11, 10))) == 2
    # every order has its 'created' history row
    assert sorted(c["order_id"] for c in db.changes if c["field"] == "created") == sorted(out["orders"])


def test_seed_is_rerunnable():
    db = FakeDb()
    seed.seed(db, TODAY)

    out = seed.seed(db, TODAY)

    assert out == {"clients": {}, "orders": []} and len(db.clients) == 3


def test_seed_keeps_eval_order_ids():
    db = FakeDb()

    out = seed.seed(db, TODAY)

    ids = {key: [o["id"] for o in db.open_orders(cid)] for key, cid in out["clients"].items()}
    assert ids == {"sharma": [1, 2], "gupta": [3, 4, 7], "patel": [5, 6]}  # eval/cases.json uses 1-6


GUPTA_TRANSCRIPT = "हाँ भैया, Gupta Fabricators से बोल रहा हूँ। वो MS sheet वाला order है ना, उसको one fifty कर दो।"
GUPTA_ITEM = Item(
    kind="update", item="MS sheet", quantity=150, changed_fields=["quantity"],
    order_ref="MS sheet वाला order", evidence="वो MS sheet वाला order है ना, उसको one fifty कर दो",
    confidence=0.9,
)


def test_gupta_ms_sheet_update_goes_to_owner_with_both_orders(tmp_path, monkeypatch):
    db = FakeDb()
    seed.seed(db, TODAY)
    gupta = db.client_by_phone("919800000002")
    sheets = {o["id"]: o for o in db.open_orders(gupta["id"]) if o["item"] == "MS sheet"}
    assert [(o["spec"], o["quantity"], o["rate"], o["delivery_date"]) for o in sheets.values()] == [
        ("2mm", 100, 1150, "2026-11-09"), ("2mm", 60, 1100, "2026-11-13")]

    def complete_json(system, user, schema):
        if schema is extract.Extraction:
            return extract.Extraction(items=[GUPTA_ITEM])
        # matcher: like the real LLM, flag every open order the note could mean
        orders = user.split("Voice note se nikla item:")[0]
        ids = [int(m) for m in re.findall(r"#(\d+), MS sheet,", orders)]
        return LlmMatch(order_id=ids[0], candidate_ids=ids, confidence=0.8)

    monkeypatch.setattr(pipeline.stt, "transcribe", lambda path, *, keyterms=None: {
        "transcript": GUPTA_TRANSCRIPT, "segments": [{"start": 0.3, "end": 6.1, "text": GUPTA_TRANSCRIPT}]})
    monkeypatch.setattr(extract.llm, "complete_json", complete_json)
    monkeypatch.setattr(pipeline.clips, "duration", lambda p: 6.4)
    note = tmp_path / "gupta.ogg"
    note.write_bytes(b"OggS gupta")

    res = pipeline.handle_voice_note(note, "919800000002", "wamid.g1", CALL_TIME, db=db)

    assert res.order_ids == [] and len(res.pending) == 1
    [p] = res.pending
    assert sorted(p.options) == sorted(sheets) == [3, 7]
    assert whatsapp.owner_buttons(p) == [
        (f"pc:{p.id}:3", "Order #3"), (f"pc:{p.id}:7", "Order #7"), (f"pc:{p.id}:no", "❌ Nahi")]
    assert "Kaunse order ka hai?" in p.question
    # nothing written to either order until the owner taps
    assert [db.get_order(i)["quantity"] for i in (3, 7)] == [100, 60]
    assert not [c for c in db.changes if c["order_id"] in (3, 7) and c["field"] != "created"]
