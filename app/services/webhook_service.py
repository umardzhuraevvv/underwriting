import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.database import Anketa, WebhookConfig

logger = logging.getLogger("app")


def _build_payload(event: str, anketa: Anketa) -> dict:
    client_name = anketa.full_name or anketa.company_name or ""
    return {
        "event": event,
        "anketa_id": anketa.id,
        "client_name": client_name,
        "client_type": anketa.client_type or "individual",
        "decision": anketa.decision,
        "dti": anketa.dti,
        "purchase_price": anketa.purchase_price,
        "down_payment_percent": anketa.down_payment_percent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _sign_payload(body: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={signature}"


def send_webhook(config: WebhookConfig, event: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode()
    headers = {"Content-Type": "application/json"}
    if config.secret:
        headers["X-Webhook-Signature"] = _sign_payload(body, config.secret)
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(config.url, content=body, headers=headers)
            logger.info("Webhook %s -> %s: %s", config.name, config.url, resp.status_code)
    except Exception:
        logger.exception("Webhook %s -> %s failed", config.name, config.url)


def notify_webhooks(db: Session, event: str, anketa: Anketa) -> None:
    configs = db.query(WebhookConfig).filter(WebhookConfig.is_active == True).all()
    payload = _build_payload(event, anketa)
    for cfg in configs:
        if cfg.events and cfg.events != "all":
            allowed = [e.strip() for e in cfg.events.split(",")]
            short_event = event.split(".")[-1] if "." in event else event
            if event not in allowed and short_event not in allowed:
                continue
        send_webhook(cfg, event, payload)
