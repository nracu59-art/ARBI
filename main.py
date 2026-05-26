import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv

from scraper import scrape_decisions
from analyzer import analyze
from formatter import format_messages
from pdf_analyzer import load_keywords, case_matches_filter, analyze_case

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
# Numărul maxim de PDF-uri analizate per rulare (evită timeout în Actions)
MAX_PDF_ANALYSES = 30


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


async def run_pdf_analysis(decisions: list[dict], target_date: date) -> None:
    """Filtrează dosarele relevante, analizează PDF-urile și generează raportul HTML."""
    try:
        from scripts.generate_court_report import generate as generate_report
    except ImportError:
        import importlib.util, sys as _sys
        spec = importlib.util.spec_from_file_location(
            "generate_court_report",
            Path(__file__).parent / "scripts" / "generate_court_report.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        generate_report = mod.generate

    keywords = load_keywords()
    filter_kws = keywords["case_filter"]

    # Filtrare dosare relevante
    relevant = [d for d in decisions if case_matches_filter(d, filter_kws)]
    logger.info(f"Dosare relevante (cu cuvinte cheie): {len(relevant)} din {len(decisions)}")

    if not relevant:
        logger.info("Niciun dosar relevant — raport HTML nu se generează")
        return None

    # Limitează numărul de PDF-uri analizate
    to_analyze = relevant[:MAX_PDF_ANALYSES]
    if len(relevant) > MAX_PDF_ANALYSES:
        logger.warning(f"Analizez doar primele {MAX_PDF_ANALYSES} din {len(relevant)} dosare")

    # Analizează PDF-urile în paralel (batch de 5 pentru a nu supraîncărca)
    analyses = []
    batch_size = 5
    for i in range(0, len(to_analyze), batch_size):
        batch = to_analyze[i:i + batch_size]
        results = await asyncio.gather(
            *[analyze_case(d, keywords) for d in batch],
            return_exceptions=True,
        )
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"PDF analysis exception: {r}")
            else:
                analyses.append(r)
        logger.info(f"  Analizat {min(i + batch_size, len(to_analyze))}/{len(to_analyze)} PDF-uri")

    # Generează HTML
    report_path = generate_report(analyses, target_date)
    logger.info(f"Raport HTML generat: {report_path}")
    return report_path


async def main() -> None:
    token   = _require("TELEGRAM_BOT_TOKEN")
    chat_id = _require("TELEGRAM_CHAT_ID")

    target_date = date.today() - timedelta(days=1)
    logger.info(f"Target date: {target_date.strftime('%d.%m.%Y')}")

    # ── 1. Scraping hotărâri penale ──────────────────────────────────────────
    decisions = await scrape_decisions(target_date)
    stats     = analyze(decisions)
    messages  = format_messages(decisions, stats, target_date)

    # ── 2. Trimite rapoartele Telegram ───────────────────────────────────────
    logger.info(f"Sending {len(messages)} Telegram message(s) — {stats['total']} decisions")
    for i, msg in enumerate(messages, 1):
        await send_message(token, chat_id, msg)
        logger.info(f"Sent message {i}/{len(messages)}")
        if i < len(messages):
            await asyncio.sleep(1)

    # ── 3. Analiză PDF + raport HTML ─────────────────────────────────────────
    if decisions:
        report_path = await run_pdf_analysis(decisions, target_date)
        if report_path:
            date_ro = target_date.strftime("%d.%m.%Y")
            summary_msg = (
                f"📊 <b>Raport PDF — Confiscare &amp; Sechestru</b>\n"
                f"📅 {date_ro}\n"
                f"📁 <code>{report_path.name}</code>\n\n"
                f"Raportul HTML a fost salvat în repo la:\n"
                f"<code>reports/{report_path.name}</code>"
            )
            await send_message(token, chat_id, summary_msg)
            logger.info("PDF analysis summary sent to Telegram")

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
