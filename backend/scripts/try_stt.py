"""Run STT on one audio file. Without --dry-run this hits the real Prisma API (uses credits).

    cd backend && uv run python -m scripts.try_stt path/to/note.ogg [--dry-run]
"""

import argparse
import json
import logging
import sys
import tempfile

from app import clips, stt
from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", help="audio file (ogg, wav, mp3, m4a, ...)")
    parser.add_argument("--dry-run", action="store_true", help="only print VAD chunks, no API call")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()

    if args.dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            chunks = clips.split_on_silence(args.audio, out_dir=tmp, max_len=settings.gnani_stt_max_chunk_s)
        print(json.dumps([{"start": c.start, "end": c.end} for c in chunks], indent=2))
        return

    if not settings.gnani_api_key:
        sys.exit("GNANI_API_KEY is empty. Set it in the repo-root .env")
    result = stt.transcribe(args.audio, settings=settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
