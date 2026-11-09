import pytest

from app import extract, pipeline
from app.matcher import LlmMatch
from tests.fake_db import FakeDb
from tests.fakes import (
    BRACKET_ORDER,
    CALL_TIME,
    EXTRACT_KEYTERMS,
    EXTRACT_NO_KEYTERMS,
    SHARMA,
    TRANSCRIPT_KEYTERMS,
    TRANSCRIPT_NO_KEYTERMS,
)

SPLIT = "और एक नया order"


def segments(transcript):
    first, second = transcript.split(SPLIT)
    return [{"start": 0.4, "end": 9.8, "text": first.strip()},
            {"start": 10.3, "end": 16.0, "text": SPLIT + second}]


@pytest.fixture
def db():
    d = FakeDb()
    d.create_client(SHARMA["name"], SHARMA["phone"], SHARMA["aliases"])
    d.add_order(BRACKET_ORDER)
    return d


@pytest.fixture
def note(tmp_path):
    p = tmp_path / "note.ogg"
    p.write_bytes(b"OggS fake voice note")
    return p


@pytest.fixture
def world(monkeypatch):
    """Fake STT + LLM. The matcher LLM is overconfident on purpose: it links anything
    that is an update to order #12."""
    state = {"stt_calls": []}

    def install(transcript, extraction):
        def transcribe(audio_path, *, keyterms=None):
            state["stt_calls"].append(keyterms)
            return {"transcript": transcript, "segments": segments(transcript), "model": "prisma-v3.0"}

        def complete_json(system, user, schema):
            if schema is extract.Extraction:
                return extraction
            item = user.split("Voice note se nikla item:")[1]
            if '"new_order"' in item:
                return LlmMatch(order_id=None, candidate_ids=[], confidence=0.9)
            return LlmMatch(order_id=12, candidate_ids=[12], confidence=0.92)

        monkeypatch.setattr(pipeline.stt, "transcribe", transcribe)
        monkeypatch.setattr(extract.llm, "complete_json", complete_json)
        monkeypatch.setattr(pipeline.clips, "duration", lambda p: 16.5)
        return state

    return install


def test_keyterms_note_updates_bracket_and_creates_sheet(db, note, world):
    state = world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)

    res = pipeline.handle_voice_note(note, "+91 98000 00001", "wamid.1", CALL_TIME, db=db)

    assert "Sharma Steels" in state["stt_calls"][0] and "bracket" in state["stt_calls"][0]
    assert res.pending_ids == [] and res.order_ids == [12, 13]
    bracket = db.get_order(12)
    assert (bracket["quantity"], bracket["rate"]) == (300, 42)
    sheet = db.get_order(13)
    assert (sheet["item"], sheet["quantity"], sheet["delivery_date"]) == ("MS sheet", 50, "2026-11-13")

    changes = {(c["order_id"], c["field"]): c for c in db.changes}
    assert changes[(12, "quantity")]["old_value"] == 200 and changes[(12, "rate")]["new_value"] == 42
    assert changes[(12, "quantity")]["call_id"] == res.call_id
    assert (changes[(12, "quantity")]["clip_start"], changes[(12, "quantity")]["clip_end"]) == (0.4, 9.8)
    assert (changes[(13, "created")]["clip_start"], changes[(13, "created")]["clip_end"]) == (10.3, 16.0)
    assert changes[(13, "created")]["clip_path"].startswith("clips/")

    call = db.calls[0]
    assert call["transcript"] == TRANSCRIPT_KEYTERMS and call["duration_seconds"] == 16.5
    assert call["audio_url"] == f"calls/{call['audio_hash']}.ogg"
    assert "Order #12 (bracket) update" in res.summary and "300" in res.summary and "₹42" in res.summary
    assert "Naya order: MS sheet" in res.summary
    assert "confirm" not in res.summary


def test_no_keyterms_note_sends_bracket_update_to_owner(db, note, world):
    world(TRANSCRIPT_NO_KEYTERMS, EXTRACT_NO_KEYTERMS)

    res = pipeline.handle_voice_note(note, "919800000001", "wamid.2", CALL_TIME, db=db)

    assert res.order_ids == [13]  # only the sheet order
    assert res.pending_ids == [1]
    assert (db.get_order(12)["quantity"], db.get_order(12)["rate"]) == (200, 45)  # untouched
    assert not [c for c in db.changes if c["order_id"] == 12]
    p = db.pending[0]
    assert p["options"] == [12]
    assert p["extracted_json"]["item"]["quantity"] == 300
    assert p["extracted_json"]["clip"]["path"].startswith("clips/")
    assert "Sharma Steels" in res.pending[0].question and "#12 bracket 200" in res.pending[0].question
    assert "1 baat owner se confirm" in res.summary


def test_same_audio_reuses_cached_transcript(db, note, world):
    state = world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)

    pipeline.handle_voice_note(note, "919800000001", "wamid.1", CALL_TIME, db=db)
    pipeline.handle_voice_note(note, "919800000001", "wamid.2", CALL_TIME, db=db)

    assert len(state["stt_calls"]) == 1
    assert db.calls[1]["transcript"] == TRANSCRIPT_KEYTERMS


