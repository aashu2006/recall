"""In-memory stand-in for app.db.Db, same method names and behaviour (incl. the RPCs'
one order_changes row per changed field)."""

from copy import deepcopy
from datetime import date, datetime

from app.db import ORDER_FIELDS, _clean_fields, normalize_phone


class FakeDb:
    def __init__(self):
        self.clients: list[dict] = []
        self.orders: list[dict] = []
        self.changes: list[dict] = []
        self.calls: list[dict] = []
        self.pending: list[dict] = []
        self.uploads: list[str] = []
        self.sends: list[dict] = []

    # clients
    def client_by_phone(self, phone):
        return next((c for c in self.clients if c["phone"] == normalize_phone(phone)), None)

    def get_client(self, client_id):
        return next((c for c in self.clients if c["id"] == client_id), None)

    def create_client(self, name, phone, aliases=None):
        row = {"id": len(self.clients) + 1, "name": name, "phone": normalize_phone(phone) if phone else None,
               "aliases": aliases or []}
        self.clients.append(row)
        return row

    # orders
    def open_orders(self, client_id):
        return [deepcopy(o) for o in self.orders if o["client_id"] == client_id and o["status"] == "open"]

    def get_order(self, order_id):
        return next((deepcopy(o) for o in self.orders if o["id"] == order_id), None)

    def add_order(self, order: dict):
        """Seed helper: put an order in with a known id."""
        self.orders.append({"status": "open", "spec": None, "unit": None, **order})

    def create_order(self, client_id, fields, *, call_id=None, clip=None, confidence=None):
        payload = {k: v for k, v in _clean_fields(fields).items() if k in ORDER_FIELDS}
        order_id = max([o["id"] for o in self.orders], default=0) + 1
        self.orders.append({"id": order_id, "client_id": client_id, "status": "open",
                            **{k: payload.get(k) for k in ORDER_FIELDS}})
        self._change(order_id, call_id, "created", None, str(payload), clip, confidence)
        return order_id

    def update_order(self, order_id, fields, *, call_id=None, clip=None, confidence=None):
        order = next(o for o in self.orders if o["id"] == order_id)
        changed = 0
        for k, v in _clean_fields(fields).items():
            if order.get(k) != v:
                self._change(order_id, call_id, k, order.get(k), v, clip, confidence)
                order[k] = v
                changed += 1
        return changed

    def _change(self, order_id, call_id, field, old, new, clip, confidence):
        clip = clip or {}
        self.changes.append({"order_id": order_id, "call_id": call_id, "field": field, "old_value": old,
                             "new_value": new, "clip_start": clip.get("start"), "clip_end": clip.get("end"),
                             "clip_path": clip.get("path"), "confidence": confidence})

    def deliveries_between(self, start: date, end: date):
        out = []
        for o in self.orders:
            d = o.get("delivery_date")
            if o["status"] == "open" and d and start.isoformat() <= str(d) <= end.isoformat():
                out.append({**o, "clients": {"name": self.get_client(o["client_id"])["name"]}})
        return sorted(out, key=lambda o: (str(o["delivery_date"]), o["id"]))

    # calls
    def call_by_wa_message_id(self, wa_message_id):
        return next((c for c in self.calls if c["wa_message_id"] == wa_message_id), None)

    def cached_call(self, audio_hash):
        hits = [c for c in self.calls if c["audio_hash"] == audio_hash and c.get("transcript") is not None]
        return hits[-1] if hits else None

    def insert_call(self, **fields):
        row = {"id": len(self.calls) + 1, **fields}
        self.calls.append(row)
        return row["id"]

    # pending
    def insert_pending(self, *, call_id, client_id, extracted, question, options):
        row = {"id": len(self.pending) + 1, "call_id": call_id, "client_id": client_id,
               "extracted_json": deepcopy(extracted), "question": question, "options": options,
               "status": "pending"}
        self.pending.append(row)
        return row["id"]

    def get_pending(self, pending_id):
        return next((deepcopy(p) for p in self.pending if p["id"] == pending_id), None)

    def list_pending(self):
        return [{**p, "clients": {"name": self.get_client(p["client_id"])["name"]}}
                for p in self.pending if p["status"] == "pending"]

    def resolve_pending(self, pending_id, status):
        row = next((p for p in self.pending if p["id"] == pending_id), None)
        if not row or row["status"] != "pending":
            return False
        row["status"] = status
        return True

    def reopen_pending(self, pending_id):
        next(p for p in self.pending if p["id"] == pending_id)["status"] = "pending"

    # storage
    def upload_call_audio(self, audio_path, audio_hash):
        self.uploads.append(f"calls/{audio_hash}.ogg")
        return self.uploads[-1]

    def upload_clip(self, audio_path, audio_hash, start, end):
        self.uploads.append(f"clips/{audio_hash}/{start:.2f}-{end:.2f}.mp3")
        return self.uploads[-1]

    def upload(self, object_path, local_path, content_type):
        self.uploads.append(object_path)
        return object_path

    # whatsapp send log
    def sends_since(self, since: datetime) -> int:
        return sum(1 for s in self.sends if s["created_at"] >= since)

    def record_send(self, to_phone, kind, wa_message_id=None):
        self.sends.append({"to_phone": to_phone, "kind": kind, "wa_message_id": wa_message_id,
                           "created_at": datetime.now().astimezone()})
