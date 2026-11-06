"""Glue for one inbound WhatsApp message: media -> stt -> extract -> match -> save or confirm.

Runs inside a FastAPI BackgroundTask. Drops duplicates by calls.wa_message_id before
downloading anything (WhatsApp retries webhooks). Confident items are written to
orders + order_changes in one transaction; anything unsure goes to pending_confirmations.
"""

from typing import Any


def handle_webhook(payload: dict[str, Any]) -> None:
    """Process a raw webhook payload. Not implemented yet."""
