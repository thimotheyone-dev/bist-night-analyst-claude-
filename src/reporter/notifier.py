"""
Opsiyonel bildirim gönderimi. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID ortam
değişkenleri tanımlı değilse sessizce atlanır (zorunlu değildir).
"""

from __future__ import annotations

import logging

import requests

from config import settings

logger = logging.getLogger(__name__)


def send_telegram_message(text: str) -> bool:
    if not settings.NOTIFICATIONS_ENABLED:
        logger.info("Telegram bildirimleri yapılandırılmamış, atlanıyor.")
        return False

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("Telegram bildirimi gönderilemedi: %s", exc)
        return False


def notify_summary(summary: str, top_buys: list[str] | None = None) -> None:
    message = f"📊 *BIST Gece Taraması*\n\n{summary}"
    if top_buys:
        message += "\n\n*Öne çıkan AL sinyalleri:*\n" + "\n".join(f"• {t}" for t in top_buys)
    send_telegram_message(message)
