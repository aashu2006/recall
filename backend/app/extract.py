"""Transcript -> list of extracted items (pydantic models).

Each item is a new order or an update to an existing one, with the exact words it came
from (evidence) and a confidence. Prompts are in prompts.py, in Hinglish.

Guards on top of the LLM (never silently guess):
- delivery dates are resolved in code from the client's own words ("Friday tak", "kal",
  "parso") against the call time in Asia/Kolkata; a date with no spoken phrase is dropped
- evidence that is not in the transcript caps confidence below the auto-save threshold
"""

import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app import llm, prompts

IST = ZoneInfo("Asia/Kolkata")
UNVERIFIED_EVIDENCE_CONFIDENCE = 0.5
EVIDENCE_MIN_OVERLAP = 0.6

ChangeField = Literal["quantity", "unit", "rate", "delivery_date", "spec"]
CHANGE_FIELDS: tuple[str, ...] = ("quantity", "unit", "rate", "delivery_date", "spec")


class Item(BaseModel):
    kind: Literal["new_order", "update"]
    item: str | None = None
    spec: str | None = None
    quantity: float | None = None
    unit: str | None = None
    rate: float | None = None
    delivery_date: date | None = None
    delivery_phrase: str | None = None
    changed_fields: list[ChangeField] = []
    order_ref: str | None = None
    evidence: str = ""
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    items: list[Item]


def extract(
    transcript: str,
    *,
    call_time: datetime,
    client_name: str | None,
    open_orders: list[dict],
) -> list[Item]:
    if not transcript.strip():
        return []
    call_date = call_time.astimezone(IST).date()
    user = prompts.EXTRACT_USER.format(
        call_date=call_date.isoformat(),
        weekday=call_date.strftime("%A"),
        client_name=client_name or "(pata nahi)",
        open_orders=prompts.format_orders(open_orders),
        transcript=transcript,
    )
    result = llm.complete_json(prompts.EXTRACT_SYSTEM, user, Extraction)
    return [_post_process(item, transcript, call_date) for item in result.items]


def _post_process(item: Item, transcript: str, call_date: date) -> Item:
    item = item.model_copy(deep=True)
    if item.delivery_phrase:
        resolved = resolve_date(item.delivery_phrase, call_date)
        if resolved:
            item.delivery_date = resolved
    else:
        item.delivery_date = None  # a date nobody said is an invented date
    if item.kind == "new_order":
        item.changed_fields = []
    elif not item.changed_fields:
        item.changed_fields = [f for f in CHANGE_FIELDS if getattr(item, f) is not None]
    if overlap(item.evidence, transcript) < EVIDENCE_MIN_OVERLAP:
        item.confidence = min(item.confidence, UNVERIFIED_EVIDENCE_CONFIDENCE)
    return item


_OFFSETS = {
    "aaj": 0, "aj": 0, "आज": 0, "today": 0,
    "kal": 1, "कल": 1, "tomorrow": 1,
    "parso": 2, "parson": 2, "parsoon": 2, "परसों": 2, "परसो": 2,
}
_WEEKDAYS = {
    0: ("monday", "somvar", "somwar", "सोमवार", "मंडे"),
    1: ("tuesday", "mangalvar", "mangalwar", "मंगलवार", "ट्यूज़डे"),
    2: ("wednesday", "budhvar", "budhwar", "बुधवार", "वेडनेसडे"),
    3: ("thursday", "guruvar", "guruwar", "brihaspativar", "गुरुवार", "बृहस्पतिवार", "थर्सडे"),
    4: ("friday", "shukravar", "shukrawar", "शुक्रवार", "फ्राइडे"),
    5: ("saturday", "shanivar", "shaniwar", "शनिवार", "सैटरडे"),
    6: ("sunday", "ravivar", "raviwar", "itvaar", "itwar", "रविवार", "इतवार", "संडे"),
}


def resolve_date(phrase: str, call_date: date) -> date | None:
    """Resolve "kal", "parso", "Friday tak" etc. against the call date. None if unknown.

    A weekday means its next occurrence after the call date (never the call day itself).
    "day after tomorrow" is checked before "tomorrow".
    """
    text = phrase.casefold()
    if "day after tomorrow" in text:
        return call_date + timedelta(days=2)
    words = tokens(text)
    for word in words:
        if word in _OFFSETS:
            return call_date + timedelta(days=_OFFSETS[word])
    for weekday, names in _WEEKDAYS.items():
        if any(name in words for name in names):
            ahead = (weekday - call_date.weekday()) % 7 or 7
            return call_date + timedelta(days=ahead)
    return None


_TOKEN = re.compile(r"[^\s,.;:?!।|\"'()\[\]]+")


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.casefold())


def overlap(needle: str, haystack: str) -> float:
    """Share of needle's words that appear in haystack (0 if needle is empty)."""
    words = tokens(needle)
    if not words:
        return 0.0
    hay = set(tokens(haystack))
    return sum(w in hay for w in words) / len(words)
