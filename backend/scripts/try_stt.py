"""Run STT on one audio file. Without --dry-run this hits the real Prisma API (uses credits).

    cd backend && uv run python -m scripts.try_stt path/to/note.ogg [--dry-run]
    cd backend && uv run python -m scripts.try_stt note.ogg --model prisma-v3.0 --format transcribe \\
        --language hi-IN --keyterms "MS sheet,bracket,kg"

--model/--format/--language/--keyterms override settings for this run only.
"""

import argparse
import json
import logging
import sys
import tempfile

from app import clips, stt
from app.config import Settings, get_settings

log = logging.getLogger("try_stt")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", help="audio file (ogg, wav, mp3, m4a, ...)")
    parser.add_argument("--dry-run", action="store_true", help="only print VAD chunks, no API call")
    parser.add_argument("--model", help="e.g. prisma-v3.0 (GNANI_STT_MODEL)")
    parser.add_argument("--format", help="verbatim, transcribe, codemix, transliterate (GNANI_STT_FORMAT)")
    parser.add_argument("--language", help='e.g. "hi-IN,en-IN" or indic-auto (GNANI_STT_LANGUAGE_CODE)')
    parser.add_argument(
        "--keyterms", help='comma separated, e.g. "MS sheet,bracket,kg"; "none" sends no keyterms'
    )
    return parser.parse_args(argv)


def parse_keyterms(value: str | None) -> list[str] | None:
    """None keeps the settings default, "none" means send no keyterms."""
    if value is None:
        return None
    if value.strip().lower() == "none":
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """Copy of settings with CLI overrides; the cached settings are not touched."""
    overrides = {
        "gnani_stt_model": args.model,
        "gnani_stt_format": args.format,
        "gnani_stt_language_code": args.language,
    }
    return settings.model_copy(update={k: v for k, v in overrides.items() if v})


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = apply_overrides(get_settings(), args)

    if args.dry_run:
        with tempfile.TemporaryDirectory() as tmp:
            chunks = clips.split_on_silence(args.audio, out_dir=tmp, max_len=settings.gnani_stt_max_chunk_s)
        print(json.dumps([{"start": c.start, "end": c.end} for c in chunks], indent=2))
        return

    if not settings.gnani_api_key:
        sys.exit("GNANI_API_KEY is empty. Set it in the repo-root .env")
    keyterms = parse_keyterms(args.keyterms)
    log.info(
        "model=%s format=%s language=%s keyterms=%s",
        settings.gnani_stt_model,
        settings.gnani_stt_format,
        settings.gnani_stt_language_code,
        settings.gnani_stt_keyterms if keyterms is None else keyterms,
    )
    result = stt.transcribe(args.audio, settings=settings, keyterms=keyterms)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
