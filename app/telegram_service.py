"""Telegram notification service."""
import logging

import httpx
from sqlalchemy.orm import Session

from app.database import SystemSettings, User

logger = logging.getLogger(__name__)


def get_bot_token(db: Session) -> str | None:
    """Get Telegram bot token from SystemSettings."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == "telegram_bot_token").first()
    return setting.value if setting else None


def send_telegram_sync(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a message via Telegram Bot API (synchronous)."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = httpx.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
        if resp.status_code == 200:
            return True
        logger.warning("Telegram API returned %s: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)
    return False


def notify_telegram(db: Session, user_id: int, message: str):
    """Send Telegram notification to a specific user."""
    bot_token = get_bot_token(db)
    if not bot_token:
        return
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.telegram_chat_id:
        return
    send_telegram_sync(bot_token, user.telegram_chat_id, message)


def notify_telegram_many(db: Session, user_ids: list[int], message: str):
    """Send Telegram notification to multiple users."""
    bot_token = get_bot_token(db)
    if not bot_token:
        return
    users = db.query(User).filter(User.id.in_(user_ids), User.telegram_chat_id.isnot(None)).all()
    for user in users:
        if user.telegram_chat_id:
            send_telegram_sync(bot_token, user.telegram_chat_id, message)
