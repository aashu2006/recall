import hashlib
import shutil
import subprocess
from datetime import date
from unittest.mock import MagicMock

import pytest

from app import db


@pytest.fixture
def sb():
    return MagicMock()


def test_create_order_goes_through_rpc_with_clean_fields(sb):
    sb.rpc.return_value.execute.return_value.data = 7
    d = db.Db(sb)

    order_id = d.create_order(
        1,
        {"item": "MS sheet", "quantity": 50.0, "rate": 42.5, "delivery_date": date(2026, 11, 13),
         "evidence": "dropped", "confidence": 0.9},
        call_id=3, clip={"start": 1.2, "end": 4.0, "path": "clips/h/1.20-4.00.mp3"}, confidence=0.9,
    )

    assert order_id == 7
    sb.table.assert_not_called()  # never write the orders table directly
    sb.rpc.assert_called_once_with("create_order", {
        "p_client_id": 1,
        "p_fields": {"item": "MS sheet", "quantity": 50, "rate": 42.5, "delivery_date": "2026-11-13"},
        "p_call_id": 3, "p_clip_start": 1.2, "p_clip_end": 4.0,
        "p_clip_path": "clips/h/1.20-4.00.mp3", "p_confidence": 0.9,
    })


def test_update_order_rpc(sb):
    sb.rpc.return_value.execute.return_value.data = 2
    d = db.Db(sb)

    assert d.update_order(12, {"quantity": 300.0, "rate": 42.0}, call_id=3) == 2
    name, args = sb.rpc.call_args.args
    assert name == "update_order"
    assert args["p_order_id"] == 12 and args["p_fields"] == {"quantity": 300, "rate": 42}
    assert args["p_clip_path"] is None


def test_update_order_with_nothing_to_change_skips_rpc(sb):
    assert db.Db(sb).update_order(12, {}) == 0
    sb.rpc.assert_not_called()


def test_resolve_pending_only_touches_pending_rows(sb):
    chain = sb.table.return_value.update.return_value.eq.return_value.eq.return_value
    chain.execute.return_value.data = []
    d = db.Db(sb)

    assert d.resolve_pending(5, "confirmed") is False
    sb.table.return_value.update.return_value.eq.assert_called_with("id", 5)
    sb.table.return_value.update.return_value.eq.return_value.eq.assert_called_with("status", "pending")

    chain.execute.return_value.data = [{"id": 5}]
    assert d.resolve_pending(5, "confirmed") is True


def test_upload_call_audio_is_keyed_by_hash(sb, tmp_path):
    note = tmp_path / "note.OGG"
    note.write_bytes(b"OggS")

    path = db.Db(sb, bucket="audio").upload_call_audio(note, "abc")

    assert path == "calls/abc.ogg"
    sb.storage.from_.assert_called_with("audio")
    sb.storage.from_.return_value.upload.assert_called_once_with(
        "calls/abc.ogg", b"OggS", {"content-type": "audio/ogg", "upsert": "true"}
    )


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_upload_clip_cuts_mp3(sb, tmp_path):
    tone = tmp_path / "tone.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=3", str(tone)], check=True)

    path = db.Db(sb).upload_clip(tone, "abc", 0.5, 2.0)

    assert path == "clips/abc/0.50-2.00.mp3"
    uploaded = sb.storage.from_.return_value.upload.call_args.args
    assert uploaded[1][:3] in (b"ID3", b"\xff\xfb", b"\xff\xf3")  # MP3 bytes
    assert uploaded[2]["content-type"] == "audio/mpeg"


def test_file_sha256(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"recall")

    assert db.file_sha256(f) == hashlib.sha256(b"recall").hexdigest()


def test_normalize_phone():
    assert db.normalize_phone("+91 98000-00001") == "919800000001"


def test_record_send_logs_every_column(sb):
    db.Db(sb).record_send("919900000000", "briefing", msg_type="audio", body="Good morning",
                          media_path="briefings/x.ogg", status="failed", error="Graph API 400")

    sb.table.assert_called_with("wa_sends")
    sb.table.return_value.insert.assert_called_once_with({
        "to_phone": "919900000000", "kind": "briefing", "msg_type": "audio", "body": "Good morning",
        "media_path": "briefings/x.ogg", "status": "failed", "error": "Graph API 400", "wa_message_id": None})


def test_send_cap_counts_only_sent_rows(sb):
    from datetime import datetime, timezone

    sb.table.return_value.select.return_value.eq.return_value.gte.return_value.limit.return_value \
        .execute.return_value.count = 3

    assert db.Db(sb).sends_since(datetime(2026, 11, 9, tzinfo=timezone.utc)) == 3
    sb.table.return_value.select.return_value.eq.assert_called_once_with("status", "sent")
