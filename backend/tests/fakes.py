"""Canned LLM outputs for the two real Prisma transcripts in fixtures/.

Both are the same voice note: transcript_keyterms.txt was transcribed with client keyterms
("bracket" heard right), transcript_no_keyterms.txt without ("bracket" heard as "डाला").
"""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.extract import Extraction, Item

FIXTURES = Path(__file__).parent / "fixtures"
TRANSCRIPT_KEYTERMS = (FIXTURES / "transcript_keyterms.txt").read_text().strip()
TRANSCRIPT_NO_KEYTERMS = (FIXTURES / "transcript_no_keyterms.txt").read_text().strip()

# Monday 9 Nov 2026, 10:30 IST
CALL_TIME = datetime(2026, 11, 9, 10, 30, tzinfo=ZoneInfo("Asia/Kolkata"))

BRACKET_ORDER = {
    "id": 12, "client_id": 1, "item": "bracket", "spec": None, "quantity": 200, "unit": "pcs",
    "rate": 45, "delivery_date": "2026-11-20", "status": "open",
}
ANGLE_ORDER = {
    "id": 14, "client_id": 1, "item": "angle", "spec": "40x40x5", "quantity": 500, "unit": "kg",
    "rate": 62, "delivery_date": "2026-11-10", "status": "open",
}
SHARMA = {"id": 1, "name": "Sharma Steels", "phone": "919800000001", "aliases": ["Sharma ji"]}

SHEET_ITEM = Item(
    kind="new_order", item="MS sheet", spec="3mm MS", quantity=50, unit="pcs",
    delivery_phrase="Friday तक", delivery_date="2026-11-14",  # LLM got the date wrong on purpose
    evidence="three mm MS sheet के fifty piece चाहिए। Friday तक भेज देना", confidence=0.9,
)

EXTRACT_KEYTERMS = Extraction(items=[
    Item(
        kind="update", item="bracket", quantity=300, rate=42, changed_fields=["quantity", "rate"],
        order_ref="दो सौ bracket वाला order",
        evidence="वो दो सौ bracket वाला order है ना, उसको three hundred कर दो and rate भी। "
                 "forty five की जगह forty two रुपये लगा देना",
        confidence=0.9,
    ),
    SHEET_ITEM,
])

EXTRACT_NO_KEYTERMS = Extraction(items=[
    Item(
        kind="update", item="डाला", quantity=300, rate=42, changed_fields=["quantity", "rate"],
        order_ref="दो सौ रुपए का डाला order",
        evidence="वो दो सौ रुपए का डाला order है ना, उसको three hundred कर दो and rate भी। "
                 "forty five की जगह forty two रुपये लगा देना",
        confidence=0.75,
    ),
    SHEET_ITEM,
])
