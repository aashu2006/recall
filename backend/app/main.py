"""FastAPI entrypoint: health check, the WhatsApp webhook (GET verify, POST messages) and
the morning briefing trigger.

The POST handler must return 200 immediately; all work runs in a BackgroundTask.
"""

import json
import logging
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app import whatsapp
from app.config import Settings, get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Recall")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    settings: Annotated[Settings, Depends(get_settings)],
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> PlainTextResponse:
    """Meta calls this once when the webhook URL is registered and echoes back the challenge."""
    expected = settings.wa_verify_token
    if mode == "subscribe" and expected and token == expected and challenge is not None:
        return PlainTextResponse(challenge)
    return PlainTextResponse("forbidden", status_code=403)


@app.post("/webhook")
async def receive_webhook(
    request: Request,
    background: BackgroundTasks,
    settings: Annotated[Settings, Depends(get_settings)],
    signature: Annotated[str | None, Header(alias="X-Hub-Signature-256")] = None,
):
    raw = await request.body()
    if not settings.wa_app_secret:
        log.error("WA_APP_SECRET is not set, rejecting webhook")
        return JSONResponse({"status": "forbidden"}, status_code=403)
    if not whatsapp.verify_signature(raw, signature, settings.wa_app_secret):
        return JSONResponse({"status": "bad signature"}, status_code=403)
    try:
        payload = json.loads(raw)
    except ValueError:
        return JSONResponse({"status": "bad json"}, status_code=400)
    background.add_task(whatsapp.process_webhook, payload)
    return {"status": "received"}
