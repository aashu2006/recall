"""WhatsApp Cloud API: send text, buttons and voice notes, download inbound media, and
process webhook payloads (runs in the BackgroundTask started by main.py).

Every outbound send counts against the hard daily cap WA_DAILY_SEND_CAP (Asia/Kolkata
day), logged in the wa_sends table so restarts don't reset it.

Owner buttons carry ids like "pc:<pending_id>:<choice>", choice = order id, "new" or "no".
"""

import hashlib
import hmac
import logging
import tempfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

import httpx

from app import pipeline
from app.config import Settings, get_settings
from app.db import Db, get_db, normalize_phone
from app.extract import IST

log = logging.getLogger(__name__)

MIME_EXT = {"audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/aac": ".aac",
            "audio/amr": ".amr", "audio/wav": ".wav"}
BUTTON_TITLE_MAX = 20
BODY_MAX = 1024
SEEN_MAX = 1000


class WhatsAppError(Exception):
    pass


def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """Check Meta's X-Hub-Signature-256 ("sha256=<hex hmac of the raw body>")."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


class WhatsApp:
    def __init__(self, settings: Settings | None = None, db: Db | None = None,
                 client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        self.db = db or get_db()
        self.http = client or httpx.Client(timeout=30)
        s = self.settings
        self.base = f"{s.wa_graph_base_url.rstrip('/')}/{s.wa_graph_api_version}"
        self.auth = {"Authorization": f"Bearer {s.wa_token}"}

    # inbound media
    def download_media(self, media_id: str, dest_dir: str | Path) -> Path:
        meta = self._check(self.http.get(f"{self.base}/{media_id}", headers=self.auth)).json()
        mime = (meta.get("mime_type") or "").split(";")[0].strip()
        data = self._check(self.http.get(meta["url"], headers=self.auth)).content
        path = Path(dest_dir) / f"{media_id}{MIME_EXT.get(mime, '.ogg')}"
        path.write_bytes(data)
        return path

    # outbound
    def send_text(self, to: str, text: str) -> str | None:
        return self._send(to, "text", {"type": "text", "text": {"body": text[:4096]}})

    def send_buttons(self, to: str, body: str, buttons: list[tuple[str, str]]) -> str | None:
        """buttons: up to 3 (id, title). Titles are cut to WhatsApp's 20 chars."""
        return self._send(to, "buttons", {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body[:BODY_MAX]},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": bid, "title": title[:BUTTON_TITLE_MAX]}}
                    for bid, title in buttons[:3]
                ]},
            },
        })

    def send_audio(self, to: str, ogg_path: str | Path) -> str | None:
        """Upload an OGG/Opus file and send it as a voice note."""
        if self._capped():
            return None
        r = self.http.post(
            f"{self.base}/{self.settings.wa_phone_number_id}/media", headers=self.auth,
            data={"messaging_product": "whatsapp", "type": "audio/ogg"},
            files={"file": (Path(ogg_path).name, Path(ogg_path).read_bytes(), "audio/ogg")},
        )
        media_id = self._check(r).json()["id"]
        return self._send(to, "audio", {"type": "audio", "audio": {"id": media_id}})

    def _send(self, to: str, kind: str, message: dict) -> str | None:
        if self._capped():
            return None
        to = normalize_phone(to)
        r = self.http.post(
            f"{self.base}/{self.settings.wa_phone_number_id}/messages", headers=self.auth,
            json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **message},
        )
        wa_id = (self._check(r).json().get("messages") or [{}])[0].get("id")
        self.db.record_send(to, kind, wa_id)
        return wa_id

    def _capped(self) -> bool:
        today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        sent = self.db.sends_since(today)
        if sent >= self.settings.wa_daily_send_cap:
            log.warning("WA_DAILY_SEND_CAP reached (%d sent today), not sending", sent)
            return True
        return False

    @staticmethod
    def _check(r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            raise WhatsAppError(f"Graph API {r.status_code}: {r.text[:300]}")
        return r


# webhook processing

_seen: OrderedDict[str, None] = OrderedDict()  # message ids handled by this process


def _first_time(message_id: str) -> bool:
    if message_id in _seen:
        return False
    _seen[message_id] = None
    while len(_seen) > SEEN_MAX:
        _seen.popitem(last=False)
    return True


def process_webhook(payload: dict, *, wa: WhatsApp | None = None, db: Db | None = None) -> None:
    """Handle every message in a webhook payload. Never raises (it's a background task)."""
    for change in (c for e in payload.get("entry", []) for c in e.get("changes", [])):
        value = change.get("value", {})
        names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
        for message in value.get("messages", []):
            try:
                if not _first_time(message.get("id", "")):
                    continue
                wa = wa or WhatsApp(db=db)
                db = db or wa.db
                if message.get("type") == "audio":
                    _handle_voice(message, names.get(message.get("from")), wa, db)
                elif message.get("type") == "interactive":
                    _handle_button(message, wa, db)
                else:
                    log.info("Ignoring %s message %s", message.get("type"), message.get("id"))
            except Exception:
                log.exception("Failed to process message %s", message.get("id"))


def _handle_voice(message: dict, sender_name: str | None, wa: WhatsApp, db: Db) -> None:
    msg_id, sender = message["id"], message["from"]
    if db.call_by_wa_message_id(msg_id):
        log.info("Duplicate voice note %s, skipping", msg_id)
        return
    call_time = datetime.fromtimestamp(int(message.get("timestamp") or datetime.now().timestamp()), IST)
    with tempfile.TemporaryDirectory(prefix="recall-wa-") as tmp:
        audio = wa.download_media(message["audio"]["id"], tmp)
        try:
            result = pipeline.handle_voice_note(audio, sender, msg_id, call_time,
                                                sender_name=sender_name, db=db)
        except Exception:
            owner = wa.settings.owner_wa_number
            if owner:
                wa.send_text(owner, f"⚠️ {sender_name or sender} ka voice note process nahi hua. Logs dekhein.")
            raise
    if result.duplicate:
        return
    try:
        wa.send_text(sender, result.summary)
    except Exception:  # e.g. sender not on the test number's allowed list; owner still gets the buttons
        log.exception("Summary to %s failed", sender)
    owner = wa.settings.owner_wa_number
    if not owner:
        if result.pending:
            log.warning("OWNER_WA_NUMBER not set, %d pending items not sent", len(result.pending))
        return
    for p in result.pending:
        wa.send_buttons(owner, p.question, owner_buttons(p))


def owner_buttons(p: pipeline.Pending) -> list[tuple[str, str]]:
    buttons = []
    for opt in p.options[:2]:
        title = "✅ Naya order" if opt == "new" else f"Order #{opt}"
        buttons.append((f"pc:{p.id}:{opt}", title))
    buttons.append((f"pc:{p.id}:no", "❌ Nahi"))
    return buttons


def _handle_button(message: dict, wa: WhatsApp, db: Db) -> None:
    reply = (message.get("interactive") or {}).get("button_reply") or {}
    owner = normalize_phone(wa.settings.owner_wa_number)
    if not owner or normalize_phone(message.get("from", "")) != owner:
        log.warning("Button reply from non-owner %s ignored", message.get("from"))
        return
    parts = (reply.get("id") or "").split(":")
    if len(parts) != 3 or parts[0] != "pc" or not parts[1].isdigit():
        log.warning("Unknown button id %r", reply.get("id"))
        return
    wa.send_text(owner, pipeline.resolve_pending(int(parts[1]), parts[2], db=db))
