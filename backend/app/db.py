"""Supabase client (service key, server side only).

Rule: never update orders without inserting a matching order_changes row in the same
transaction. Orders are only written through the create_order / update_order Postgres
functions (supabase/migrations/002), which do both in one transaction.

Audio lives in the private "audio" bucket. calls.audio_url and order_changes.clip_path
hold object paths in that bucket (the dashboard makes signed URLs).
"""

import hashlib
import re
import tempfile
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app import clips
from app.config import Settings, get_settings

ORDER_FIELDS = ("item", "spec", "quantity", "unit", "rate", "delivery_date")
AUDIO_TYPES = {".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mpeg", ".wav": "audio/wav",
               ".m4a": "audio/mp4", ".aac": "audio/aac", ".amr": "audio/amr"}


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def normalize_phone(phone: str) -> str:
    """WhatsApp style: digits only, with country code, no +."""
    return re.sub(r"\D", "", phone or "")


def _clean(value: Any) -> Any:
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _clean_fields(fields: dict) -> dict:
    return {k: _clean(v) for k, v in fields.items()}


def _one(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


class Db:
    def __init__(self, client, bucket: str = "audio"):
        self.sb = client
        self.bucket = bucket

    # clients
    def client_by_phone(self, phone: str) -> dict | None:
        res = self.sb.table("clients").select("*").eq("phone", normalize_phone(phone)).limit(1).execute()
        return _one(res.data)

    def get_client(self, client_id: int) -> dict | None:
        return _one(self.sb.table("clients").select("*").eq("id", client_id).limit(1).execute().data)

    def create_client(self, name: str, phone: str | None, aliases: list[str] | None = None) -> dict:
        row = {"name": name, "phone": normalize_phone(phone) if phone else None, "aliases": aliases or []}
        return self.sb.table("clients").insert(row).execute().data[0]

    # orders (writes only through the RPCs)
    def open_orders(self, client_id: int) -> list[dict]:
        res = (
            self.sb.table("orders").select("*").eq("client_id", client_id).eq("status", "open")
            .order("id").execute()
        )
        return res.data

    def get_order(self, order_id: int) -> dict | None:
        return _one(self.sb.table("orders").select("*").eq("id", order_id).limit(1).execute().data)

    def create_order(self, client_id: int, fields: dict, *, call_id: int | None = None,
                     clip: dict | None = None, confidence: float | None = None) -> int:
        payload = {k: v for k, v in _clean_fields(fields).items() if k in ORDER_FIELDS}
        return self.sb.rpc("create_order", {
            "p_client_id": client_id, "p_fields": payload, "p_call_id": call_id,
            **_clip_args(clip), "p_confidence": confidence,
        }).execute().data

    def update_order(self, order_id: int, fields: dict, *, call_id: int | None = None,
                     clip: dict | None = None, confidence: float | None = None) -> int:
        """Apply changed fields; returns how many actually changed (one order_changes row each)."""
        payload = _clean_fields(fields)
        if not payload:
            return 0
        return self.sb.rpc("update_order", {
            "p_order_id": order_id, "p_fields": payload, "p_call_id": call_id,
            **_clip_args(clip), "p_confidence": confidence,
        }).execute().data

    def deliveries_between(self, start: date, end: date) -> list[dict]:
        """Open orders with delivery_date in [start, end], with the client's name."""
        res = (
            self.sb.table("orders").select("*, clients(name)").eq("status", "open")
            .gte("delivery_date", start.isoformat()).lte("delivery_date", end.isoformat())
            .order("delivery_date").order("id").execute()
        )
        return res.data

    # calls
    def call_by_wa_message_id(self, wa_message_id: str) -> dict | None:
        res = self.sb.table("calls").select("id").eq("wa_message_id", wa_message_id).limit(1).execute()
        return _one(res.data)

    def cached_call(self, audio_hash: str) -> dict | None:
        """Most recent call with this audio and a transcript, so we never re-transcribe."""
        res = (
            self.sb.table("calls").select("id, transcript, segments, audio_url, duration_seconds")
            .eq("audio_hash", audio_hash).not_.is_("transcript", "null")
            .order("id", desc=True).limit(1).execute()
        )
        return _one(res.data)

    def insert_call(self, **fields) -> int:
        return self.sb.table("calls").insert(_clean_fields(fields)).execute().data[0]["id"]

    # pending confirmations
    def insert_pending(self, *, call_id: int | None, client_id: int | None, extracted: dict,
                       question: str, options: list | None) -> int:
        row = {"call_id": call_id, "client_id": client_id, "extracted_json": extracted,
               "question": question, "options": options}
        return self.sb.table("pending_confirmations").insert(row).execute().data[0]["id"]

    def get_pending(self, pending_id: int) -> dict | None:
        res = self.sb.table("pending_confirmations").select("*").eq("id", pending_id).limit(1).execute()
        return _one(res.data)

    def list_pending(self) -> list[dict]:
        res = (
            self.sb.table("pending_confirmations").select("*, clients(name)").eq("status", "pending")
            .order("id").execute()
        )
        return res.data

    def resolve_pending(self, pending_id: int, status: str) -> bool:
        """Mark pending -> confirmed/rejected. False if it was already resolved (double tap)."""
        res = (
            self.sb.table("pending_confirmations")
            .update({"status": status, "resolved_at": datetime.now().astimezone().isoformat()})
            .eq("id", pending_id).eq("status", "pending").execute()
        )
        return bool(res.data)

    def reopen_pending(self, pending_id: int) -> None:
        """Undo a resolve when applying the owner's choice failed, so they can tap again."""
        self.sb.table("pending_confirmations").update({"status": "pending", "resolved_at": None}) \
            .eq("id", pending_id).execute()

    # whatsapp send log (daily cap)
    def sends_since(self, since: datetime) -> int:
        res = (
            self.sb.table("wa_sends").select("id", count="exact")
            .gte("created_at", since.isoformat()).limit(1).execute()
        )
        return res.count or 0

    def record_send(self, to_phone: str, kind: str, wa_message_id: str | None = None) -> None:
        self.sb.table("wa_sends").insert(
            {"to_phone": to_phone, "kind": kind, "wa_message_id": wa_message_id}
        ).execute()

    # storage
    def upload(self, object_path: str, local_path: str | Path, content_type: str) -> str:
        self.sb.storage.from_(self.bucket).upload(
            object_path, Path(local_path).read_bytes(),
            {"content-type": content_type, "upsert": "true"},
        )
        return object_path

    def upload_call_audio(self, audio_path: str | Path, audio_hash: str) -> str:
        """Original voice note -> calls/<hash><ext>. Same audio, same path (upsert)."""
        ext = Path(audio_path).suffix.lower() or ".ogg"
        return self.upload(f"calls/{audio_hash}{ext}", audio_path, AUDIO_TYPES.get(ext, "application/octet-stream"))

    def upload_clip(self, audio_path: str | Path, audio_hash: str, start: float, end: float) -> str:
        """Cut [start, end] as an MP3 proof clip and upload it to clips/<hash>/<start>-<end>.mp3."""
        with tempfile.TemporaryDirectory(prefix="recall-clip-") as tmp:
            clip = clips.cut_clip(audio_path, start, end, Path(tmp) / "clip.mp3")
            return self.upload(f"clips/{audio_hash}/{start:.2f}-{end:.2f}.mp3", clip, "audio/mpeg")


def _clip_args(clip: dict | None) -> dict:
    clip = clip or {}
    return {"p_clip_start": clip.get("start"), "p_clip_end": clip.get("end"), "p_clip_path": clip.get("path")}


@lru_cache
def get_db() -> Db:
    from supabase import create_client

    settings: Settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_key):
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    return Db(create_client(settings.supabase_url, settings.supabase_service_key),
              settings.supabase_audio_bucket)
