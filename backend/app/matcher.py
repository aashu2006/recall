"""Decide whether an extracted item is a new order or an update, and to which order.

The LLM sees the client's open orders and the item, and returns order_id (or null for a
new order), candidate ids and a confidence. Code then decides:

- "create": new order, confident, nothing in the open orders looks like it
- "update": exactly one candidate, confidence >= MIN_CONFIDENCE, and the order's item name
  was actually said (in item / order_ref / evidence)
- "confirm": anything else. Goes to pending_confirmations, never straight to orders.
"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app import llm, prompts
from app.extract import Item, tokens

MIN_CONFIDENCE = 0.7


class LlmMatch(BaseModel):
    order_id: int | None = None
    candidate_ids: list[int] = []
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


@dataclass
class Decision:
    action: Literal["create", "update", "confirm"]
    order_id: int | None
    confidence: float
    candidate_ids: list[int] = field(default_factory=list)
    reason: str = ""


def match(item: Item, open_orders: list[dict]) -> Decision:
    if not open_orders:
        if item.kind == "new_order" and item.item and item.confidence >= MIN_CONFIDENCE:
            return Decision("create", None, item.confidence, reason="koi open order nahi")
        return Decision("confirm", None, item.confidence, reason="update hai par koi open order nahi"
                        if item.kind == "update" else "extraction pakka nahi")

    by_id = {o["id"]: o for o in open_orders}
    user = prompts.MATCH_USER.format(
        open_orders=prompts.format_orders(open_orders),
        item=item.model_dump_json(include={"kind", "item", "spec", "quantity", "unit", "rate",
                                           "delivery_date", "order_ref", "evidence"}),
    )
    raw = llm.complete_json(prompts.MATCH_SYSTEM, user, LlmMatch)

    order_id = raw.order_id if raw.order_id in by_id else None
    candidates = [c for c in dict.fromkeys(raw.candidate_ids) if c in by_id]
    if order_id is not None and order_id not in candidates:
        candidates.insert(0, order_id)
    confidence = min(raw.confidence, item.confidence)

    if item.kind == "new_order":
        if order_id is None and not candidates and item.item and confidence >= MIN_CONFIDENCE:
            return Decision("create", None, confidence, [], raw.reason)
        return Decision("confirm", order_id, confidence, candidates,
                        raw.reason or "naya order hai ya purane ka update?")

    if order_id is None:
        return Decision("confirm", None, confidence, candidates, raw.reason or "order nahi mila")
    if len(candidates) > 1:
        return Decision("confirm", order_id, confidence, candidates, raw.reason or "ek se zyada order fit")
    if not names_match(by_id[order_id], item):
        return Decision("confirm", order_id, min(confidence, MIN_CONFIDENCE - 0.01), candidates,
                        f"order #{order_id} ka item '{by_id[order_id]['item']}' voice note mein nahi bola")
    if confidence < MIN_CONFIDENCE:
        return Decision("confirm", order_id, confidence, candidates, raw.reason)
    return Decision("update", order_id, confidence, candidates, raw.reason)


def names_match(order: dict, item: Item) -> bool:
    """True if every word of the order's item name was said for this item."""
    target = {_stem(w) for w in tokens(order.get("item") or "")}
    said = {_stem(w) for w in tokens(" ".join(filter(None, [item.item, item.order_ref, item.evidence])))}
    return bool(target) and target <= said


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word
