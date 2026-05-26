"""
Descarcă PDF-ul hotărârii, extrage textul și identifică secțiunile
relevante despre confiscare, sechestru și bunuri.
"""
import io
import json
import logging
import re
from pathlib import Path

import httpx
import pdfplumber

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config" / "keywords.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def load_keywords() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def case_matches_filter(decision: dict, filter_keywords: list[str]) -> bool:
    """Verifică dacă dosarul conține cuvinte cheie în tematică sau denumire."""
    text = " ".join([
        decision.get("tematica_dosarului", ""),
        decision.get("denumirea_dosarului", ""),
    ]).lower()
    return any(kw.lower() in text for kw in filter_keywords)


async def analyze_case(decision: dict, keywords: dict) -> dict:
    """
    Descarcă PDF-ul și extrage informațiile relevante.
    Returnează un dict cu detaliile analizei.
    """
    url = decision.get("act_judecatoresc_url", "")
    result = {
        "dosar": decision,
        "pdf_url": url,
        "pdf_disponibil": bool(url),
        "text_extras": False,
        "pagini": 0,
        "keywords_gasite": [],
        "sectiuni_confiscare": [],
        "sectiuni_bunuri": [],
        "sectiuni_decizie": [],
        "eroare": None,
    }

    if not url:
        result["eroare"] = "Nu există link PDF"
        return result

    try:
        pdf_bytes = await _download_pdf(url)
        if not pdf_bytes:
            result["eroare"] = "PDF indisponibil (403/404)"
            return result

        text, pages = _extract_text(pdf_bytes)
        result["pagini"] = pages
        result["text_extras"] = bool(text)

        if not text:
            result["eroare"] = "PDF scanat (fără text selectabil)"
            return result

        result["keywords_gasite"] = _find_keywords(text, keywords["asset_keywords"])
        result["sectiuni_confiscare"] = _extract_sections(
            text,
            ["confiscat", "confiscă", "confiscarea", "sechestrat", "indisponibilizat",
             "aplică sechestru", "pune sechestru"],
            context_chars=500,
        )
        result["sectiuni_bunuri"] = _extract_sections(
            text,
            ["autoturism", "automobil", "imobil", "apartament", "teren", "lot",
             "mijloace bănești", "numerar", "cont bancar", "lei", "euro"],
            context_chars=400,
        )
        result["sectiuni_decizie"] = _extract_sections(
            text,
            ["dispune", "hotărăște", "condamnat", "achitat", "încetat",
             "pedeapsă", "amendă", "privațiune"],
            context_chars=600,
        )

    except Exception as exc:
        logger.error(f"Eroare la analiza PDF {url}: {exc}")
        result["eroare"] = str(exc)

    return result


async def _download_pdf(url: str) -> bytes | None:
    try:
        async with httpx.AsyncClient(
            headers=HEADERS,
            timeout=30,
            follow_redirects=True,
            verify=False,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and b"%PDF" in resp.content[:10]:
                return resp.content
            logger.warning(f"PDF status {resp.status_code}: {url}")
            return None
    except Exception as exc:
        logger.error(f"Download failed {url}: {exc}")
        return None


def _extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Returnează (text_complet, numar_pagini)."""
    pages_text = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n_pages = len(pdf.pages)
            for page in pdf.pages:
                t = page.extract_text() or ""
                pages_text.append(t)
        full_text = "\n".join(pages_text)
        return full_text, n_pages
    except Exception as exc:
        logger.error(f"Text extraction failed: {exc}")
        return "", 0


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    text_lower = text.lower()
    return sorted({kw for kw in keywords if kw.lower() in text_lower})


def _extract_sections(text: str, trigger_words: list[str], context_chars: int = 400) -> list[str]:
    """
    Pentru fiecare trigger word găsit în text, extrage un paragraf de context.
    Deduplicare: evită secțiuni care se suprapun.
    """
    sections = []
    text_lower = text.lower()
    used_positions: list[tuple[int, int]] = []

    for word in trigger_words:
        word_lower = word.lower()
        start = 0
        while True:
            pos = text_lower.find(word_lower, start)
            if pos == -1:
                break

            # Extinde la paragraf sau la context_chars
            begin = max(0, pos - context_chars // 2)
            end = min(len(text), pos + context_chars // 2)

            # Ajustează la granița propoziției/paragrafului
            begin = _find_sentence_start(text, begin)
            end = _find_sentence_end(text, end)

            # Verifică suprapunere cu secțiuni deja extrase
            overlaps = any(
                not (end <= u_start or begin >= u_end)
                for u_start, u_end in used_positions
            )
            if not overlaps:
                snippet = text[begin:end].strip()
                if len(snippet) > 50:
                    sections.append(_clean_text(snippet))
                    used_positions.append((begin, end))

            start = pos + len(word_lower)

    return sections[:10]  # maxim 10 secțiuni per categorie


def _find_sentence_start(text: str, pos: int) -> int:
    for char in ["\n\n", ".\n", ". "]:
        idx = text.rfind(char, 0, pos)
        if idx != -1:
            return idx + len(char)
    return pos


def _find_sentence_end(text: str, pos: int) -> int:
    for char in ["\n\n", ".\n"]:
        idx = text.find(char, pos)
        if idx != -1:
            return idx + len(char)
    dot = text.find(". ", pos)
    return dot + 2 if dot != -1 else min(pos + 50, len(text))


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()
