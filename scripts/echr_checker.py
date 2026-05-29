"""
ECHR Confiscation Checker
Queries HUDOC API for recent judgments related to confiscation/forfeiture.
Saves results to results/echr_YYYY-MM-DD.json and cleans up files older than 30 days.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests

HUDOC_API = "https://hudoc.echr.coe.int/app/query/results"

KEYWORDS = [
    "confiscation",
    "forfeiture",
    "confiscate",
    "proceeds of crime",
    "asset recovery",
    "confiscare",
    "bien confisqué",
    "confiscation des biens",
]

DOCUMENT_TYPES = ["GRANDCHAMBER", "CHAMBER", "COMMITTEE"]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
LOOKBACK_DAYS = 14


def build_query() -> str:
    # HUDOC query syntax: == exact match, ~ contains, space inside () = OR
    # Values must NOT be quoted for single words; quotes only for multi-word phrases
    def _q(s: str) -> str:
        return f'"{s}"' if " " in s else s

    keyword_clause = " ".join(f"fulltext~{_q(kw)}" for kw in KEYWORDS)
    doc_type_clause = " ".join(f"documentcollectionid2=={dt}" for dt in DOCUMENT_TYPES)
    # No language filter — avoids missing French-only or recently-published cases
    return (
        f"(contentsitename==ECHR) "
        f"({doc_type_clause}) "
        f"({keyword_clause})"
    )


def fetch_hudoc(query: str, start: int = 0, length: int = 500) -> dict:
    params = {
        "query": query,
        "select": (
            "itemid,docname,docdate,judgementdate,kpdate,importance,"
            "respondent,respondentOrderEng,applicability,"
            "conclusion,violation,nonviolation,scl,article"
        ),
        "sort": "kpdate Descending",  # sort by HUDOC publication date
        "start": start,
        "length": length,
        "rankingModelId": "BasicRank",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://hudoc.echr.coe.int/",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for attempt in range(4):
        try:
            response = requests.get(HUDOC_API, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if attempt == 3:
                raise
            wait = 2 ** (attempt + 1)
            print(f"Attempt {attempt + 1} failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)
    return {}


def parse_judgments(api_response: dict, cutoff: datetime) -> list[dict]:
    seen: set[str] = set()
    judgments = []
    for result in api_response.get("results", []):
        cols = result.get("columns", {})
        itemid = cols.get("itemid", "")

        # Deduplicate — same case may appear in multiple languages
        if itemid in seen:
            continue
        seen.add(itemid)

        # Use kpdate (HUDOC publication date) as primary; fall back to judgement/doc date
        kpdate_raw = cols.get("kpdate") or ""
        raw_date = kpdate_raw or cols.get("judgementdate") or cols.get("docdate") or ""
        date_str = raw_date[:10] if raw_date else ""

        if date_str:
            try:
                pub_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if pub_date < cutoff:
                    continue
            except ValueError:
                pass

        doc_date_str = (cols.get("judgementdate") or cols.get("docdate") or "")[:10]
        respondent = cols.get("respondentOrderEng") or cols.get("respondent") or ""
        conclusion = (cols.get("conclusion") or "").strip()

        judgments.append(
            {
                "itemid": itemid,
                "docname": cols.get("docname", ""),
                "docdate": doc_date_str,
                "kpdate": kpdate_raw[:10] if kpdate_raw else "",
                "importance": cols.get("importance", ""),
                "respondent": respondent,
                "applicability": (cols.get("applicability") or "").strip(),
                "conclusion": conclusion[:600],
                "violation": (cols.get("violation") or "")[:300],
                "nonviolation": (cols.get("nonviolation") or "")[:300],
                "scl": (cols.get("scl") or "").strip()[:300],
                "url": f"https://hudoc.echr.coe.int/eng?i={itemid}" if itemid else "",
            }
        )
    return judgments


def cleanup_old_results(days: int = 30) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for filename in os.listdir(RESULTS_DIR):
        if not (filename.startswith("echr_") and filename.endswith(".json")):
            continue
        date_str = filename.replace("echr_", "").replace(".json", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            if file_date < cutoff:
                os.remove(os.path.join(RESULTS_DIR, filename))
                print(f"Deleted old result file: {filename}")
        except ValueError:
            continue


def main() -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    date_label = now.strftime("%Y-%m-%d")

    print(f"Checking HUDOC for confiscation judgments (last {LOOKBACK_DAYS} days)...")
    print(f"Keywords: {', '.join(KEYWORDS)}")

    query = build_query()
    api_response = fetch_hudoc(query)
    total_api = api_response.get("resultcount", 0)
    judgments = parse_judgments(api_response, cutoff)

    print(f"API returned {total_api} total matches; {len(judgments)} within last {LOOKBACK_DAYS} days")

    output = {
        "date": date_label,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lookback_days": LOOKBACK_DAYS,
        "query_keywords": KEYWORDS,
        "total_api_results": total_api,
        "total_filtered": len(judgments),
        "judgments": judgments,
    }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(RESULTS_DIR, f"echr_{date_label}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"Results saved to {output_path}")

    cleanup_old_results(30)


if __name__ == "__main__":
    main()
