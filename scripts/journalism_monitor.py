#!/usr/bin/env python3
"""
Monitorizare zilnică a jurnalismului de investigație din Republica Moldova.
Scrapează sursele principale via RSS, analizează articolele, salvează JSON.
"""

import hashlib
import json
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
CONFIG_FILE = BASE_DIR / "config" / "journalism_sites.json"
RESULTS_DIR = BASE_DIR / "results" / "journalism"
LOOKBACK_HOURS = 26

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ARBI-JournalismMonitor/1.0; "
        "+https://github.com/nracu59-art/ARBI)"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
    "Accept-Language": "ro-MD,ro;q=0.9,en;q=0.8",
}

RSS_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}


# ─── Config Loading ───────────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


# ─── Date Parsing ─────────────────────────────────────────────────────────────

def parse_pubdate(raw: str) -> Optional[datetime]:
    """Parse various date formats from RSS feeds into UTC datetime."""
    if not raw:
        return None
    raw = raw.strip()

    # RFC 2822 (standard RSS)
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # ISO 8601
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw[:len(fmt)], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def is_recent(pub_dt: Optional[datetime], lookback_hours: int = LOOKBACK_HOURS) -> bool:
    if pub_dt is None:
        return True  # include if date unknown
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    return pub_dt >= cutoff


# ─── Text Cleaning ────────────────────────────────────────────────────────────

def strip_html(text: str) -> str:
    if not text:
        return ""
    clean = BeautifulSoup(text, "html.parser").get_text(separator=" ")
    return re.sub(r"\s+", " ", clean).strip()


def article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


# ─── Category Analysis ────────────────────────────────────────────────────────

def analyze_article(title: str, summary: str, categories_cfg: dict, inv_keywords: list) -> dict:
    text_lower = (title + " " + summary).lower()

    matched_categories = []
    for cat_key, cat_cfg in categories_cfg.items():
        score = sum(1 for kw in cat_cfg["keywords"] if kw.lower() in text_lower)
        if score > 0:
            matched_categories.append((cat_key, score))

    matched_categories.sort(key=lambda x: x[1], reverse=True)

    inv_score = sum(1 for kw in inv_keywords if kw.lower() in text_lower)

    return {
        "categories": [c[0] for c in matched_categories[:3]],
        "category_scores": {c[0]: c[1] for c in matched_categories},
        "investigative_score": inv_score,
        "relevance_score": sum(s for _, s in matched_categories) + inv_score * 2,
    }


# ─── RSS Fetching ─────────────────────────────────────────────────────────────

def fetch_rss(url: str, timeout: int = 20) -> Optional[ET.Element]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        content = resp.content

        # strip XML declaration encoding issues
        text = content.decode("utf-8", errors="replace")
        text = re.sub(r'<\?xml[^>]*\?>', '', text, count=1)

        root = ET.fromstring(text)
        return root
    except Exception as e:
        logger.warning("RSS fetch failed for %s: %s", url, e)
        return None


def parse_rss_items(root: ET.Element) -> list[dict]:
    """Parse items from RSS 2.0 or Atom feed."""
    items = []

    # RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")
            content_el = item.find("content:encoded", RSS_NS)
            dc_date_el = item.find("dc:date", RSS_NS)

            title = strip_html(title_el.text if title_el is not None else "")
            link = (link_el.text or "").strip() if link_el is not None else ""
            summary = strip_html(
                (content_el.text if content_el is not None else None)
                or (desc_el.text if desc_el is not None else "")
                or ""
            )[:800]

            raw_date = (
                (pubdate_el.text if pubdate_el is not None else None)
                or (dc_date_el.text if dc_date_el is not None else None)
                or ""
            )

            if title and link:
                items.append({
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "raw_date": raw_date,
                })
        return items

    # Atom feed
    atom_ns = "http://www.w3.org/2005/Atom"
    for entry in root.findall(f"{{{atom_ns}}}entry"):
        title_el = entry.find(f"{{{atom_ns}}}title")
        link_el = entry.find(f"{{{atom_ns}}}link")
        summary_el = entry.find(f"{{{atom_ns}}}summary")
        content_el = entry.find(f"{{{atom_ns}}}content")
        updated_el = entry.find(f"{{{atom_ns}}}updated")
        published_el = entry.find(f"{{{atom_ns}}}published")

        title = strip_html(title_el.text if title_el is not None else "")
        link = ""
        if link_el is not None:
            link = link_el.get("href", link_el.text or "")
        summary = strip_html(
            (content_el.text if content_el is not None else None)
            or (summary_el.text if summary_el is not None else "")
            or ""
        )[:800]
        raw_date = (
            (published_el.text if published_el is not None else None)
            or (updated_el.text if updated_el is not None else None)
            or ""
        )

        if title and link:
            items.append({
                "title": title,
                "url": link,
                "summary": summary,
                "raw_date": raw_date,
            })

    return items


