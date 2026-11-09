"""Audio splitting (Silero VAD) and proof clip cutting with ffmpeg.

- split_on_silence: voice note -> speech chunks (<= max_len s, 16 kHz mono wav) for Prisma REST.
  Chunk start/end offsets are the segment timestamps used for audio proof.
- cut_clip: cut an MP3 proof clip from segment start/end timestamps.

Clips are stored in the Supabase "audio" bucket and linked from order_changes.
Needs ffmpeg and ffprobe on PATH (see README).
"""

import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from pysilero_vad import SileroVoiceActivityDetector

SAMPLE_RATE = 16_000
SAMPLE_WIDTH = 2  # 16-bit PCM
FRAME_S = SileroVoiceActivityDetector.chunk_samples() / SAMPLE_RATE  # 32 ms

# VAD tuning
SPEECH_ON = 0.5  # prob to enter speech
SPEECH_OFF = 0.35  # prob below which we count silence
MIN_SPEECH_S = 0.25  # drop blips shorter than this
MIN_SILENCE_S = 0.3  # silence needed to end a speech region
PAD_S = 0.15  # padding around each region
MAX_MERGE_GAP_S = 1.0  # longer silences start a new chunk (saves credits, finer clips)
MIN_CHUNK_S = 0.1  # Prisma returns empty transcript below this


class ClipError(Exception):
    pass


@dataclass(frozen=True)
class Chunk:
    start: float
    end: float
    path: Path


def split_on_silence(
    audio_path: str | Path, out_dir: str | Path | None = None, max_len: float = 28.0
) -> list[Chunk]:
    """Split audio into speech chunks of at most max_len seconds, as 16 kHz mono wav files.

    Files go to out_dir (a new temp dir if None); the caller cleans up. Returns [] if no speech.
    """
    out = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="recall-chunks-"))
    out.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="recall-wav-") as tmp:
        full_wav = Path(tmp) / "full.wav"
        to_wav16k(audio_path, full_wav)
        with wave.open(str(full_wav), "rb") as w:
            pcm = w.readframes(w.getnframes())

    total = len(pcm) / SAMPLE_WIDTH / SAMPLE_RATE
    regions = _speech_regions(_vad_probs(pcm), total=total)

    chunks = []
    for i, (start, end) in enumerate(_group(regions, max_len)):
        if end - start < MIN_CHUNK_S:
            continue
        path = out / f"chunk_{i:03d}.wav"
        _write_wav(path, pcm[_byte_offset(start) : _byte_offset(end)])
        chunks.append(Chunk(round(start, 3), round(end, 3), path))
    return chunks


def cut_clip(
    audio_path: str | Path, start: float, end: float, out_path: str | Path | None = None
) -> Path:
    """Cut [start, end] seconds of audio_path into a mono MP3 proof clip."""
    start = max(0.0, start)
    if end <= start:
        raise ValueError(f"end ({end}) must be after start ({start})")
    if out_path is None:
        out_path = Path(tempfile.mkdtemp(prefix="recall-clip-")) / f"clip_{start:.2f}_{end:.2f}.mp3"
    out_path = Path(out_path)
    _run_ffmpeg(
        ["-ss", f"{start:.3f}", "-i", str(audio_path), "-t", f"{end - start:.3f}",
         "-ac", "1", "-c:a", "libmp3lame", "-b:a", "64k", str(out_path)]
    )
    return out_path


def duration(audio_path: str | Path) -> float:
    """Length of an audio file in seconds (ffprobe)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
             str(audio_path)],
            check=True, capture_output=True, text=True,
        )
        return round(float(out.stdout.strip()), 3)
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as e:
        raise ClipError(f"ffprobe failed on {audio_path}: {e}") from e


def to_wav16k(audio_path: str | Path, out_path: str | Path) -> Path:
    """Convert any audio ffmpeg can read to 16 kHz mono 16-bit wav."""
    _run_ffmpeg(
        ["-i", str(audio_path), "-ac", "1", "-ar", str(SAMPLE_RATE),
         "-c:a", "pcm_s16le", "-f", "wav", str(out_path)]
    )
    return Path(out_path)


def _run_ffmpeg(args: list[str]) -> None:
    cmd = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", *args]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as e:
        raise ClipError("ffmpeg not found on PATH") from e
    except subprocess.CalledProcessError as e:
        raise ClipError(f"ffmpeg failed: {e.stderr.decode(errors='replace').strip()}") from e


def _vad_probs(pcm: bytes) -> list[float]:
    """Speech probability per 32 ms frame. The trailing partial frame is ignored."""
    vad = SileroVoiceActivityDetector()
    n = vad.chunk_bytes()
    return [vad(pcm[i : i + n]) for i in range(0, len(pcm) - n + 1, n)]


def _speech_regions(
    probs: list[float], frame_s: float = FRAME_S, total: float | None = None
) -> list[tuple[float, float]]:
    """Turn per-frame speech probabilities into padded (start, end) speech regions in seconds."""
    total = len(probs) * frame_s if total is None else total
    raw: list[tuple[float, float]] = []
    start = silence_since = None
    for i, p in enumerate(probs):
        t = i * frame_s
        if start is None:
            if p >= SPEECH_ON:
                start, silence_since = t, None
        elif p < SPEECH_OFF:
            if silence_since is None:
                silence_since = t
            elif t + frame_s - silence_since >= MIN_SILENCE_S:
                raw.append((start, silence_since))
                start = silence_since = None
        else:
            silence_since = None
    if start is not None:
        raw.append((start, silence_since if silence_since is not None else len(probs) * frame_s))

    regions: list[tuple[float, float]] = []
    for s, e in raw:
        if e - s < MIN_SPEECH_S:
            continue
        s, e = max(0.0, s - PAD_S), min(total, e + PAD_S)
        if regions and s <= regions[-1][1]:
            regions[-1] = (regions[-1][0], e)
        else:
            regions.append((s, e))
    return regions


def _group(regions: list[tuple[float, float]], max_len: float) -> list[tuple[float, float]]:
    """Pack speech regions into chunks no longer than max_len. Long regions are hard-split."""
    chunks: list[tuple[float, float]] = []
    for start, end in regions:
        if chunks and start - chunks[-1][1] <= MAX_MERGE_GAP_S and end - chunks[-1][0] <= max_len:
            chunks[-1] = (chunks[-1][0], end)
            continue
        while end - start > max_len:
            chunks.append((start, start + max_len))
            start += max_len
        chunks.append((start, end))
    return chunks


def _byte_offset(seconds: float) -> int:
    return round(seconds * SAMPLE_RATE) * SAMPLE_WIDTH


def _write_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(SAMPLE_WIDTH)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
