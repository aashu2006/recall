"""Eval scripts, with Prisma, Timbre and the LLM mocked. Never calls a real API.

    uv run --project backend --with jiwer pytest eval/tests
"""

import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import make_audio  # noqa: E402
import run_eval  # noqa: E402
from app.extract import Item  # noqa: E402
from app.matcher import Decision  # noqa: E402
from common import load_cases  # noqa: E402

CALL_DATE = date(2026, 11, 9)
REQUIRED_CATEGORIES = {"new_order", "quantity_change", "rate_change", "date_change", "two_items",
                       "ambiguous_update", "noisy"}


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    def blocked(self, request):
        raise RuntimeError(f"Real HTTP call blocked in tests: {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture(autouse=True)
def pauses(monkeypatch):
    """run_eval --pause sleeps between runs; record instead of waiting."""
    out = []
    monkeypatch.setattr(run_eval.time, "sleep", out.append)
    return out


# ------------------------------------------------------------------ cases.json

def test_cases_cover_the_prd_and_reference_real_seed_orders():
    data = load_cases()
    cases = data["cases"]
    world = run_eval.build_world(CALL_DATE)
    assert len(cases) == 10
    assert len({c["id"] for c in cases}) == 10
    assert REQUIRED_CATEGORIES <= {c["category"] for c in cases}
    assert {c["client"] for c in cases} == {"sharma", "gupta", "patel"} == set(world)
    assert [c["speaker"] for c in cases] == ["female", "male"] * 5  # voices alternate
    assert any(c.get("noise_snr_db", 99) < data["default_noise_snr_db"] for c in cases)

    for c in cases:
        assert c["script"].strip() and c["reference"].strip()
        assert not any(ch.isdigit() for ch in c["script"]), f"{c['id']}: numbers as words for Timbre"
        orders = {o["id"]: o for o in run_eval.case_orders(c, world, CALL_DATE)}
        for e in c["expected"]:
            assert e["kind"] in ("new_order", "update")
            if e["kind"] == "update" and not e.get("expect_confirmation"):
                assert run_eval.item_matches(orders[e["order_id"]]["item"], e["item"]), c["id"]
            for cand in e.get("candidates", []):
                assert run_eval.item_matches(orders[cand]["item"], e["item"]), c["id"]
            if e.get("expect_confirmation"):  # ambiguous: two open orders of the same item
                same = [o for o in orders.values() if run_eval.item_matches(o["item"], e["item"])]
                assert len(same) >= 2, c["id"]


def test_world_matches_a_fresh_seed():
    world = run_eval.build_world(CALL_DATE)
    sharma = world["sharma"]["open_orders"]
    assert world["sharma"]["client"]["name"] == "Sharma Steels"
    assert [o["id"] for o in sharma] == [1, 2]
    assert sharma[0]["item"] == "bracket" and sharma[0]["quantity"] == 200
    assert [o["id"] for o in world["patel"]["open_orders"]] == [5, 6]


def test_expected_dates_are_relative_to_call_time():
    case = {"expected": [{"kind": "new_order", "item": "x", "delivery_in_days": 4},
                         {"kind": "update", "item": "y", "delivery_in_days": None}]}
    out = run_eval.expected_items(case, CALL_DATE)
    assert out[0]["delivery_date"] == "2026-11-13"
    assert out[1]["delivery_date"] is None
    assert "delivery_in_days" not in out[0]


# ------------------------------------------------------------------ scoring

def test_normalize_text_ignores_punctuation_and_nukta_variants():
    assert run_eval.normalize_text("हाँ भैया, Order है ना।") == run_eval.normalize_text("हां भैया order है ना")
    assert run_eval.normalize_text("चीज़ें") == run_eval.normalize_text("चीजें")


def test_field_rules():
    assert run_eval.item_matches("angle", "MS angle")
    assert run_eval.item_matches("bracket", "brackets")
    assert not run_eval.item_matches("bracket", "डाला")
    assert run_eval.field_ok("unit", "pcs", "piece")
    assert run_eval.field_ok("spec", "50x50x6", "50 x 50 x 6")
    assert run_eval.field_ok("spec", "3mm", "3mm MS")
    assert run_eval.field_ok("quantity", 300, 300.0)
    assert not run_eval.field_ok("rate", None, 45)  # restating an unchanged value is wrong
    assert run_eval.field_ok("delivery_date", "2026-11-13", date(2026, 11, 13))


def test_score_case_pairs_by_item_and_flags_extras():
    expected = [
        {"kind": "update", "item": "bracket", "quantity": 300, "rate": None, "delivery_date": None, "order_id": 1},
        {"kind": "new_order", "item": "MS sheet", "quantity": 50, "rate": 2400, "delivery_date": "2026-11-13"},
    ]
    items = [
        {"kind": "new_order", "item": "MS sheet", "quantity": 50, "rate": 2400, "delivery_date": "2026-11-14"},
        {"kind": "update", "item": "bracket", "quantity": 300, "rate": None, "delivery_date": None},
        {"kind": "new_order", "item": "nut bolt", "quantity": 1, "rate": None, "delivery_date": None},
    ]
    decisions = [
        {"action": "create", "order_id": None, "candidate_ids": []},
        {"action": "update", "order_id": 1, "candidate_ids": [1]},
        {"action": "confirm", "order_id": None, "candidate_ids": []},
    ]
    s = run_eval.score_case(expected, items, decisions)
    assert [i["got_index"] for i in s["items"]] == [1, 0]
    assert s["items"][0]["correct"] and s["items"][0]["match_ok"]
    assert not s["items"][1]["correct"]  # wrong date
    assert s["items"][1]["match_ok"]
    assert s["extra_items"] == [2]


def test_ambiguous_update_must_go_to_owner():
    e = {"kind": "update", "item": "MS sheet", "order_id": None, "expect_confirmation": True, "candidates": [3, 101]}
    assert run_eval.decision_ok(e, {"action": "confirm", "order_id": 3, "candidate_ids": [3, 101]})
    assert not run_eval.decision_ok(e, {"action": "update", "order_id": 3, "candidate_ids": [3]})
    assert not run_eval.decision_ok(e, {"action": "confirm", "order_id": None, "candidate_ids": [3]})


# ------------------------------------------------------------------ end to end, mocked

def _fake_pipeline(monkeypatch, data, *, stt_calls):
    """Perfect STT (returns the reference) and perfect extraction/matching from cases.json."""
    by_ref = {c["reference"]: c for c in data["cases"]}
    audio_to_case = {}

    def transcribe(audio, keyterms=None, settings=None):
        stt_calls.append(Path(audio).name)
        case = audio_to_case[Path(audio).read_bytes()]
        return {"transcript": case["reference"], "segments": [], "model": "fake"}

    def extract(transcript, *, call_time, client_name, open_orders):
        case = by_ref[transcript]
        return [Item(kind=e["kind"], item=e["item"], spec=e.get("spec"), quantity=e.get("quantity"),
                     unit=e.get("unit"), rate=e.get("rate"), delivery_date=e["delivery_date"],
                     evidence=transcript, confidence=0.9)
                for e in run_eval.expected_items(case, CALL_DATE)]

    def match(item, open_orders):
        for c in data["cases"]:
            for e in c["expected"]:
                if e["item"] == item.item and e["kind"] == item.kind and e.get("quantity") == item.quantity:
                    if e.get("expect_confirmation"):
                        return Decision("confirm", None, 0.5, e["candidates"])
                    if e["kind"] == "update":
                        return Decision("update", e["order_id"], 0.9, [e["order_id"]])
                    return Decision("create", None, 0.9)
        raise AssertionError(item)

    monkeypatch.setattr(run_eval.stt, "transcribe", transcribe)
    monkeypatch.setattr(run_eval.extract, "extract", extract)
    monkeypatch.setattr(run_eval.matcher, "match", match)
    return audio_to_case


def test_run_eval_end_to_end_mocked(tmp_path, monkeypatch, pauses):
    data = load_cases()
    stt_calls: list[str] = []
    audio_to_case = _fake_pipeline(monkeypatch, data, stt_calls=stt_calls)
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    for c in data["cases"]:
        for kind in ("clean.ogg", "noisy.wav"):
            blob = f"{c['id']}-{kind}".encode()
            (audio_dir / f"{c['id']}.{kind}").write_bytes(blob)
            audio_to_case[blob] = c

    args = ["--audio-dir", str(audio_dir), "--cache-dir", str(tmp_path / "cache"),
            "--out", str(tmp_path / "results.md"), "--json-out", str(tmp_path / "results.json"), "--yes"]
    assert run_eval.main(args) == 0
    assert len(stt_calls) == 20

    md = (tmp_path / "results.md").read_text()
    assert "| WER | 0.0% | 0.0% |" in md
    assert "| Extraction accuracy (item, qty, rate, date all correct) | 12/12 (100%) | 12/12 (100%) |" in md
    assert "| Matching accuracy | 12/12 (100%) | 12/12 (100%) |" in md
    assert "| Confirmation rate (items sent to owner) | 1/12 (8%) | 1/12 (8%) |" in md
    assert "confirm (#3/#101)" in md
    raw = json.loads((tmp_path / "results.json").read_text())
    assert len(raw["records"]) == 20 and not any("error" in r for r in raw["records"])

    assert pauses == [10.0] * 19  # default --pause between the 20 runs, none after the last
    pauses.clear()

    # Second run: every transcript comes from the cache, Prisma is never called again.
    assert run_eval.main(args) == 0
    assert len(stt_calls) == 20


def test_run_eval_dry_run_and_decline_call_nothing(tmp_path, monkeypatch, pauses):
    data = load_cases()
    stt_calls: list[str] = []
    audio_to_case = _fake_pipeline(monkeypatch, data, stt_calls=stt_calls)
    (tmp_path / "C01.clean.ogg").write_bytes(b"a")
    audio_to_case[b"a"] = data["cases"][0]
    base = ["--audio-dir", str(tmp_path), "--cache-dir", str(tmp_path / "cache"), "--only", "C01",
            "--variants", "clean", "--out", str(tmp_path / "r.md"), "--json-out", str(tmp_path / "r.json")]
    assert run_eval.main([*base, "--dry-run"]) == 0
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert run_eval.main(base) == 1
    assert stt_calls == [] and not (tmp_path / "r.md").exists() and pauses == []


def test_one_failing_case_does_not_lose_the_run(tmp_path, monkeypatch):
    data = load_cases(only=["C01", "C02"])
    stt_calls: list[str] = []
    audio_to_case = _fake_pipeline(monkeypatch, data, stt_calls=stt_calls)
    for c in data["cases"]:
        (tmp_path / f"{c['id']}.clean.ogg").write_bytes(c["id"].encode())
        audio_to_case[c["id"].encode()] = c
    real = run_eval.extract.extract

    def flaky(transcript, **kw):
        if "Patel" in transcript:
            raise RuntimeError("LLM down")
        return real(transcript, **kw)

    monkeypatch.setattr(run_eval.extract, "extract", flaky)
    assert run_eval.main(["--audio-dir", str(tmp_path), "--cache-dir", str(tmp_path / "c"), "--only", "C01,C02",
                          "--variants", "clean", "--out", str(tmp_path / "r.md"),
                          "--json-out", str(tmp_path / "r.json"), "--yes"]) == 0
    md = (tmp_path / "r.md").read_text()
    assert "| Extraction accuracy (item, qty, rate, date all correct) | 1/2 (50%) |" in md
    assert "| Cases that errored | 1 |" in md


# ------------------------------------------------------------------ make_audio

def test_make_audio_skips_existing_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("app.tts.synthesize", lambda text, settings: calls.append(
        (settings.gnani_tts_voice, settings.gnani_tts_language)) or b"OggS-fake")
    monkeypatch.setattr(make_audio, "make_noisy", lambda src, out, snr_db, seed: out.write_bytes(b"noisy"))
    args = ["--out", str(tmp_path), "--only", "C01,C02,C09", "--yes"]

    assert make_audio.main(args) == 0
    assert calls == [("Poorvi", "hi-en"), ("Vikrant", "hi-en"), ("Poorvi", "hi-en")]
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "C01.clean.ogg", "C01.noisy.wav", "C02.clean.ogg", "C02.noisy.wav", "C09.clean.ogg", "C09.noisy.wav"]

    assert make_audio.main(args) == 0
    assert len(calls) == 3  # nothing paid twice


def test_make_audio_dry_run_and_decline_call_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("app.tts.synthesize", lambda *a, **k: pytest.fail("Timbre called"))
    assert make_audio.main(["--out", str(tmp_path), "--dry-run"]) == 0
    monkeypatch.setattr("builtins.input", lambda _: "")
    assert make_audio.main(["--out", str(tmp_path)]) == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_make_noisy_gives_8khz_mono_at_the_target_snr(tmp_path):
    clean = tmp_path / "tone.ogg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=700:duration=3",
                    "-ar", "48000", "-c:a", "libopus", str(clean)], check=True)
    out = make_audio.make_noisy(clean, tmp_path / "tone.noisy.wav", snr_db=3, seed=7)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels,codec_name",
                            "-of", "json", str(out)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream == {"codec_name": "pcm_mulaw", "sample_rate": "8000", "channels": 1}
    # Noise really went in: louder than the band-limited tone alone would be, by about 10*log10(1 + 10^-0.3)
    band = tmp_path / "band.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(clean), "-af", make_audio.PHONE_BAND,
                    "-ar", "8000", str(band)], check=True)
    assert make_audio.mean_volume(out) - make_audio.mean_volume(band) == pytest.approx(1.76, abs=0.6)