# ─── Article Summary Fetching ────────────────────────────────────────────────

ARTICLE_CONTENT_SELECTORS = [
    "article .entry-content",
    "article .post-content",
    "article .article-body",
    "article .article-content",
    ".entry-content",
    ".post-content",
    ".article-body",
    ".article-content",
    ".article-text",
    ".story-body",
    ".content-body",
    "article",
    "[itemprop='articleBody']",
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro-MD,ro;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def fetch_article_summary(url: str, timeout: int = 12) -> str:
    """Fetch article page and extract first meaningful paragraph as summary."""
    try:
        resp = requests.get(url, headers=BROWSER_HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "nav", "header", "footer",
                                   "aside", "figure", "figcaption", ".ad", ".ads"]):
            tag.decompose()

        # Try known content selectors
        content_el = None
        for selector in ARTICLE_CONTENT_SELECTORS:
            content_el = soup.select_one(selector)
            if content_el:
                break

        # Fall back to <main> or <body>
        if not content_el:
            content_el = soup.find("main") or soup.find("body")

        if not content_el:
            return ""

        # Find first substantial paragraph (min 60 chars, not nav/caption text)
        for p in content_el.find_all("p"):
            text = p.get_text(separator=" ", strip=True)
            text = re.sub(r"\s+", " ", text)
            if len(text) >= 60 and not text.startswith(("©", "Foto:", "Sursa:", "Tags:")):
                # Return first 2 sentences, max 280 chars
                sentences = re.split(r"(?<=[.!?])\s+", text)
                summary = " ".join(sentences[:2])
                return summary[:280] + ("…" if len(summary) > 280 else "")

        return ""
    except Exception as e:
        logger.debug("Could not fetch summary for %s: %s", url, e)
        return ""


def enrich_summaries(articles: list[dict], max_enriched: int = 30) -> None:
    """Fetch summaries for articles that have short/empty summaries from RSS."""
    enriched = 0
    for article in articles:
        if enriched >= max_enriched:
            break
        if len(article.get("summary", "")) >= 80:
            continue  # already has a good summary
        url = article.get("url", "")
        if not url:
            continue
        logger.info("Fetching summary for: %s", article["title"][:60])
        fetched = fetch_article_summary(url)
        if fetched:
            article["summary"] = fetched
            enriched += 1
        time.sleep(0.5)
    logger.info("Enriched %d article summaries", enriched)


# ─── HTML Fallback Scraping ───────────────────────────────────────────────────

