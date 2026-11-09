from datetime import date

import pytest

from app import extract
from app.extract import Extraction, Item
from tests.fakes import (
    BRACKET_ORDER,
    CALL_TIME,
    EXTRACT_KEYTERMS,
    TRANSCRIPT_KEYTERMS,
)


@pytest.fixture
def fake_llm(monkeypatch):
    seen = {}

    def install(result: Extraction):
        def complete_json(system, user, schema):
            seen.update(system=system, user=user, schema=schema)
            return result

        monkeypatch.setattr(extract.llm, "complete_json", complete_json)
        return seen

    return install


def test_extract_keyterms_transcript(fake_llm):
    seen = fake_llm(EXTRACT_KEYTERMS)

    items = extract.extract(
        TRANSCRIPT_KEYTERMS, call_time=CALL_TIME, client_name="Sharma Steels", open_orders=[BRACKET_ORDER]
    )

    update, sheet = items
    assert (update.kind, update.item, update.quantity, update.rate) == ("update", "bracket", 300, 42)
    assert update.changed_fields == ["quantity", "rate"]
    assert update.confidence == 0.9
    # "Friday तक" on Monday 9 Nov resolves to Friday 13 Nov, overriding the LLM's 14th.
    assert sheet.delivery_date == date(2026, 11, 13)
    assert sheet.confidence == 0.9

    assert "2026-11-09 (Monday)" in seen["user"]
    assert "Sharma Steels" in seen["user"]
    assert "#12, bracket, qty 200 pcs, rate 45" in seen["user"]
    assert TRANSCRIPT_KEYTERMS in seen["user"]
    assert seen["schema"] is Extraction


def test_invented_evidence_caps_confidence(fake_llm):
    fake_llm(Extraction(items=[Item(kind="new_order", item="channel", quantity=10,
                                    evidence="das channel bhej do", confidence=0.95)]))

    [item] = extract.extract(TRANSCRIPT_KEYTERMS, call_time=CALL_TIME, client_name=None, open_orders=[])

    assert item.confidence == extract.UNVERIFIED_EVIDENCE_CONFIDENCE


def test_date_without_spoken_phrase_is_dropped(fake_llm):
    fake_llm(Extraction(items=[Item(kind="new_order", item="MS sheet", quantity=50,
                                    delivery_date="2026-11-20", evidence="MS sheet", confidence=0.9)]))

    [item] = extract.extract(TRANSCRIPT_KEYTERMS, call_time=CALL_TIME, client_name=None, open_orders=[])

    assert item.delivery_date is None


def test_update_without_changed_fields_infers_them(fake_llm):
    fake_llm(Extraction(items=[Item(kind="update", item="bracket", quantity=300,
                                    evidence="bracket", confidence=0.9)]))

    [item] = extract.extract(TRANSCRIPT_KEYTERMS, call_time=CALL_TIME, client_name=None, open_orders=[])

    assert item.changed_fields == ["quantity"]


def test_empty_transcript_skips_llm(monkeypatch):
    monkeypatch.setattr(extract.llm, "complete_json", lambda *a: pytest.fail("LLM called"))

    assert extract.extract("  ", call_time=CALL_TIME, client_name=None, open_orders=[]) == []


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("kal tak", date(2026, 11, 10)),
        ("कल भेज देना", date(2026, 11, 10)),
        ("parso", date(2026, 11, 11)),
        ("परसों तक", date(2026, 11, 11)),
        ("aaj hi", date(2026, 11, 9)),
        ("Friday tak", date(2026, 11, 13)),
        ("shukravar", date(2026, 11, 13)),
        ("Monday", date(2026, 11, 16)),  # same weekday means next week
        ("day after tomorrow", date(2026, 11, 11)),
        ("15 tareekh", None),
    ],
)
def test_resolve_date(phrase, expected):
    assert extract.resolve_date(phrase, date(2026, 11, 9)) == expected


def test_resolve_uses_ist_date(fake_llm):
    # 20:00 UTC Sunday 8 Nov is 01:30 IST Monday 9 Nov.
    from datetime import datetime, timezone

    seen = fake_llm(Extraction(items=[]))
    extract.extract("kuch", call_time=datetime(2026, 11, 8, 20, 0, tzinfo=timezone.utc),
                    client_name=None, open_orders=[])

    assert "2026-11-09 (Monday)" in seen["user"]


def test_prompt_has_hindi_number_words_that_sound_alike(fake_llm):
    seen = fake_llm(EXTRACT_KEYTERMS)

    extract.extract(TRANSCRIPT_KEYTERMS, call_time=CALL_TIME, client_name="Sharma Steels",
                    open_orders=[BRACKET_ORDER])

    system = seen["system"]
    for pair in ("छियासठ (chhiyasath) 66", "अड़सठ (adsath) 68", "साठ 60", "सात 7", '"आठ सौ साठ" = 860'):
        assert pair in system
    rows = dict(line.strip().split(": ", 1) for line in system.splitlines()
                if line.strip()[:3] in {"11-", "20s", "30s", "40s", "50s", "60s", "70s", "80s", "90s"})
    assert len(rows["11-19"].split()) == 9
    for decade in ("20s", "30s", "40s", "50s", "60s", "70s", "80s"):
        assert len(rows[decade].split()) == 10, decade  # tens word + x1 .. x9
    assert rows["90s"].split(", ")[0].count(" ") == 9 and rows["90s"].endswith("सौ 100")
