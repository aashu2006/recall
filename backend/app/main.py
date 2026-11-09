"""FastAPI entrypoint: health check, the WhatsApp webhook (GET verify, POST messages), the
morning briefing (send / preview) and resolving a pending confirmation without WhatsApp.

Everything except /health and /webhook needs the CRON_SECRET bearer token.

The webhook POST handler must return 200 immediately; all work runs in a BackgroundTask.
"""

import hmac
import json
import logging
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from app import briefing, pipeline, whatsapp
from app.config import Settings, get_settings
from app.db import get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(title="Recall")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def require_cron_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Bearer CRON_SECRET. Refuses everything when the secret is not set."""
    expected = f"Bearer {settings.cron_secret}"
    if not settings.cron_secret or not hmac.compare_digest(authorization or "", expected):
        raise HTTPException(status_code=403, detail="forbidden")


Authorized = Depends(require_cron_secret)


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


@app.post("/briefing/send", dependencies=[Authorized])
def send_briefing(settings: Annotated[Settings, Depends(get_settings)]):
    """Morning briefing to the owner on WhatsApp. Any scheduler can call it."""
    db = get_db()
    return briefing.send(db, whatsapp.WhatsApp(settings=settings, db=db))


@app.post("/briefing/preview", dependencies=[Authorized])
def preview_briefing(settings: Annotated[Settings, Depends(get_settings)]):
    """Build and voice the briefing, store it under briefings/ in the audio bucket and log it
    in wa_sends (status preview). Nothing is sent on WhatsApp."""
    out = briefing.preview(get_db(), settings)
    return JSONResponse(out, status_code=502 if out.get("error") else 200)


class Resolve(BaseModel):
    choice: str = Field(pattern=r"^(\d+|new|no)$", description="an order id, new or no")


@app.post("/pending/{pending_id}/resolve", dependencies=[Authorized])
def resolve_pending(pending_id: int, body: Resolve):
    """The owner's button tap, without WhatsApp. Same path as the button: checks the choice,
    marks the item resolved, then creates or updates the order with its order_changes row."""
    db = get_db()
    row = db.get_pending(pending_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"pending #{pending_id} not found")
    if row["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"pending #{pending_id} is already {row['status']}")
    options = [str(o) for o in row.get("options") or []]
    if body.choice != "no" and body.choice not in options:
        raise HTTPException(status_code=422, detail=f"choice must be one of {options + ['no']}")
    message = pipeline.resolve_pending(pending_id, body.choice, db=db)
    status = db.get_pending(pending_id)["status"]
    out = {"pending_id": pending_id, "choice": body.choice, "status": status, "message": message}
    return JSONResponse(out, status_code=500 if status == "pending" else 200)  # pending again = save failed