def scrape_html_articles(site: dict, timeout: int = 20) -> list[dict]:
    """Fallback HTML scraper for sites without working RSS."""
    try:
        resp = requests.get(site["url"], headers={**HEADERS, "Accept": "text/html"}, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        items = []
        # Try common article patterns
        for article in soup.find_all(["article", "div"], class_=re.compile(r"post|article|news|item", re.I))[:20]:
            title_el = article.find(["h1", "h2", "h3", "h4"])
            link_el = article.find("a", href=True)
            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            href = link_el["href"]
            if not href.startswith("http"):
                href = site["url"].rstrip("/") + "/" + href.lstrip("/")

            summary_el = article.find(["p", "div"], class_=re.compile(r"excerpt|summary|desc|text", re.I))
            summary = summary_el.get_text(strip=True)[:400] if summary_el else ""

            time_el = article.find(["time", "span"], attrs={"datetime": True})
            raw_date = time_el.get("datetime", "") if time_el else ""

            if title and href:
                items.append({"title": title, "url": href, "summary": summary, "raw_date": raw_date})

        return items
    except Exception as e:
        logger.warning("HTML fallback failed for %s: %s", site["url"], e)
        return []


# ─── Site Scraping ────────────────────────────────────────────────────────────

def scrape_site(site: dict, categories_cfg: dict, inv_keywords: list) -> list[dict]:
    logger.info("Scraping: %s (%s)", site["name"], site.get("rss", "no RSS"))
    raw_items = []

    if site.get("rss"):
        root = fetch_rss(site["rss"])
        if root is not None:
            raw_items = parse_rss_items(root)

    if not raw_items:
        logger.info("RSS empty/failed, trying HTML fallback for %s", site["name"])
        raw_items = scrape_html_articles(site, timeout=15)

    articles = []
    for item in raw_items:
        pub_dt = parse_pubdate(item.get("raw_date", ""))

        if not is_recent(pub_dt):
            continue

        pub_str = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ") if pub_dt else ""
        pub_date = pub_str[:10] if pub_str else ""

        analysis = analyze_article(
            item["title"], item.get("summary", ""),
            categories_cfg, inv_keywords
        )

        articles.append({
            "id": article_id(item["url"]),
            "title": item["title"],
            "url": item["url"],
            "source": site["name"],
            "source_key": site["key"],
            "published": pub_str,
            "published_date": pub_date,
            "summary": item.get("summary", "")[:500],
            "categories": analysis["categories"],
            "category_scores": analysis["category_scores"],
            "investigative_score": analysis["investigative_score"],
            "relevance_score": analysis["relevance_score"],
        })

    logger.info("  → %d articles in last %dh from %s", len(articles), LOOKBACK_HOURS, site["name"])
    return articles


# ─── Statistics ───────────────────────────────────────────────────────────────

def compute_stats(articles: list[dict], sites: list[dict], categories_cfg: dict) -> dict:
    by_source = {}
    for s in sites:
        count = sum(1 for a in articles if a["source_key"] == s["key"])
        if count:
            by_source[s["key"]] = {"name": s["name"], "count": count}

    by_category = {}
    for cat_key, cat_cfg in categories_cfg.items():
        count = sum(1 for a in articles if cat_key in a.get("categories", []))
        if count:
            by_category[cat_key] = {"label": cat_cfg["label"], "emoji": cat_cfg["emoji"], "count": count}

    investigative = sum(1 for a in articles if a.get("investigative_score", 0) > 0)

    return {
        "total": len(articles),
        "investigative": investigative,
        "by_source": by_source,
        "by_category": by_category,
    }


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    cfg = load_config()
    sites = cfg["sites"]
    categories_cfg = cfg["categories"]
    inv_keywords = cfg.get("investigative_keywords", [])

    all_articles = []
    seen_urls = set()
    sources_checked = 0
    sources_ok = 0

    for site in sites:
        sources_checked += 1
        try:
            articles = scrape_site(site, categories_cfg, inv_keywords)
            sources_ok += len(articles) >= 0  # always count
            for a in articles:
                if a["url"] not in seen_urls:
                    seen_urls.add(a["url"])
                    all_articles.append(a)
        except Exception as e:
            logger.error("Error scraping %s: %s", site["name"], e)
        time.sleep(1)

    # Sort: investigative first, then by relevance
    all_articles.sort(key=lambda a: (-(a.get("investigative_score", 0)), -a.get("relevance_score", 0)))

    # Enrich summaries for articles that have short/empty descriptions from RSS
    if all_articles:
        enrich_summaries(all_articles)

    now_utc = datetime.now(timezone.utc)
    stats = compute_stats(all_articles, sites, categories_cfg)

    result = {
        "date": now_utc.strftime("%Y-%m-%d"),
        "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lookback_hours": LOOKBACK_HOURS,
        "sources_checked": sources_checked,
        "sources_ok": sources_ok,
        "stats": stats,
        "articles": all_articles,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"journalism_{now_utc.strftime('%Y-%m-%d')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info("Results saved: %s (%d articles)", out_path, len(all_articles))

    # Clean up files older than 30 days
    cutoff_date = now_utc - timedelta(days=30)
    for old_file in RESULTS_DIR.glob("journalism_*.json"):
        try:
            file_date_str = old_file.stem.replace("journalism_", "")
            file_date = datetime.strptime(file_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff_date:
                old_file.unlink()
                logger.info("Deleted old result: %s", old_file.name)
        except (ValueError, OSError):
            pass

    return result


if __name__ == "__main__":
    main()
