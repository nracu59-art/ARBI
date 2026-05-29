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

HUDOC_BASE = "https://hudoc.echr.coe.int"
HUDOC_API = f"{HUDOC_BASE}/app/query/results"

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
    def _q(s: str) -> str:
        return f'"{s}"' if " " in s else s

    keyword_clause = " ".join(f"fulltext~{_q(kw)}" for kw in KEYWORDS)
    doc_type_clause = " ".join(f"documentcollectionid2=={dt}" for dt in DOCUMENT_TYPES)
    return (
        f"(contentsitename==ECHR) "
        f"({doc_type_clause}) "
        f"({keyword_clause})"
    )


def make_session() -> requests.Session:
    """Initialize a session with HUDOC cookies, mimicking a browser visit."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        # Visit the HUDOC homepage to obtain session cookies
        r = session.get(
            f"{HUDOC_BASE}/eng",
            headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            timeout=20,
            allow_redirects=True,
        )
        print(f"  Session init: HTTP {r.status_code}, cookies={list(session.cookies.keys())}")
    except Exception as exc:
        print(f"  Session init failed (continuing anyway): {exc}")
    return session


def fetch_hudoc(session: requests.Session, query: str, start: int = 0, length: int = 500) -> dict:
    params = {
        "query": query,
        "select": (
            "itemid,docname,docdate,judgementdate,kpdate,importance,"
            "respondent,respondentOrderEng,applicability,"
            "conclusion,violation,nonviolation,scl,article"
        ),
        "sort": "kpdate Descending",
        "start": start,
        "length": length,
        "rankingModelId": "BasicRank",
    }
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"{HUDOC_BASE}/eng",
    }
    for attempt in range(4):
        try:
            response = session.get(HUDOC_API, params=params, headers=headers, timeout=30)
            print(f"  HTTP {response.status_code} | {len(response.content)} bytes")
            if not response.content:
                print("  Empty response body")
                time.sleep(2 ** (attempt + 1))
                continue
            response.raise_for_status()
            data = response.json()
            msg = data.get("message", "")
            print(f"  resultcount={data.get('resultcount')} | message={msg!r}")
            return data
        except requests.RequestException as exc:
            if attempt == 3:
                raise
            wait = 2 ** (attempt + 1)
            print(f"  Attempt {attempt + 1} failed: {exc}. Retrying in {wait}s...")
            time.sleep(wait)
        except ValueError as exc:
            print(f"  JSON decode error: {exc} | body: {response.text[:200]}")
            raise
    return {}


def parse_judgments(api_response: dict, cutoff: datetime) -> list[dict]:
    seen: set[str] = set()
    judgments = []
    for result in api_response.get("results", []):
        cols = result.get("columns", {})
        itemid = cols.get("itemid", "")

        if itemid in seen:
            continue
        seen.add(itemid)

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
                "url": f"{HUDOC_BASE}/eng?i={itemid}" if itemid else "",
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
    cutoff = now - timedelta(days=LOOKBACK_DAYS)
    date_label = now.strftime("%Y-%m-%d")

    print(f"Checking HUDOC for confiscation judgments (last {LOOKBACK_DAYS} days)...")
    print(f"Keywords: {', '.join(KEYWORDS)}")

    session = make_session()

    # Diagnostic: test multiple query formats to find which one HUDOC accepts
    test_queries = [
        ("bare keyword",          "confiscation"),
        ("no contentsitename",    "(documentcollectionid2==GRANDCHAMBER documentcollectionid2==CHAMBER) (fulltext~confiscation)"),
        ("specific itemid",       "contentsitename==ECHR itemid==001-250210"),
        ("no rankingModel flag",  "(contentsitename==ECHR)(documentcollectionid2==GRANDCHAMBER)(fulltext~confiscation)"),
        ("colon operator",        "documentcollectionid2:GRANDCHAMBER fulltext:confiscation"),
    ]
    for label, tq in test_queries:
        try:
            r = session.get(
                HUDOC_API,
                params={"query": tq, "select": "itemid,docname", "start": 0, "length": 3, "rankingModelId": "BasicRank"},
                headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest", "Referer": f"{HUDOC_BASE}/eng"},
                timeout=15,
            )
            d = r.json() if r.content else {}
            print(f"  [{label}] HTTP {r.status_code} | {len(r.content)}b | resultcount={d.get('resultcount')}")
        except Exception as exc:
            print(f"  [{label}] ERROR: {exc}")
        time.sleep(1)

    query = build_query()
    print(f"Query: {query}")

    api_response = fetch_hudoc(session, query)
    total_api = api_response.get("resultcount", 0)
    judgments = parse_judgments(api_response, cutoff)

    print(f"API returned {total_api} total; {len(judgments)} within last {LOOKBACK_DAYS} days")

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
