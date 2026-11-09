"""Shared paths and case loading for the eval scripts.

The eval imports the backend's own code (stt, extract, matcher, tts, seed), so the scripts
run inside the backend's uv environment; see eval/README.md.
"""

import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO = EVAL_DIR.parent
BACKEND = REPO / "backend"
CASES = EVAL_DIR / "cases.json"
OUT = EVAL_DIR / "out"  # gitignored: generated audio, transcript cache, raw results
AUDIO_DIR = OUT / "audio"
TRANSCRIPT_CACHE = OUT / "transcripts"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def load_cases(path: Path = CASES, only: list[str] | None = None) -> dict:
    data = json.loads(Path(path).read_text())
    if only:
        wanted = {c.strip() for c in only}
        data["cases"] = [c for c in data["cases"] if c["id"] in wanted]
        missing = wanted - {c["id"] for c in data["cases"]}
        if missing:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(missing))}")
    return data


def clean_path(case: dict, audio_dir: Path = AUDIO_DIR) -> Path:
    """Timbre output, OGG/Opus 48 kHz like a WhatsApp voice note."""
    return audio_dir / f"{case['id']}.clean.ogg"


def noisy_path(case: dict, audio_dir: Path = AUDIO_DIR) -> Path:
    """Clean audio + noise, squeezed to 8 kHz mu-law phone quality."""
    return audio_dir / f"{case['id']}.noisy.wav"


def voice_for(case: dict, data: dict) -> str:
    return data["voices"][case["speaker"]]


def snr_for(case: dict, data: dict) -> float:
    return float(case.get("noise_snr_db", data["default_noise_snr_db"]))
