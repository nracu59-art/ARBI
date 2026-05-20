import asyncio
import logging
import os
import sys
from datetime import date, timedelta

import httpx
from dotenv import load_dotenv

from scraper import scrape_decisions
from analyzer import analyze
from formatter import format_messages

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        logger.error(f"Missing required environment variable: {name}")
        sys.exit(1)
    return value


async def send_message(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            logger.error(f"Telegram API error {resp.status_code}: {resp.text}")
            resp.raise_for_status()


async def main() -> None:
    token = _require("TELEGRAM_BOT_TOKEN")
    chat_id = _require("TELEGRAM_CHAT_ID")

    target_date = date.today() - timedelta(days=1)
    logger.info(f"Target date: {target_date.strftime('%d.%m.%Y')}")

    decisions = await scrape_decisions(target_date)
    stats = analyze(decisions)
    messages = format_messages(decisions, stats, target_date)

    logger.info(f"Sending {len(messages)} message(s) — {stats['total']} decisions found")
    for i, msg in enumerate(messages, 1):
        await send_message(token, chat_id, msg)
        logger.info(f"Sent message {i}/{len(messages)}")
        if i < len(messages):
            await asyncio.sleep(1)  # stay within Telegram rate limits

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
