"""
ECHR Telegram Reporter
Reads the latest results JSON and sends a formatted report to a Telegram chat.
"""

import json
import os
from datetime import datetime

import requests

TELEGRAM_API = "https://api.telegram.org"
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
MAX_MESSAGE_LENGTH = 4096
SEPARATOR = "━" * 22


def send_message(bot_token: str, chat_id: str, text: str) -> None:
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()


def send_long_message(bot_token: str, chat_id: str, text: str) -> None:
    """Split message into chunks if it exceeds Telegram's limit."""
    if len(text) <= MAX_MESSAGE_LENGTH:
        send_message(bot_token, chat_id, text)
        return
    chunks = []
    while text:
        if len(text) <= MAX_MESSAGE_LENGTH:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_at == -1:
            split_at = MAX_MESSAGE_LENGTH
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    for i, chunk in enumerate(chunks, 1):
        prefix = f"<b>[{i}/{len(chunks)}]</b>\n" if len(chunks) > 1 else ""
        send_message(bot_token, chat_id, prefix + chunk)


def format_date_ro(date_str: str) -> str:
    """Convert YYYY-MM-DD to Romanian format DD.MM.YYYY."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except ValueError:
        return date_str


def format_report(data: dict) -> str:
    date_label = format_date_ro(data.get("date", ""))
    checked_at = data.get("checked_at", "")[:16].replace("T", " ")
    total = data.get("total_found", 0)
    judgments = data.get("judgments", [])

    header = (
        f"⚖️ <b>Raport CEDO - {date_label}</b>\n"
        f"📊 Hotărâri noi despre confiscare: <b>{total}</b>\n"
        f"🕙 Verificat la: {checked_at} UTC\n"
        f"{SEPARATOR}"
    )

    if total == 0:
        return (
            f"{header}\n\n"
            "❌ Nu au fost găsite hotărâri noi despre confiscare în ultimele 24 ore.\n"
            f"\n{SEPARATOR}\n"
            "🔍 Sursa: hudoc.echr.coe.int"
        )

    lines = [header, ""]
    for i, j in enumerate(judgments, 1):
        respondent = j.get("respondent", "N/A")
        doc_date = format_date_ro(j.get("docdate", ""))
        conclusion = j.get("conclusion", "").strip()
        applicability = j.get("applicability", "").strip()
        url = j.get("url", "")
        docname = j.get("docname", "N/A")

        entry = [f"<b>{i}. {docname}</b>"]
        if doc_date:
            entry.append(f"📅 Data: {doc_date} | 🏳️ Stat: {respondent}")
        if applicability:
            entry.append(f"📌 Articole: {applicability[:150]}")
        if conclusion:
            display_conclusion = conclusion[:300] + "..." if len(conclusion) > 300 else conclusion
            entry.append(f"📋 Concluzii: {display_conclusion}")
        if url:
            entry.append(f'🔗 <a href="{url}">Accesează hotărârea</a>')
        lines.extend(entry)
        lines.append("")

    if total > len(judgments):
        lines.append(
            f"... și alte {total - len(judgments)} hotărâri. "
            f'<a href="https://hudoc.echr.coe.int">Accesează HUDOC</a>'
        )
        lines.append("")

    lines.append(SEPARATOR)
    lines.append("🔍 Sursa: hudoc.echr.coe.int")
    return "\n".join(lines)


def find_latest_results() -> str | None:
    if not os.path.isdir(RESULTS_DIR):
        return None
    files = sorted(
        f for f in os.listdir(RESULTS_DIR)
        if f.startswith("echr_") and f.endswith(".json")
    )
    return os.path.join(RESULTS_DIR, files[-1]) if files else None


def main() -> None:
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    latest = find_latest_results()
    if not latest:
        send_long_message(
            bot_token, chat_id,
            "⚠️ <b>ECHR Monitor</b>\n\nNu s-a găsit niciun fișier de rezultate.\n"
            "Este posibil că verificarea din seara precedentă a eșuat."
        )
        return

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    message = format_report(data)
    send_long_message(bot_token, chat_id, message)
    print(f"Report sent from {latest}")


if __name__ == "__main__":
    main()
