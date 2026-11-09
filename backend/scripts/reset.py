"""Delete every row from every Recall table, so the demo can be seeded again from scratch.

    cd backend && uv run python -m scripts.reset [--yes]
    cd backend && uv run python -m scripts.seed

Children go before parents (foreign keys, no cascades). Storage files (call audio, clips)
are left in the bucket. Deleting calls also deletes the transcript cache (calls.audio_hash),
so the next run of an old voice note calls Prisma again and spends credits. Deleting wa_sends
resets today's WA_DAILY_SEND_CAP count. Asks before deleting unless --yes.
"""

import argparse

from postgrest import CountMethod, ReturnMethod

from app.db import get_db

# Delete order: every table before the tables it references
TABLES = ("order_changes", "reminders", "pending_confirmations", "wa_sends", "orders", "calls", "clients")


def reset(sb) -> dict[str, int]:
    """Delete all rows from TABLES. Returns rows deleted per table."""
    deleted = {}
    for table in TABLES:
        # PostgREST refuses a DELETE without a filter; every id is >= 1
        res = sb.table(table).delete(count=CountMethod.exact, returning=ReturnMethod.minimal) \
            .gte("id", 0).execute()
        deleted[table] = res.count or 0
        print(f"{table}: {deleted[table]} rows deleted")
    return deleted


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--yes", action="store_true", help="don't ask before deleting")
    args = parser.parse_args(argv)
    if not args.yes:
        answer = input(f"Delete ALL rows from {', '.join(TABLES)}? Type 'reset' to go on: ")
        if answer.strip() != "reset":
            print("Nothing deleted.")
            return
    reset(get_db().sb)


if __name__ == "__main__":
    main()
