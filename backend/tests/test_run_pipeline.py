from datetime import datetime

from app import pipeline
from scripts import run_pipeline


def test_call_time_defaults_to_ist():
    assert run_pipeline.call_time("2026-11-09T10:30:00").utcoffset().total_seconds() == 5.5 * 3600
    assert run_pipeline.call_time("2026-11-09T05:00:00+00:00").hour == 5
    assert run_pipeline.call_time(None).tzinfo is not None


def test_main_runs_pipeline_and_prints(monkeypatch, capsys):
    seen = {}

    def handle(audio, phone, msg_id, t):
        seen.update(audio=audio, phone=phone, msg_id=msg_id, t=t)
        return pipeline.PipelineResult(call_id=3, order_ids=[13], pending_ids=[1], summary="Namaste",
                                       pending=[pipeline.Pending(1, "Kaunsa order?", [12])])

    monkeypatch.setattr(pipeline, "handle_voice_note", handle)

    run_pipeline.main(["note.ogg", "--time", "2026-11-09T10:30:00", "--message-id", "m1"])

    assert seen["audio"] == "note.ogg" and seen["phone"] == "919800000001" and seen["msg_id"] == "m1"
    assert seen["t"] == datetime.fromisoformat("2026-11-09T10:30:00+05:30")
    out = capsys.readouterr().out
    assert '"call_id": 3' in out and "client gets ---\nNamaste" in out and "Kaunsa order?" in out


def test_from_phone_flag_and_seed_default():
    assert run_pipeline.parse_args(["note.ogg"]).from_phone == "919800000001"  # Sharma Steels in seed.py
    assert run_pipeline.parse_args(["note.ogg", "--from-phone", "919800000002"]).from_phone == "919800000002"
    assert run_pipeline.parse_args(["note.ogg", "--phone", "919800000003"]).from_phone == "919800000003"
