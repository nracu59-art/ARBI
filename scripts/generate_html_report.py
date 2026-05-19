"""
ECHR HTML Report Generator
Reads the latest results JSON and generates a self-contained HTML report in reports/.
"""

import json
import os
from datetime import datetime, timezone

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")
REPORTS_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

IMPORTANCE_LABELS = {"1": "Mare", "2": "Medie", "3": "Redusă", "4": "Necomunicată"}
IMPORTANCE_COLORS = {"1": "#c0392b", "2": "#e67e22", "3": "#27ae60", "4": "#7f8c8d"}

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raport CEDO Confiscare – {date_ro}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #2c3e50; }}
  .header {{ background: #1a3a5c; color: #fff; padding: 28px 40px; }}
  .header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: 0.5px; }}
  .header .subtitle {{ margin-top: 6px; font-size: 0.9rem; opacity: 0.85; }}
  .stats {{ background: #2c5282; color: #fff; padding: 16px 40px;
            display: flex; gap: 40px; flex-wrap: wrap; }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat .val {{ font-size: 1.8rem; font-weight: 700; }}
  .stat .lbl {{ font-size: 0.75rem; opacity: 0.8; text-transform: uppercase; letter-spacing: 0.8px; }}
  .container {{ max-width: 1000px; margin: 30px auto; padding: 0 20px 40px; }}
  .section-title {{ font-size: 1rem; font-weight: 700; color: #1a3a5c;
                    text-transform: uppercase; letter-spacing: 1px;
                    margin: 28px 0 14px; border-bottom: 2px solid #1a3a5c;
                    padding-bottom: 6px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
           padding: 20px 24px; margin-bottom: 16px; border-left: 5px solid #1a3a5c; }}
  .card-title {{ font-size: 1rem; font-weight: 700; color: #1a3a5c; margin-bottom: 10px; }}
  .card-title a {{ color: inherit; text-decoration: none; }}
  .card-title a:hover {{ text-decoration: underline; }}
  .badge {{ display: inline-block; font-size: 0.7rem; font-weight: 700;
            padding: 2px 8px; border-radius: 12px; color: #fff;
            margin-right: 6px; vertical-align: middle; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;
           font-size: 0.82rem; color: #555; }}
  .meta span {{ display: flex; align-items: center; gap: 4px; }}
  .field {{ margin-top: 8px; font-size: 0.84rem; }}
  .field strong {{ color: #1a3a5c; }}
  .link-btn {{ display: inline-block; margin-top: 12px; padding: 6px 16px;
               background: #1a3a5c; color: #fff; border-radius: 5px;
               font-size: 0.8rem; text-decoration: none; font-weight: 600; }}
  .link-btn:hover {{ background: #2c5282; }}
  .empty-box {{ background: #fff; border-radius: 8px; padding: 30px 24px;
                text-align: center; color: #7f8c8d; font-size: 0.95rem;
                box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .footer {{ text-align: center; font-size: 0.75rem; color: #999;
             margin-top: 40px; padding-bottom: 20px; }}
  @media (max-width: 600px) {{
    .header, .stats {{ padding: 20px; }}
    .stats {{ gap: 24px; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>⚖️ Raport CEDO – Hotărâri Confiscare</h1>
  <div class="subtitle">Sursa: hudoc.echr.coe.int &nbsp;|&nbsp; Generat la: {generated_at} UTC</div>
</div>
<div class="stats">
  <div class="stat"><span class="val">{total}</span><span class="lbl">Hotărâri găsite</span></div>
  <div class="stat"><span class="val">{lookback}</span><span class="lbl">Zile analizate</span></div>
  <div class="stat"><span class="val">{checked_at}</span><span class="lbl">Data verificare</span></div>
</div>
<div class="container">
{body}
</div>
<div class="footer">
  Raport generat automat · CEDO Monitor · Sursa oficială:
  <a href="https://hudoc.echr.coe.int" target="_blank">hudoc.echr.coe.int</a>
</div>
</body>
</html>
"""


def format_date_ro(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return date_str or "–"


def importance_badge(imp: str) -> str:
    label = IMPORTANCE_LABELS.get(str(imp), "")
    color = IMPORTANCE_COLORS.get(str(imp), "#7f8c8d")
    if not label:
        return ""
    return f'<span class="badge" style="background:{color}">Importanță {label}</span>'


def render_judgment_card(j: dict, index: int) -> str:
    docname = j.get("docname") or "Hotărâre CEDO"
    url = j.get("url", "")
    title_html = (
        f'<a href="{url}" target="_blank">{docname}</a>' if url else docname
    )

    imp_badge = importance_badge(j.get("importance", ""))
    respondent = j.get("respondent") or "–"
    doc_date = format_date_ro(j.get("docdate", ""))

    fields = []
    if j.get("applicability"):
        fields.append(
            f'<div class="field"><strong>Articole:</strong> {j["applicability"][:200]}</div>'
        )
    if j.get("conclusion"):
        fields.append(
            f'<div class="field"><strong>Concluzie:</strong> {j["conclusion"][:500]}</div>'
        )
    if j.get("violation"):
        fields.append(
            f'<div class="field"><strong>Violări:</strong> {j["violation"][:200]}</div>'
        )
    if j.get("nonviolation"):
        fields.append(
            f'<div class="field"><strong>Neviolări:</strong> {j["nonviolation"][:200]}</div>'
        )

    link_btn = (
        f'<a class="link-btn" href="{url}" target="_blank">Accesează hotărârea →</a>'
        if url else ""
    )

    return f"""
  <div class="card">
    <div class="card-title">{index}. {title_html} {imp_badge}</div>
    <div class="meta">
      <span>📅 {doc_date}</span>
      <span>🏳️ {respondent}</span>
    </div>
    {''.join(fields)}
    {link_btn}
  </div>"""


def build_body(data: dict) -> str:
    judgments = data.get("judgments", [])
    if not judgments:
        return (
            '<div class="section-title">Rezultate</div>'
            '<div class="empty-box">'
            '❌ Nu au fost găsite hotărâri despre confiscare în perioada analizată.<br>'
            '<small style="margin-top:8px;display:block">CEDO publică hotărâri în principal marțea și joia.</small>'
            '</div>'
        )

    by_date: dict[str, list] = {}
    for j in judgments:
        key = j.get("docdate") or "necunoscut"
        by_date.setdefault(key, []).append(j)

    sections = []
    global_idx = 1
    for date_key in sorted(by_date.keys(), reverse=True):
        date_label = format_date_ro(date_key)
        count = len(by_date[date_key])
        sections.append(
            f'<div class="section-title">📅 {date_label} &nbsp;({count} hotărâre{"i" if count != 1 else ""})</div>'
        )
        for j in by_date[date_key]:
            sections.append(render_judgment_card(j, global_idx))
            global_idx += 1

    return "\n".join(sections)


def find_latest_results() -> str | None:
    if not os.path.isdir(RESULTS_DIR):
        return None
    files = sorted(
        f for f in os.listdir(RESULTS_DIR)
        if f.startswith("echr_") and f.endswith(".json")
    )
    return os.path.join(RESULTS_DIR, files[-1]) if files else None


def main() -> None:
    latest = find_latest_results()
    if not latest:
        print("ERROR: No result JSON found in results/. Run echr_checker.py first.")
        raise SystemExit(1)

    with open(latest, encoding="utf-8") as f:
        data = json.load(f)

    now_utc = datetime.now(timezone.utc)
    date_ro = format_date_ro(data.get("date", now_utc.strftime("%Y-%m-%d")))
    checked_at_raw = data.get("checked_at", "")
    checked_at_display = format_date_ro(checked_at_raw[:10]) if checked_at_raw else date_ro
    generated_at = now_utc.strftime("%Y-%m-%d %H:%M")

    body = build_body(data)
    html = HTML_TEMPLATE.format(
        date_ro=date_ro,
        generated_at=generated_at,
        total=data.get("total_filtered", len(data.get("judgments", []))),
        lookback=data.get("lookback_days", 7),
        checked_at=checked_at_display,
        body=body,
    )

    os.makedirs(REPORTS_DIR, exist_ok=True)
    report_date = data.get("date", now_utc.strftime("%Y-%m-%d"))
    output_path = os.path.join(REPORTS_DIR, f"raport_cedo_{report_date}.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML report saved to {output_path}")


if __name__ == "__main__":
    main()
