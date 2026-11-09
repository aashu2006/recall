"""Run the full voice note pipeline on a local audio file, without WhatsApp.

    cd backend && uv run python -m scripts.run_pipeline path/to/note.ogg [--phone 919800000001] \\
        [--time 2026-11-09T10:30:00+05:30] [--message-id test-1]

Uses real Prisma (unless this audio's hash is already cached in calls), the LLM and
Supabase. Nothing is sent on WhatsApp: the client summary and owner questions are printed.
--message-id makes re-runs idempotent (a seen id is skipped).
"""

import argparse
import json
import logging
from dataclasses import asdict
from datetime import datetime

from app import pipeline
from app.extract import IST


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("audio", help="audio file (ogg, wav, mp3, m4a, ...)")
    parser.add_argument("--phone", default="919800000001", help="sender phone (default: seeded Sharma Steels)")
    parser.add_argument("--time", help="call time, ISO 8601 (default: now, Asia/Kolkata)")
    parser.add_argument("--message-id", help="pretend WhatsApp message id, for dedupe")
    return parser.parse_args(argv)


def call_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(IST)
    t = datetime.fromisoformat(value)
    return t if t.tzinfo else t.replace(tzinfo=IST)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    result = pipeline.handle_voice_note(args.audio, args.phone, args.message_id, call_time(args.time))
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    if result.summary:
        print("\n--- client gets ---\n" + result.summary)
    for p in result.pending:
        print(f"\n--- owner gets (pending #{p.id}, options {p.options} or no) ---\n{p.question}")


if __name__ == "__main__":
    main()