def test_duplicate_message_id_is_skipped(db, note, world):
    state = world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)
    pipeline.handle_voice_note(note, "919800000001", "wamid.1", CALL_TIME, db=db)

    res = pipeline.handle_voice_note(note, "919800000001", "wamid.1", CALL_TIME, db=db)

    assert res.duplicate and len(db.calls) == 1 and len(state["stt_calls"]) == 1


def test_unknown_sender_becomes_client(db, note, world):
    world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)

    pipeline.handle_voice_note(note, "919811111111", "wamid.9", CALL_TIME, sender_name="Gupta ji", db=db)

    assert db.client_by_phone("919811111111")["name"] == "Gupta ji"


def test_owner_confirms_pending_update(db, note, world):
    world(TRANSCRIPT_NO_KEYTERMS, EXTRACT_NO_KEYTERMS)
    pipeline.handle_voice_note(note, "919800000001", "wamid.2", CALL_TIME, db=db)

    reply = pipeline.resolve_pending(1, "12", db=db)

    assert reply.startswith("✅ Order #12 update")
    assert (db.get_order(12)["quantity"], db.get_order(12)["rate"]) == (300, 42)
    assert {c["field"] for c in db.changes if c["order_id"] == 12} == {"quantity", "rate"}
    assert all(c["confidence"] == 1.0 for c in db.changes if c["order_id"] == 12)
    assert "pehle hi" in pipeline.resolve_pending(1, "12", db=db)  # double tap does nothing
    assert len([c for c in db.changes if c["order_id"] == 12]) == 2


def test_owner_rejects_and_invalid_choices(db, note, world):
    world(TRANSCRIPT_NO_KEYTERMS, EXTRACT_NO_KEYTERMS)
    pipeline.handle_voice_note(note, "919800000001", "wamid.2", CALL_TIME, db=db)

    assert "valid nahi" in pipeline.resolve_pending(1, "new", db=db)  # not offered for this one
    assert "valid nahi" in pipeline.resolve_pending(1, "99", db=db)
    assert pipeline.resolve_pending(1, "no", db=db).startswith("❌")
    assert db.pending[0]["status"] == "rejected"
    assert db.get_order(12)["quantity"] == 200
    assert "nahi mila" in pipeline.resolve_pending(42, "no", db=db)


def test_update_with_no_open_orders_goes_to_owner(db, note, world):
    """Client has no open orders at all: the update must wait for the owner, not vanish."""
    world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)
    db.orders.clear()

    res = pipeline.handle_voice_note(note, "919800000001", "wamid.3", CALL_TIME, db=db)

    assert res.order_ids == [1]  # only the sheet order is created
    assert db.get_order(1)["item"] == "MS sheet"
    [p] = db.pending
    assert res.pending_ids == [p["id"]] and p["options"] == ["new"]
    assert p["extracted_json"]["item"]["kind"] == "update"
    assert p["extracted_json"]["item"]["quantity"] == 300
    assert "order nahi mila" in res.pending[0].question
    assert "1 baat owner se confirm" in res.summary


def test_update_matching_no_open_order_goes_to_owner(db, note, world, monkeypatch):
    """Client has open orders but none fits the update (LLM returns no order and no candidates)."""
    world(TRANSCRIPT_KEYTERMS, EXTRACT_KEYTERMS)
    extraction_llm = extract.llm.complete_json

    def no_match(system, user, schema):
        if schema is extract.Extraction:
            return extraction_llm(system, user, schema)
        return LlmMatch(order_id=None, candidate_ids=[], confidence=0.9)

    monkeypatch.setattr(extract.llm, "complete_json", no_match)

    res = pipeline.handle_voice_note(note, "919800000001", "wamid.4", CALL_TIME, db=db)

    assert db.get_order(12)["quantity"] == 200 and not [c for c in db.changes if c["order_id"] == 12]
    [p] = db.pending
    assert p["options"] == ["new"] and p["extracted_json"]["item"]["kind"] == "update"
    assert "order nahi mila" in res.pending[0].question
    assert pipeline.resolve_pending(p["id"], "new", db=db).startswith("✅ Naya order")


def test_failed_apply_reopens_pending(db, note, world, monkeypatch):
    world(TRANSCRIPT_NO_KEYTERMS, EXTRACT_NO_KEYTERMS)
    pipeline.handle_voice_note(note, "919800000001", "wamid.2", CALL_TIME, db=db)
    monkeypatch.setattr(db, "update_order", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))

    assert pipeline.resolve_pending(1, "12", db=db).startswith("⚠️")
    assert db.pending[0]["status"] == "pending"


def test_clip_span_falls_back_to_best_segment():
    segs = [{"start": 0, "end": 5, "text": "a b c d e f g h i j"}, {"start": 6, "end": 9, "text": "x y z"}]

    assert pipeline.clip_span("j", segs) == (0, 5)
    assert pipeline.clip_span("nothing here", segs) is None
    assert pipeline.clip_span("", segs) is None


def test_clip_span_grows_across_chunk_boundary():
    segs = [{"start": 0, "end": 4, "text": "intro baat"},
            {"start": 5, "end": 9, "text": "bracket wala order"},
            {"start": 10, "end": 14, "text": "300 kar do rate 42"}]

    assert pipeline.clip_span("bracket wala order 300 kar do", segs) == (5, 14)
