import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from app import clips

FIXTURES = Path(__file__).parent / "fixtures"
F = 0.032  # VAD frame length in seconds

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def frames(seconds: float) -> int:
    return round(seconds / F)


def test_speech_regions_split_on_long_silence():
    probs = [0.0] * 10 + [0.9] * 20 + [0.0] * 20 + [0.9] * 20 + [0.0] * 10

    regions = clips._speech_regions(probs, frame_s=F)

    assert len(regions) == 2
    assert regions[0] == pytest.approx((10 * F - clips.PAD_S, 30 * F + clips.PAD_S))
    assert regions[1] == pytest.approx((50 * F - clips.PAD_S, 70 * F + clips.PAD_S))


def test_speech_regions_bridge_short_pause():
    probs = [0.9] * 20 + [0.0] * 5 + [0.9] * 20

    assert len(clips._speech_regions(probs, frame_s=F)) == 1


def test_speech_regions_drop_blips():
    probs = [0.0] * 10 + [0.9] * 3 + [0.0] * 10

    assert clips._speech_regions(probs, frame_s=F) == []


def test_speech_regions_padding_clamped_to_file():
    probs = [0.9] * 30
    total = 30 * F

    assert clips._speech_regions(probs, frame_s=F, total=total) == [(0.0, pytest.approx(total))]


def test_group_packs_close_regions_up_to_max_len():
    regions = [(0.0, 10.0), (10.5, 20.0), (20.5, 30.0)]

    assert clips._group(regions, max_len=28.0) == [(0.0, 20.0), (20.5, 30.0)]


def test_group_starts_new_chunk_after_long_silence():
    assert clips._group([(0.0, 2.0), (5.0, 7.0)], max_len=28.0) == [(0.0, 2.0), (5.0, 7.0)]


def test_group_hard_splits_long_region():
    chunks = clips._group([(0.0, 70.0)], max_len=28.0)

    assert chunks == [(0.0, 28.0), (28.0, 56.0), (56.0, 70.0)]


def make_tone(path: Path, seconds: float) -> Path:
    # Stereo 44.1 kHz on purpose, so we check the 16 kHz mono conversion.
    subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}", "-ar", "44100", "-ac", "2", str(path)],
        check=True,
    )
    return path


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout)


@needs_ffmpeg
def test_split_on_silence_writes_16k_mono_chunks(tmp_path, monkeypatch):
    tone = make_tone(tmp_path / "tone.wav", 5.0)
    speech = set(range(frames(0.5), frames(1.5))) | set(range(frames(3.5), frames(4.5)))
    monkeypatch.setattr(
        clips, "_vad_probs",
        lambda pcm: [0.9 if i in speech else 0.0 for i in range(len(pcm) // 1024)],
    )

    chunks = clips.split_on_silence(tone, out_dir=tmp_path / "out", max_len=28.0)

    assert len(chunks) == 2
    for c in chunks:
        assert c.path.parent == tmp_path / "out"
        with wave.open(str(c.path), "rb") as w:
            assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
            assert w.getnframes() / 16000 == pytest.approx(c.end - c.start, abs=0.002)


@needs_ffmpeg
def test_split_on_silence_no_speech(tmp_path, monkeypatch):
    tone = make_tone(tmp_path / "tone.wav", 2.0)
    monkeypatch.setattr(clips, "_vad_probs", lambda pcm: [0.0] * (len(pcm) // 1024))

    assert clips.split_on_silence(tone, out_dir=tmp_path / "out") == []


@needs_ffmpeg
def test_cut_clip_duration(tmp_path):
    tone = make_tone(tmp_path / "tone.wav", 5.0)

    clip = clips.cut_clip(tone, 1.0, 3.5, tmp_path / "clip.mp3")

    assert clip == tmp_path / "clip.mp3"
    assert duration(clip) == pytest.approx(2.5, abs=0.1)


def test_cut_clip_rejects_empty_range(tmp_path):
    with pytest.raises(ValueError):
        clips.cut_clip(tmp_path / "x.wav", 3.0, 3.0)


@needs_ffmpeg
def test_ffmpeg_failure_raises_clip_error(tmp_path):
    bad = tmp_path / "bad.ogg"
    bad.write_bytes(b"not audio")

    with pytest.raises(clips.ClipError):
        clips.split_on_silence(bad, out_dir=tmp_path / "out")


@needs_ffmpeg
@pytest.mark.skipif(not (FIXTURES / "sample_note.ogg").exists(), reason="sample_note.ogg missing")
@pytest.mark.parametrize("max_len", [28.0, 8.0])
def test_real_vad_on_sample_note(tmp_path, max_len):
    chunks = clips.split_on_silence(FIXTURES / "sample_note.ogg", out_dir=tmp_path, max_len=max_len)

    assert chunks
    assert all(c.end - c.start <= max_len for c in chunks)
    assert all(b.start >= a.end for a, b in zip(chunks, chunks[1:]))
