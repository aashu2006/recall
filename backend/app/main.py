"""FastAPI entrypoint: health check and the WhatsApp webhook (GET verify, POST messages).

The POST handler must return 200 immediately; all work runs in a BackgroundTask.
"""

from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, Query, Request
from fastapi.responses import PlainTextResponse

from app import pipeline
from app.config import Settings, get_settings

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
async def receive_webhook(request: Request, background: BackgroundTasks) -> dict[str, str]:
    # TODO: verify X-Hub-Signature-256 with WA_APP_SECRET.
    payload = await request.json()
    background.add_task(pipeline.handle_webhook, payload)
    return {"status": "received"}
