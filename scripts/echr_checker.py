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
    "seizure of property",
    "proceeds of crime",
]

DOCUMENT_TYPES = ["GRANDCHAMBER", "CHAMBER", "COMMITTEE"]

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def build_query(date_from: str, date_to: str) -> str:
    keyword_clause = " ".join(f'fulltext~"{kw}"' for kw in KEYWORDS)
    doc_type_clause = " ".join(
        f'documentcollectionid2:"{dt}"' for dt in DOCUMENT_TYPES
    )
    return (
        f"(contentsitename==ECHR) "
        f"(languageisocode==ENG) "
        f"({doc_type_clause}) "
        f"({keyword_clause}) "
        f'(kpdate>="{date_from}") '
        f'(kpdate<="{date_to}")'
    )


def fetch_hudoc(query: str, start: int = 0, length: int = 100) -> dict:
    params = {
        "query": query,
        "select": "itemid,docname,docdate,importance,respondent,scl,applicability,conclusion,Rank",
        "sort": "docdate Descending",
        "start": start,
        "length": length,
        "rankingModelId": "BasicRank",
    }
    headers = {
        "User-Agent": "ECHR-Monitor/1.0 (automated court verification)",
        "Accept": "application/json",
    }
    for attempt in range(3):
        try:
            response = requests.get(HUDOC_API, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            if attempt == 2:
                raise
            wait = 2 ** (attempt + 1)
            print(f"Attempt {attempt + 1} failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)
    return {}


def parse_judgments(api_response: dict) -> list[dict]:
    judgments = []
    for result in api_response.get("results", []):
        cols = result.get("columns", {})
        itemid = cols.get("itemid", "")
        raw_date = cols.get("docdate", "") or ""
        doc_date = raw_date[:10] if raw_date else ""
        conclusion = cols.get("conclusion", "") or ""
        judgments.append(
            {
                "itemid": itemid,
                "docname": cols.get("docname", ""),
                "docdate": doc_date,
                "respondent": cols.get("respondent", ""),
                "applicability": cols.get("applicability", ""),
                "conclusion": conclusion[:500],
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
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                os.remove(os.path.join(RESULTS_DIR, filename))
                print(f"Deleted old result file: {filename}")
        except ValueError:
            continue


def main() -> None:
    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(hours=24)).strftime("%Y-%m-%dT00:00:00.0Z")
    date_to = now.strftime("%Y-%m-%dT23:59:59.0Z")
    date_label = now.strftime("%Y-%m-%d")

    print(f"Checking HUDOC for confiscation judgments from {date_from} to {date_to}")

    query = build_query(date_from, date_to)
    api_response = fetch_hudoc(query)
    total_found = api_response.get("resultcount", 0)
    judgments = parse_judgments(api_response)

    print(f"Found {total_found} judgment(s)")

    output = {
        "date": date_label,
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "query_keywords": KEYWORDS,
        "total_found": total_found,
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
