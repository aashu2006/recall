"""Morning briefing for the owner: today's and tomorrow's deliveries and pending items as
short Hinglish text, rendered to a voice note with Timbre and sent on WhatsApp.

Two versions of the text: `text` with digits (WhatsApp fallback if TTS fails) and
`spoken` with numbers as words (Timbre reads words more naturally).
"""

import logging
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from app import tts
from app.db import Db
from app.extract import IST

log = logging.getLogger(__name__)

MAX_PER_DAY = 5  # orders read out per day, the rest are "aur N"
UNIT_WORDS = {"pcs": "pieces", "pc": "pieces", "piece": "pieces", "kg": "kilo", "ton": "ton",
              "mtr": "meter", "m": "meter"}


@dataclass
class Briefing:
    text: str
    spoken: str


def build(db: Db, today: date | None = None) -> Briefing:
    today = today or datetime.now(IST).date()
    days = [("Aaj", db.deliveries_between(today, today)),
            ("Kal", db.deliveries_between(today + timedelta(days=1), today + timedelta(days=1)))]
    pending = db.list_pending()

    text = ["Good morning! 🌅"]
    spoken = ["Good morning."]
    for label, orders in days:
        if not orders:
            text.append(f"{label} koi delivery nahi.")
            spoken.append(f"{label} koi delivery nahi hai.")
            continue
        n = len(orders)
        text.append(f"{label} {n} delivery:")
        spoken.append(f"{label} {words(n)} {'delivery hai' if n == 1 else 'deliveries hain'}.")
        for o in orders[:MAX_PER_DAY]:
            client = (o.get("clients") or {}).get("name") or "client"
            text.append(f"• {client}: {_line(o, spoken=False)}")
            spoken.append(f"{client} ko {_line(o, spoken=True)}.")
        if n > MAX_PER_DAY:
            text.append(f"…aur {n - MAX_PER_DAY}")
            spoken.append(f"Aur {words(n - MAX_PER_DAY)} orders.")
    if pending:
        p = len(pending)
        text.append(f"⏳ {p} item aapke confirm ka wait kar {'raha hai' if p == 1 else 'rahe hain'}.")
        spoken.append(f"{words(p)} {'item' if p == 1 else 'items'} aapke confirmation ka wait kar "
                      f"{'raha hai' if p == 1 else 'rahe hain'}, WhatsApp pe buttons dekh lijiye.")
    return Briefing("\n".join(text), " ".join(spoken))


def send(db: Db, wa, today: date | None = None) -> dict:
    """Build the briefing and send it to OWNER_WA_NUMBER as a voice note (text if TTS fails)."""
    owner = wa.settings.owner_wa_number
    if not owner:
        raise RuntimeError("OWNER_WA_NUMBER is not set")
    b = build(db, today)
    try:
        audio = tts.synthesize(b.spoken, settings=wa.settings)
    except Exception:
        log.exception("Timbre failed, sending briefing as text")
        return {"text": b.text, "sent": "text" if wa.send_text(owner, b.text) else None}
    with tempfile.TemporaryDirectory(prefix="recall-brief-") as tmp:
        path = Path(tmp) / "briefing.ogg"
        path.write_bytes(audio)
        return {"text": b.text, "sent": "audio" if wa.send_audio(owner, path) else None}


def _line(o: dict, *, spoken: bool) -> str:
    qty, unit, item = o.get("quantity"), o.get("unit") or "", o.get("item") or ""
    spec = o.get("spec")
    what = f"{spec} {item}".strip() if spec and spoken else item
    if qty is None:
        return what
    if spoken:
        return f"{words(qty)} {UNIT_WORDS.get(unit.lower(), unit)} {what}".replace("  ", " ")
    return f"{item}{f' ({spec})' if spec else ''} {_num(qty)} {unit}".strip()


def _num(value) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"


_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
         "fifteen sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def words(value) -> str:
    """Number -> English words, the way Hinglish speakers say quantities ("three hundred")."""
    f = float(value)
    if not f.is_integer():
        whole, frac = _num(f).split(".")
        return f"{words(int(whole))} point {' '.join(_ONES[int(d)] for d in frac)}"
    n = int(f)
    if n < 0:
        return "minus " + words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else f" {_ONES[n % 10]}")
    for size, name in ((10_000_000, "crore"), (100_000, "lakh"), (1000, "thousand"), (100, "hundred")):
        if n >= size:
            rest = n % size
            return f"{words(n // size)} {name}" + (f" {words(rest)}" if rest else "")
    raise AssertionError("unreachable")
