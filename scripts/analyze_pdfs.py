"""
ECHR PDF Analyzer
Downloads judgment PDFs from HUDOC, extracts confiscation/seizure passages,
and generates a detailed Romanian HTML analysis report.
"""

import io
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber
import requests

HUDOC_BASE = "https://hudoc.echr.coe.int"
RESULTS_DIR = Path(__file__).parent.parent / "results"
REPORTS_DIR = Path(__file__).parent.parent / "reports"
MAX_JUDGMENTS = 30
REQUEST_DELAY = 2  # seconds between PDF downloads

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Referer": "https://hudoc.echr.coe.int/",
    "Accept-Language": "en-US,en;q=0.9",
}

# Romanian labels for matched term categories
TERM_MAP: list[tuple[str, str]] = [
    (r"\bconfiscat\w*\b",                 "Confiscare"),
    (r"\bforfeiture\b|\bforfeit\w*\b",    "Confiscare penală"),
    (r"\bseizure\b|\bseize[ds]?\b|\bseizing\b|\battachment\b", "Sechestru"),
    (r"\bproceeds of crime\b|\billicit proceeds\b",            "Produse ale infracțiunii"),
    (r"\basset recover\w*\b|\brecovery of assets\b",           "Recuperare active"),
    (r"\bfrozen assets\b|\bfreezing order\b|\bfreeze\b",       "Înghețare active"),
    (r"\bArticle 1 of Protocol No\.?\s*1\b",                   "Protocol 1 – Drept proprietate"),
    (r"\bpecuniary damage\b|\bjust satisfaction\b",            "Reparație echitabilă"),
    (r"\bcompensation\b",                                      "Compensație"),
]

COMBINED_RE = re.compile(
    "|".join(pattern for pattern, _ in TERM_MAP),
    re.IGNORECASE,
)


# ── PDF Download ─────────────────────────────────────────────

