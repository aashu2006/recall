"""Voice the eval scripts with Timbre, then make a noisy 8 kHz phone-quality copy of each.

    uv run --project backend python eval/make_audio.py --dry-run     # plan only, no API calls
    uv run --project backend python eval/make_audio.py               # asks before spending credits
    uv run --project backend python eval/make_audio.py --only C01,C09 --yes

Writes eval/out/audio/<id>.clean.ogg (Timbre, via backend/app/tts.py) and <id>.noisy.wav.
Files that already exist are skipped, so a case is never voiced twice. Delete a file to
redo it. Voices alternate by speaker (female Poorvi, male Vikrant), language hi-en.

Noisy copy (local ffmpeg, free): band-limit to 300-3400 Hz, add generated pink + brown noise
at the case's SNR (default 10 dB, the "noisy" case 3 dB), resample to 8 kHz mono mu-law.
"""

import argparse
import re
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from common import AUDIO_DIR, CASES, clean_path, load_cases, noisy_path, snr_for, voice_for

PHONE_BAND = "highpass=f=300,lowpass=f=3400"
WORK_RATE = 16_000
PHONE_RATE = 8_000


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cases", type=Path, default=CASES)
    p.add_argument("--out", type=Path, default=AUDIO_DIR, help="audio output dir")
    p.add_argument("--only", help="comma separated case ids, e.g. C01,C09")
    p.add_argument("--female-voice", help="override voices.female from cases.json")
    p.add_argument("--male-voice", help="override voices.male from cases.json")
    p.add_argument("--dry-run", action="store_true", help="print the plan, call nothing")
    p.add_argument("--yes", action="store_true", help="don't ask before calling Timbre")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = load_cases(args.cases, args.only.split(",") if args.only else None)
    if args.female_voice:
        data["voices"]["female"] = args.female_voice
    if args.male_voice:
        data["voices"]["male"] = args.male_voice
    todo_tts = [c for c in data["cases"] if not _exists(clean_path(c, args.out))]
    todo_noise = [c for c in data["cases"] if not _exists(noisy_path(c, args.out))]
    chars = sum(len(c["script"]) for c in todo_tts)
    print(f"{len(data['cases'])} cases. Timbre calls needed: {len(todo_tts)} ({chars} chars). "
          f"Noisy copies needed: {len(todo_noise)} (local ffmpeg).")
    for c in todo_tts:
        print(f"  TTS   {c['id']} voice={voice_for(c, data)} lang={data['tts_language']}: {c['script'][:60]}...")
    for c in todo_noise:
        print(f"  noise {c['id']} snr={snr_for(c, data):g} dB")
    if args.dry_run:
        return 0
    args.out.mkdir(parents=True, exist_ok=True)
    if todo_tts and not args.yes and input("Call Timbre now? This spends Gnani credits [y/N] ").strip().lower() != "y":
        print("Stopped. Nothing was called.")
        return 1

    if todo_tts:
        from app import tts
        from app.config import get_settings

        base = get_settings()
        for c in todo_tts:
            settings = base.model_copy(update={
                "gnani_tts_voice": voice_for(c, data), "gnani_tts_language": data["tts_language"]})
            audio = tts.synthesize(c["script"], settings=settings)
            _write_atomic(clean_path(c, args.out), audio)
            print(f"  wrote {clean_path(c, args.out)} ({len(audio)} bytes)")

    for c in todo_noise:
        src = clean_path(c, args.out)
        if not _exists(src):
            print(f"  skip noise {c['id']}: {src.name} missing")
            continue
        make_noisy(src, noisy_path(c, args.out), snr_db=snr_for(c, data), seed=zlib.crc32(c["id"].encode()))
        print(f"  wrote {noisy_path(c, args.out)}")
    return 0


def make_noisy(clean: Path, out: Path, *, snr_db: float, seed: int) -> Path:
    """Mix generated pink + brown noise into clean speech at snr_db (in the phone band),
    then make it 8 kHz mono mu-law. Deterministic for a given seed."""
    seed %= 2**31
    with tempfile.TemporaryDirectory(prefix="recall-noise-") as tmp:
        speech = Path(tmp) / "speech.wav"
        noise = Path(tmp) / "noise.wav"
        _ffmpeg(["-i", str(clean), "-af", f"aresample={WORK_RATE},{PHONE_BAND}",
                 "-ac", "1", "-ar", str(WORK_RATE), "-c:a", "pcm_s16le", str(speech)])
        dur = _duration(speech)
        # Pink for hiss and traffic, brown for machine rumble.
        _ffmpeg([
            "-f", "lavfi", "-i", f"anoisesrc=color=pink:seed={seed}:sample_rate={WORK_RATE}:duration={dur}",
            "-f", "lavfi", "-i", f"anoisesrc=color=brown:seed={seed + 1}:sample_rate={WORK_RATE}:duration={dur}",
            "-filter_complex", f"[0:a][1:a]amix=inputs=2:normalize=0:weights='0.6 1',{PHONE_BAND}",
            "-ac", "1", "-c:a", "pcm_s16le", str(noise),
        ])
        gain_db = mean_volume(speech) - snr_db - mean_volume(noise)
        tmp_out = out.with_suffix(".part.wav")
        _ffmpeg([
            "-i", str(speech), "-i", str(noise),
            "-filter_complex",
            f"[1:a]volume={gain_db:.2f}dB[n];[0:a][n]amix=inputs=2:duration=first:normalize=0,"
            f"alimiter=limit=0.9:level=0,aresample={PHONE_RATE}",
            "-ac", "1", "-ar", str(PHONE_RATE), "-c:a", "pcm_mulaw", str(tmp_out),
        ])
        tmp_out.replace(out)
    return out


def mean_volume(path: Path) -> float:
    """Mean (RMS) level in dBFS, from ffmpeg volumedetect."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True, check=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf) dB", r.stderr)
    if not m or m.group(1) == "-inf":
        raise RuntimeError(f"could not measure volume of {path} (silent?)")
    return float(m.group(1))


def _duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _ffmpeg(args: list[str]) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()[-500:]}")


def _exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _write_atomic(path: Path, data: bytes) -> None:
    """A half-written file must never look done, or the skip check would trust it."""
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


if __name__ == "__main__":
    sys.exit(main())
