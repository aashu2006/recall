"""Glue for one voice note: hash -> (cached) stt -> extract -> match -> save or confirm.

handle_voice_note() is called from the webhook BackgroundTask (via whatsapp.py) and from
scripts/run_pipeline.py. Confident items go to orders + order_changes (one RPC = one
transaction each); anything unsure goes to pending_confirmations for the owner's tap.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app import clips, extract, matcher, stt
from app.db import Db, file_sha256, get_db
from app.extract import CHANGE_FIELDS, IST, Item, overlap

log = logging.getLogger(__name__)

CLIP_MIN_GAIN = 0.15  # a neighbour segment joins the proof clip if it adds this much evidence coverage


@dataclass
class Pending:
    id: int
    question: str
    options: list  # order ids (int) and/or "new"; "no" (reject) is always allowed


@dataclass
class PipelineResult:
    call_id: int | None
    order_ids: list[int] = field(default_factory=list)
    pending_ids: list[int] = field(default_factory=list)
    summary: str = ""
    pending: list[Pending] = field(default_factory=list)
    duplicate: bool = False


def handle_voice_note(
    audio_path: str | Path,
    from_phone: str,
    wa_message_id: str | None,
    call_time: datetime | None = None,
    *,
    sender_name: str | None = None,
    db: Db | None = None,
) -> PipelineResult:
    db = db or get_db()
    call_time = call_time or datetime.now(IST)
    if wa_message_id and db.call_by_wa_message_id(wa_message_id):
        log.info("Duplicate wa_message_id %s, skipping", wa_message_id)
        return PipelineResult(call_id=None, duplicate=True)

    client = db.client_by_phone(from_phone) or db.create_client(sender_name or from_phone, from_phone)
    open_orders = db.open_orders(client["id"])

    audio_hash = file_sha256(audio_path)
    cached = db.cached_call(audio_hash)
    if cached:
        log.info("Reusing transcript of call %s (same audio hash)", cached["id"])
        transcript, segments = cached["transcript"], cached.get("segments") or []
        audio_url, duration = cached.get("audio_url"), cached.get("duration_seconds")
    else:
        result = stt.transcribe(audio_path, keyterms=stt.client_keyterms(client, open_orders))
        transcript, segments = result["transcript"], result["segments"]
        audio_url = db.upload_call_audio(audio_path, audio_hash)
        duration = _duration(audio_path)

    call_id = db.insert_call(
        client_id=client["id"], wa_message_id=wa_message_id, from_phone=from_phone,
        audio_url=audio_url, audio_hash=audio_hash, duration_seconds=duration,
        transcript=transcript, segments=segments, created_at=call_time,
    )

    items = extract.extract(transcript, call_time=call_time, client_name=client["name"],
                            open_orders=open_orders)
    orders_by_id = {o["id"]: o for o in open_orders}
    out = PipelineResult(call_id=call_id)
    saved: list[tuple[Item, dict | None]] = []

    for item in items:
        decision = matcher.match(item, open_orders)
        clip = _clip(db, audio_path, audio_hash, item.evidence, segments)
        fields = update_fields(item)
        if decision.action == "create":
            order_id = db.create_order(client["id"], order_fields(item), call_id=call_id, clip=clip,
                                       confidence=decision.confidence)
            out.order_ids.append(order_id)
            saved.append((item, None))
        elif decision.action == "update" and fields and decision.order_id in orders_by_id:
            db.update_order(decision.order_id, fields, call_id=call_id, clip=clip,
                            confidence=decision.confidence)
            out.order_ids.append(decision.order_id)
            saved.append((item, orders_by_id[decision.order_id]))
        else:  # unsure, or an update with no open order to apply it to: ask the owner, never drop
            question, options = owner_question(client["name"], item, decision, orders_by_id)
            pending_id = db.insert_pending(
                call_id=call_id, client_id=client["id"], question=question, options=options,
                extracted={"item": item.model_dump(mode="json"), "clip": clip,
                           "decision": {"order_id": decision.order_id, "candidate_ids": decision.candidate_ids,
                                        "confidence": decision.confidence, "reason": decision.reason}},
            )
            out.pending_ids.append(pending_id)
            out.pending.append(Pending(pending_id, question, options))

    out.summary = client_summary(client["name"], saved, len(out.pending_ids), bool(items))
    return out


def resolve_pending(pending_id: int, choice: str, db: Db | None = None) -> str:
    """Owner tapped a button. choice: an order id, "new" or "no". Returns a reply for the owner."""
    db = db or get_db()
    row = db.get_pending(pending_id)
    if not row:
        return f"Pending #{pending_id} nahi mila."
    if choice != "no" and choice not in {str(o) for o in row.get("options") or []}:
        return f"Pending #{pending_id}: ye option valid nahi hai."
    status = "rejected" if choice == "no" else "confirmed"
    if not db.resolve_pending(pending_id, status):
        return f"Pending #{pending_id} pehle hi {row.get('status')} hai."
    if choice == "no":
        return f"❌ Theek hai, #{pending_id} ignore kar diya."

    item = Item.model_validate(row["extracted_json"]["item"])
    clip = row["extracted_json"].get("clip")
    try:
        if choice == "new":
            order_id = db.create_order(row["client_id"], order_fields(item), call_id=row["call_id"],
                                       clip=clip, confidence=1.0)
            return f"✅ Naya order #{order_id} bana diya: {describe(item)}"
        order_id = int(choice)
        db.update_order(order_id, update_fields(item), call_id=row["call_id"], clip=clip, confidence=1.0)
        return f"✅ Order #{order_id} update ho gaya: {describe(item)}"
    except Exception:
        log.exception("Applying pending %s failed", pending_id)
        db.reopen_pending(pending_id)
        return f"⚠️ #{pending_id} save nahi hua, thodi der baad dobara try karein."


def order_fields(item: Item) -> dict:
    return {
        "item": item.item or item.order_ref or "(naam saaf nahi)",
        "spec": item.spec, "quantity": item.quantity, "unit": item.unit,
        "rate": item.rate, "delivery_date": item.delivery_date,
    }


def update_fields(item: Item) -> dict:
    """Fields to write on an existing order: what the client changed, never nulls."""
    names = item.changed_fields or [f for f in CHANGE_FIELDS if getattr(item, f) is not None]
    return {f: getattr(item, f) for f in names if getattr(item, f) is not None}


def clip_span(evidence: str, segments: list[dict]) -> tuple[float, float] | None:
    """Start/end of the segment(s) holding the evidence words, or None if not found.

    Takes the segment covering most of the evidence, then grows to neighbours only while
    each one adds at least CLIP_MIN_GAIN coverage (evidence can span a chunk boundary).
    """
    def cover(lo: int, hi: int) -> float:
        return overlap(evidence, " ".join(s["text"] for s in segments[lo : hi + 1]))

    if not evidence or not segments:
        return None
    best = max(range(len(segments)), key=lambda i: cover(i, i))
    if cover(best, best) == 0.0:
        return None
    lo = hi = best
    while True:
        here = cover(lo, hi)
        options = [(cover(lo - 1, hi), lo - 1, hi)] if lo > 0 else []
        options += [(cover(lo, hi + 1), lo, hi + 1)] if hi < len(segments) - 1 else []
        gain, new_lo, new_hi = max(options, default=(here, lo, hi))
        if gain - here < CLIP_MIN_GAIN:
            break
        lo, hi = new_lo, new_hi
    return segments[lo]["start"], segments[hi]["end"]


def _clip(db: Db, audio_path, audio_hash: str, evidence: str, segments: list[dict]) -> dict | None:
    span = clip_span(evidence, segments)
    if not span:
        return None
    clip = {"start": span[0], "end": span[1], "path": None}
    try:
        clip["path"] = db.upload_clip(audio_path, audio_hash, *span)
    except Exception:
        log.exception("Proof clip %s-%s failed, saving without it", *span)
    return clip


def _duration(audio_path) -> float | None:
    try:
        return clips.duration(audio_path)
    except Exception:
        log.warning("Could not read duration of %s", audio_path)
        return None


def _num(value) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"


def describe(item: Item) -> str:
    parts = [item.item or item.order_ref or "item"]
    if item.spec:
        parts.append(item.spec)
    if item.quantity is not None:
        parts.append(f"{_num(item.quantity)} {item.unit or ''}".strip())
    if item.rate is not None:
        parts.append(f"₹{_num(item.rate)} rate")
    if item.delivery_date:
        parts.append(f"delivery {item.delivery_date.strftime('%d %b (%a)')}")
    return ", ".join(parts)


def client_summary(client_name: str, saved: list[tuple[Item, dict | None]], pending: int,
                   anything: bool) -> str:
    lines = [f"Namaste {client_name} ji, aapka voice note mil gaya."]
    for item, order in saved:
        if order is None:
            lines.append(f"✅ Naya order: {describe(item)}")
        else:
            changes = describe(item.model_copy(update={
                f: None for f in CHANGE_FIELDS if f not in item.changed_fields}))
            lines.append(f"✅ Order #{order['id']} ({order['item']}) update: {changes}")
    if pending:
        lines.append(f"⏳ {pending} baat owner se confirm karke batayenge.")
    if not anything:
        lines.append("Isme koi order samajh nahi aaya. Owner aapse baat karenge.")
    return "\n".join(lines)


def owner_question(client_name: str, item: Item, decision: matcher.Decision,
                   orders_by_id: dict[int, dict]) -> tuple[str, list]:
    """Question text + button options (max 2 choices, plus reject) for the owner."""
    said = f'"{item.evidence}"' if item.evidence else ""
    what = describe(item)
    cands = decision.candidate_ids[:2]
    if item.kind == "update":
        if cands:
            names = ", ".join(f"#{c} {orders_by_id[c]['item']} {_num(orders_by_id[c]['quantity'] or 0)}"
                              for c in cands)
            q = f"{client_name}: update ({what}). Kaunse order ka hai? {names}\n{said}"
            return q, cands
        return f"{client_name}: update bola ({what}) par order nahi mila. Naya order bana dein?\n{said}", ["new"]
    if cands:
        return (f"{client_name}: naya order ({what}) ya #{cands[0]} ka update?\n{said}", ["new", cands[0]])
    return f"{client_name}: naya order ({what}). Sahi hai?\n{said}", ["new"]