def _try_get(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
        if r.status_code == 200 and r.content[:4] in (b"%PDF", b"\x25\x50\x44\x46"):
            return r.content
    except requests.RequestException:
        pass
    return None


def download_pdf(itemid: str, docname: str) -> bytes | None:
    safe = re.sub(r"[^\w\-]", "_", docname)[:80]
    candidates = [
        f"{HUDOC_BASE}/app/conversion/docx/pdf?library=ECHR&id={itemid}&filename={safe}.pdf",
        f"{HUDOC_BASE}/app/conversion/pdf?library=ECHR&id={itemid}",
        f"{HUDOC_BASE}/app/conversion/docx/pdf?library=ECHR&id={itemid}",
    ]
    for url in candidates:
        data = _try_get(url)
        if data:
            return data
        time.sleep(0.5)
    return None


# ── Text Extraction ───────────────────────────────────────────

def extract_text(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            parts = [p.extract_text() for p in pdf.pages if p.extract_text()]
            return "\n\n".join(parts)
    except Exception as exc:
        print(f"  PDF extraction error: {exc}")
        return ""


# ── Passage Finder ────────────────────────────────────────────

def find_passages(text: str) -> list[dict]:
    if not text:
        return []

    paragraphs = re.split(r"\n{2,}|\r\n{2,}", text)
    results = []

    for raw in paragraphs:
        para = raw.strip()
        if len(para) < 80:
            continue
        matches = COMBINED_RE.findall(para)
        if not matches:
            continue

        categories: set[str] = set()
        for pattern, label in TERM_MAP:
            if re.search(pattern, para, re.IGNORECASE):
                categories.add(label)

        results.append({
            "text": para[:900],
            "categories": sorted(categories),
            "hits": len(matches),
        })

    results.sort(key=lambda x: x["hits"], reverse=True)
    return results[:12]


# ── HTML Report ───────────────────────────────────────────────

_HTML_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #2c3e50; }
.hdr { background: #1a3a5c; color: #fff; padding: 24px 40px; }
.hdr h1 { font-size: 1.45rem; font-weight: 700; }
.hdr small { font-size: 0.82rem; opacity: .8; }
.bar { background: #2c5282; color: #fff; padding: 14px 40px;
       display: flex; gap: 36px; flex-wrap: wrap; }
.bar .v { font-size: 1.7rem; font-weight: 700; }
.bar .l { font-size: .68rem; opacity: .75; text-transform: uppercase; letter-spacing: .8px; }
.wrap { max-width: 1000px; margin: 26px auto; padding: 0 18px 60px; }
.card { background: #fff; border-radius: 10px; margin-bottom: 26px;
        box-shadow: 0 2px 10px rgba(0,0,0,.08); border-top: 4px solid #1a3a5c; }
.ch { display: flex; align-items: flex-start; gap: 14px; padding: 18px 22px 0; }
.num { background: #1a3a5c; color: #fff; border-radius: 50%; width: 34px; height: 34px;
       display: flex; align-items: center; justify-content: center;
       font-weight: 700; font-size: .85rem; flex-shrink: 0; }
.ct h2 { font-size: .98rem; font-weight: 700; }
.ct h2 a { color: #1a3a5c; text-decoration: none; }
.ct h2 a:hover { text-decoration: underline; }
.meta { font-size: .78rem; color: #666; margin-top: 3px; display: flex; gap: 12px; flex-wrap: wrap; }
.sec { padding: 14px 22px; border-top: 1px solid #f0f0f0; }
.sec h3 { font-size: .78rem; text-transform: uppercase; letter-spacing: .8px;
           color: #1a3a5c; margin-bottom: 8px; }
.sec ul { padding-left: 16px; font-size: .82rem; line-height: 1.65; }
.asec { background: #fafbfc; }
.asec h3 { color: #c0392b; }
.passage { background: #fff; border-left: 3px solid #c0392b;
           padding: 10px 14px; margin-bottom: 9px; border-radius: 0 5px 5px 0;
           font-size: .81rem; line-height: 1.72; }
.badge { display: inline-block; background: #c0392b; color: #fff;
         font-size: .66rem; padding: 1px 7px; border-radius: 9px;
         margin-bottom: 5px; font-weight: 600; }
.nodata { color: #999; font-size: .82rem; font-style: italic; }
.btn { display: inline-block; margin: 14px 22px 18px; padding: 6px 16px;
       background: #1a3a5c; color: #fff; border-radius: 5px;
       font-size: .78rem; text-decoration: none; font-weight: 600; }
.btn:hover { background: #2c5282; }
.empty { text-align: center; padding: 40px; color: #999; font-size: .9rem; }
footer { text-align: center; font-size: .72rem; color: #aaa; padding-bottom: 20px; }
@media (max-width: 600px) { .hdr, .bar { padding: 16px 18px; } }
"""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _date_ro(s: str) -> str:
    try:
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d.%m.%Y")
    except Exception:
        return s or "–"


def render_card(idx: int, j: dict) -> str:
    url = j.get("url", "")
    title = _escape(j.get("docname") or "Hotărâre CEDO")
    date = _date_ro(j.get("docdate", ""))
    respondent = _escape(j.get("respondent") or "–")
    paragraphs = j.get("paragraphs", [])
    pdf_status = j.get("pdf_status", "")

    details = []
    for key, label in [("applicability", "Articole"), ("conclusion", "Concluzie"),
                       ("violation", "Violări"), ("nonviolation", "Neviolări")]:
        val = (j.get(key) or "").strip()
        if val:
            details.append(f"<li><strong>{label}:</strong> {_escape(val[:250])}</li>")

    details_html = "<ul>" + "".join(details) + "</ul>" if details else "<p class='nodata'>–</p>"

    if paragraphs:
        items = []
        for p in paragraphs:
            cats = ", ".join(p.get("categories", []))
            badge = f'<span class="badge">{_escape(cats)}</span>' if cats else ""
            items.append(f'<div class="passage">{badge}<p>{_escape(p["text"])}</p></div>')
        analysis = '<div class="sec asec"><h3>🔍 Pasaje relevante – Confiscare / Sechestru</h3>' + "".join(items) + "</div>"
    else:
        note = _escape(pdf_status) if pdf_status else "PDF indisponibil pe HUDOC"
        analysis = f'<div class="sec asec"><h3>🔍 Analiză text</h3><p class="nodata">⚠️ {note} — accesați hotărârea completă pentru detalii.</p></div>'

    link = f'<a class="btn" href="{url}" target="_blank">Hotărârea completă →</a>' if url else ""

    return f"""<div class="card">
  <div class="ch">
    <span class="num">{idx}</span>
    <div class="ct">
      <h2><a href="{url}" target="_blank">{title}</a></h2>
      <div class="meta"><span>📅 {date}</span><span>🏳️ {respondent}</span></div>
    </div>
  </div>
  <div class="sec"><h3>📋 Date generale</h3>{details_html}</div>
  {analysis}
  {link}
</div>"""


def build_html(records: list[dict], report_date: str) -> str:
    date_ro = _date_ro(report_date)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    total = len(records)
    with_text = sum(1 for r in records if r.get("paragraphs"))

    if records:
        body = "\n".join(render_card(i + 1, r) for i, r in enumerate(records))
    else:
        body = '<div class="empty">Nu au fost găsite hotărâri pentru analiză în perioada selectată.</div>'

    return f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Analiză CEDO – Confiscare – {date_ro}</title>
<style>{_HTML_CSS}</style>
</head>
<body>
<div class="hdr">
  <h1>⚖️ Analiză CEDO – Confiscare &amp; Sechestru</h1>
  <small>Sursa: hudoc.echr.coe.int &nbsp;·&nbsp; Generat: {now} UTC</small>
</div>
<div class="bar">
  <div><span class="v">{total}</span><br><span class="l">Hotărâri verificate</span></div>
  <div><span class="v">{with_text}</span><br><span class="l">Analizate cu text</span></div>
  <div><span class="v">{date_ro}</span><br><span class="l">Data raport</span></div>
</div>
<div class="wrap">{body}</div>
<footer>Analiză automată · CEDO Monitor · <a href="https://hudoc.echr.coe.int">hudoc.echr.coe.int</a></footer>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────

def find_latest_results() -> Path | None:
    if not RESULTS_DIR.is_dir():
        return None
    files = sorted(RESULTS_DIR.glob("echr_*.json"))
    return files[-1] if files else None


def main() -> None:
    latest = find_latest_results()
    if not latest:
        print("No result JSON found — skipping analysis.")
        return

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    judgments = data.get("judgments", [])[:MAX_JUDGMENTS]
    report_date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    print(f"Analyzing {len(judgments)} judgment(s) from {latest.name}")

    records: list[dict] = []
    for j in judgments:
        itemid = j.get("itemid", "")
        docname = j.get("docname", "judgment")
        print(f"  [{itemid}] {docname[:60]}")

        record = dict(j)
        record["paragraphs"] = []
        record["pdf_status"] = ""

        if itemid:
            pdf = download_pdf(itemid, docname)
            if pdf:
                text = extract_text(pdf)
                if text:
                    record["paragraphs"] = find_passages(text)
                    record["pdf_status"] = f"OK ({len(text)//1000}k chars)"
                    print(f"    → {len(record['paragraphs'])} relevant passage(s)")
                else:
                    record["pdf_status"] = "Text neextras din PDF"
                    print("    → text extraction failed")
            else:
                record["pdf_status"] = "PDF indisponibil pe HUDOC"
                print("    → PDF not available")

            time.sleep(REQUEST_DELAY)

        records.append(record)

    html = build_html(records, report_date)

    REPORTS_DIR.mkdir(exist_ok=True)
    out = REPORTS_DIR / f"analiza_cedo_{report_date}.html"
    out.write_text(html, encoding="utf-8")
    print(f"Analysis saved to {out}")


if __name__ == "__main__":
    main()
