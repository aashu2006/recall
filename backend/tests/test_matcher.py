import pytest

from app import extract, matcher
from app.matcher import LlmMatch
from tests.fakes import (
    ANGLE_ORDER,
    BRACKET_ORDER,
    CALL_TIME,
    EXTRACT_KEYTERMS,
    EXTRACT_NO_KEYTERMS,
    SHEET_ITEM,
    TRANSCRIPT_KEYTERMS,
    TRANSCRIPT_NO_KEYTERMS,
)

OPEN_ORDERS = [BRACKET_ORDER, ANGLE_ORDER]


@pytest.fixture
def fake_llm(monkeypatch):
    """Extraction returns `extraction`; matching returns `match`. Records match prompts."""
    prompts = []

    def install(extraction, match: LlmMatch | None = None):
        def complete_json(system, user, schema):
            if schema is extract.Extraction:
                return extraction
            prompts.append(user)
            return match

        monkeypatch.setattr(extract.llm, "complete_json", complete_json)
        return prompts

    return install


def extract_update(transcript):
    items = extract.extract(transcript, call_time=CALL_TIME, client_name="Sharma Steels",
                            open_orders=OPEN_ORDERS)
    return next(i for i in items if i.kind == "update")


def test_keyterms_transcript_matches_200_bracket_order(fake_llm):
    prompts = fake_llm(EXTRACT_KEYTERMS, LlmMatch(order_id=12, candidate_ids=[12], confidence=0.92))

    decision = matcher.match(extract_update(TRANSCRIPT_KEYTERMS), OPEN_ORDERS)

    assert decision.action == "update"
    assert decision.order_id == 12
    assert decision.confidence == pytest.approx(0.9)
    assert "#12, bracket, qty 200 pcs, rate 45" in prompts[0]
    assert "#14, angle" in prompts[0]


@pytest.mark.parametrize(
    "llm_answer",
    [
        LlmMatch(order_id=12, candidate_ids=[12], confidence=0.55),  # honest LLM
        LlmMatch(order_id=12, candidate_ids=[12], confidence=0.95),  # overconfident LLM
        LlmMatch(order_id=None, candidate_ids=[12, 14], confidence=0.4),
    ],
)
def test_no_keyterms_transcript_goes_to_pending(fake_llm, llm_answer):
    fake_llm(EXTRACT_NO_KEYTERMS, llm_answer)

    decision = matcher.match(extract_update(TRANSCRIPT_NO_KEYTERMS), OPEN_ORDERS)

    assert decision.action == "confirm"
    assert decision.confidence < matcher.MIN_CONFIDENCE
    assert 12 in decision.candidate_ids


def test_two_bracket_orders_are_ambiguous(fake_llm):
    second = {**BRACKET_ORDER, "id": 15, "quantity": 100}
    fake_llm(EXTRACT_KEYTERMS, LlmMatch(order_id=12, candidate_ids=[12, 15], confidence=0.8))

    decision = matcher.match(extract_update(TRANSCRIPT_KEYTERMS), [BRACKET_ORDER, second])

    assert decision.action == "confirm"
    assert decision.candidate_ids == [12, 15]


def test_unknown_order_id_from_llm_is_ignored(fake_llm):
    fake_llm(EXTRACT_KEYTERMS, LlmMatch(order_id=999, candidate_ids=[999], confidence=0.9))

    decision = matcher.match(extract_update(TRANSCRIPT_KEYTERMS), OPEN_ORDERS)

    assert (decision.action, decision.order_id, decision.candidate_ids) == ("confirm", None, [])


def test_new_order_is_created(fake_llm):
    fake_llm(None, LlmMatch(order_id=None, candidate_ids=[], confidence=0.9))

    assert matcher.match(SHEET_ITEM, OPEN_ORDERS).action == "create"


def test_new_order_that_looks_like_existing_needs_confirmation(fake_llm):
    fake_llm(None, LlmMatch(order_id=None, candidate_ids=[14], confidence=0.8))

    decision = matcher.match(SHEET_ITEM, OPEN_ORDERS)

    assert decision.action == "confirm" and decision.candidate_ids == [14]


def test_no_open_orders_skips_llm(monkeypatch):
    monkeypatch.setattr(extract.llm, "complete_json", lambda *a: pytest.fail("LLM called"))

    assert matcher.match(SHEET_ITEM, []).action == "create"
    update = EXTRACT_KEYTERMS.items[0]
    assert matcher.match(update, []).action == "confirm"
    low = SHEET_ITEM.model_copy(update={"confidence": 0.5})
    assert matcher.match(low, []).action == "confirm"


def test_names_match_handles_plural_and_multiword():
    item = SHEET_ITEM.model_copy(update={"item": "MS sheets", "evidence": ""})

    assert matcher.names_match({"item": "MS sheet"}, item)
    assert not matcher.names_match({"item": "bracket"}, item)
