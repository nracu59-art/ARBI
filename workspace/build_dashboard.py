"""
Generează un dashboard HTML unificat care agregă:
  - Dosare active și sarcini urgente (cases.json)
  - Ultimele decizii CEDO (results/echr_*.json)
  - Sumar hotărâri penale zilnice (din rapoartele existente)

Output: dashboard/index.html
"""

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results"
REPORTS_DIR = BASE_DIR / "reports"
DASHBOARD_DIR = BASE_DIR / "dashboard"
CASES_JSON = Path(__file__).parent / "cases.json"


# ─────────────────────────────────────────────────────────────────────────────
# Citire date
# ─────────────────────────────────────────────────────────────────────────────

def load_cases() -> dict:
    if not CASES_JSON.exists():
        return {"dosare": [], "sarcini": []}
    with open(CASES_JSON, encoding="utf-8") as f:
        return json.load(f)


def load_latest_echr() -> dict | None:
    if not RESULTS_DIR.exists():
        return None
    files = sorted(
        f for f in RESULTS_DIR.iterdir()
        if f.name.startswith("echr_") and f.name.endswith(".json")
    )
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        return json.load(f)


def load_echr_week() -> list[dict]:
    if not RESULTS_DIR.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).date()
    results = []
    for f in sorted(RESULTS_DIR.iterdir()):
        if not (f.name.startswith("echr_") and f.name.endswith(".json")):
            continue
        date_str = f.name.replace("echr_", "").replace(".json", "")
        try:
            if date.fromisoformat(date_str) >= cutoff:
                with open(f, encoding="utf-8") as fp:
                    results.append(json.load(fp))
        except ValueError:
            continue
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Helpers HTML
# ─────────────────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def fmt_date(d: str) -> str:
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return d or "—"


def stadiu_badge(stadiu: str) -> str:
    colors = {
        "activ": ("#27ae60", "#e8f8f0"),
        "executare": ("#2980b9", "#eaf4fb"),
        "contestat": ("#e74c3c", "#fdf0ef"),
        "suspendat": ("#f39c12", "#fef9e7"),
        "inchis": ("#7f8c8d", "#f2f3f4"),
    }
    bg, text_bg = colors.get(stadiu, ("#7f8c8d", "#f2f3f4"))
    return (
        f'<span style="background:{bg};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.5px">{esc(stadiu.upper())}</span>'
    )


def prio_badge(prio: str) -> str:
    colors = {"inalta": "#e74c3c", "medie": "#f39c12", "scazuta": "#27ae60"}
    color = colors.get(prio, "#7f8c8d")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:0.7rem;font-weight:700">{esc(prio.upper())}</span>'
    )


def importance_badge(imp: str) -> str:
    labels = {"1": "Importanță Mare", "2": "Importanță Medie",
               "3": "Importanță Redusă", "4": "Necomunicată"}
    colors = {"1": "#c0392b", "2": "#e67e22", "3": "#27ae60", "4": "#7f8c8d"}
    label = labels.get(str(imp), "")
    color = colors.get(str(imp), "#7f8c8d")
    if not label:
        return ""
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:0.7rem;font-weight:600">{label}</span>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Secțiuni HTML
# ─────────────────────────────────────────────────────────────────────────────

def render_kpi_bar(cases_data: dict, echr_latest: dict | None, echr_week: list[dict]) -> str:
    dosare_active = sum(1 for d in cases_data.get("dosare", []) if d.get("stadiu") == "activ")
    sarcini_urgente = sum(
        1 for t in cases_data.get("sarcini", [])
        if t.get("status") == "deschis" and t.get("prioritate") == "inalta"
    )
    valoare_totala = sum(
        d.get("valoare_ron", 0) or 0
        for d in cases_data.get("dosare", [])
        if d.get("stadiu") in ("activ", "executare")
    )
    echr_total = sum(d.get("total_filtered", 0) for d in echr_week)
    echr_label = echr_latest.get("checked_at", "")[:10] if echr_latest else "—"

    return f"""
<div class="kpi-bar">
  <div class="kpi">
    <div class="kpi-val">{dosare_active}</div>
    <div class="kpi-lbl">Dosare Active</div>
  </div>
  <div class="kpi">
    <div class="kpi-val" style="color:#e74c3c">{sarcini_urgente}</div>
    <div class="kpi-lbl">Sarcini Urgente</div>
  </div>
  <div class="kpi">
    <div class="kpi-val">{valoare_totala:,.0f}</div>
    <div class="kpi-lbl">Valoare Activă (RON)</div>
  </div>
  <div class="kpi">
    <div class="kpi-val">{echr_total}</div>
    <div class="kpi-lbl">Decizii CEDO (7 zile)</div>
  </div>
  <div class="kpi">
    <div class="kpi-val kpi-date">{fmt_date(echr_label)}</div>
    <div class="kpi-lbl">Ultima verificare CEDO</div>
  </div>
</div>"""


def render_active_cases(cases_data: dict) -> str:
    dosare = [d for d in cases_data.get("dosare", []) if d.get("stadiu") != "inchis"]
    dosare = sorted(dosare, key=lambda x: (
        {"activ": 0, "executare": 1, "contestat": 2, "suspendat": 3}.get(x.get("stadiu", ""), 9),
        x.get("termen_urm", "9999"),
    ))

    if not dosare:
        return """
<div class="section">
  <div class="section-title">📁 Dosare Active</div>
  <div class="empty-card">Nu există dosare active înregistrate.</div>
</div>"""

    today = date.today().isoformat()
    rows = []
    for d in dosare:
        termen = d.get("termen_urm", "")
        termen_html = ""
        if termen:
            overdue = termen < today
            color = "#e74c3c" if overdue else "#2980b9"
            icon = "‼️" if overdue else "⏰"
            termen_html = f'<span style="color:{color};font-weight:600">{icon} {fmt_date(termen)}</span>'

        val = f"{d.get('valoare_ron', 0):,.0f} RON" if d.get("valoare_ron") else "—"
        instanta = f'<div class="case-meta">🏛 {esc(d["instanta"])}</div>' if d.get("instanta") else ""
        judecator = f'<span> · Judecător: {esc(d["judecator"])}</span>' if d.get("judecator") else ""
        note = f'<div class="case-note">📝 {esc(d["note"])}</div>' if d.get("note") else ""

        rows.append(f"""
  <div class="case-card">
    <div class="case-header">
      <div>
        <span class="case-id">{esc(d['id'])}</span>
        <span class="case-title">{esc(d['titlu'])}</span>
        {stadiu_badge(d.get('stadiu', ''))}
      </div>
      <div class="case-value">{val}</div>
    </div>
    <div class="case-meta">
      📂 Nr: <strong>{esc(d.get('nr_dosar','—'))}</strong>
      &nbsp;·&nbsp; Tip: {esc(d.get('tip','—').replace('_',' '))}
      {judecator}
    </div>
    {instanta}
    {note}
    {f'<div class="case-meta">Termen următor: {termen_html}</div>' if termen_html else ''}
  </div>""")

    return f"""
<div class="section">
  <div class="section-title">📁 Dosare Active <span class="section-count">({len(dosare)})</span></div>
  {''.join(rows)}
</div>"""


def render_tasks(cases_data: dict) -> str:
    sarcini = [t for t in cases_data.get("sarcini", []) if t.get("status") == "deschis"]
    today = date.today().isoformat()

    def sort_key(t):
        p = {"inalta": 0, "medie": 1, "scazuta": 2}.get(t.get("prioritate", ""), 9)
        overdue = -1 if t.get("termen", "9999") < today else 1
        return (overdue, p, t.get("termen", "9999"))

    sarcini = sorted(sarcini, key=sort_key)

    if not sarcini:
        return """
<div class="section">
  <div class="section-title">✅ Sarcini</div>
  <div class="empty-card">Nu există sarcini deschise.</div>
</div>"""

    rows = []
    for t in sarcini:
        termen = t.get("termen", "")
        overdue = termen and termen < today
        termen_html = ""
        if termen:
            color = "#e74c3c" if overdue else "#555"
            termen_html = f'<span style="color:{color}">⏰ {fmt_date(termen)}</span>'
            if overdue:
                termen_html += ' <span style="color:#e74c3c;font-weight:700">DEPĂȘIT</span>'

        dosar_str = f'<span class="task-dosar">[{esc(t["dosar_id"])}]</span>' if t.get("dosar_id") else ""
        resp = f'<span>👤 {esc(t["responsabil"])}</span>' if t.get("responsabil") else ""

        border_color = {"inalta": "#e74c3c", "medie": "#f39c12", "scazuta": "#27ae60"}.get(
            t.get("prioritate", ""), "#ddd"
        )
        rows.append(f"""
  <div class="task-card" style="border-left-color:{border_color}">
    <div class="task-header">
      <div>
        <span class="task-id">{esc(t['id'])}</span>
        {dosar_str}
        {prio_badge(t.get('prioritate', ''))}
      </div>
      {termen_html}
    </div>
    <div class="task-desc">{esc(t['descriere'])}</div>
    {f'<div class="task-meta">{resp}</div>' if resp else ''}
  </div>""")

    return f"""
<div class="section">
  <div class="section-title">✅ Sarcini <span class="section-count">({len(sarcini)} deschise)</span></div>
  {''.join(rows)}
</div>"""


def render_echr_section(echr_latest: dict | None) -> str:
    if not echr_latest:
        return """
<div class="section">
  <div class="section-title">⚖️ Decizii CEDO — Confiscare</div>
  <div class="empty-card">Nu au fost găsite date CEDO. Rulați scripts/echr_checker.py</div>
</div>"""

    judgments = echr_latest.get("judgments", [])
    checked = fmt_date(echr_latest.get("date", ""))
    lookback = echr_latest.get("lookback_days", 7)

    if not judgments:
        return f"""
<div class="section">
  <div class="section-title">⚖️ Decizii CEDO — Confiscare</div>
  <div class="empty-card">
    Nu au fost găsite hotărâri CEDO în ultimele {lookback} zile (verificat {checked}).
    <br><small>CEDO publică hotărâri în principal marțea și joia.</small>
  </div>
</div>"""

    imp_labels = {"1": "Mare", "2": "Medie", "3": "Redusă", "4": "Necomunicată"}
    imp_colors = {"1": "#c0392b", "2": "#e67e22", "3": "#27ae60", "4": "#7f8c8d"}

    rows = []
    for i, j in enumerate(judgments[:15], 1):
        docname = esc(j.get("docname") or "Hotărâre CEDO")
        url = j.get("url", "")
        title_html = f'<a href="{url}" target="_blank">{docname}</a>' if url else docname
        imp = str(j.get("importance", ""))
        imp_badge = ""
        if imp in imp_labels:
            imp_badge = (
                f'<span style="background:{imp_colors[imp]};color:#fff;'
                f'padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:600">'
                f'{imp_labels[imp]}</span>'
            )
        respondent = esc(j.get("respondent") or "—")
        doc_date = fmt_date(j.get("docdate", ""))
        conclusion = esc((j.get("conclusion") or "")[:250])

        rows.append(f"""
  <div class="echr-card">
    <div class="echr-title">{i}. {title_html} &nbsp;{imp_badge}</div>
    <div class="echr-meta">📅 {doc_date} &nbsp;·&nbsp; 🏳️ {respondent}</div>
    {f'<div class="echr-conclusion">{conclusion}</div>' if conclusion else ''}
    {f'<a class="echr-link" href="{url}" target="_blank">Accesează hotărârea →</a>' if url else ''}
  </div>""")

    more = f'<div class="empty-card" style="text-align:center">... și {len(judgments)-15} hotărâri suplimentare</div>' if len(judgments) > 15 else ""

    return f"""
<div class="section">
  <div class="section-title">
    ⚖️ Decizii CEDO — Confiscare
    <span class="section-count">({len(judgments)} în ultimele {lookback} zile · verificat {checked})</span>
  </div>
  {''.join(rows)}
  {more}
</div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Template principal
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ARBI Dashboard — {today}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #eef1f5; color: #2c3e50; }}

/* Header */
.header {{ background: linear-gradient(135deg, #1a2a4a 0%, #1a3a5c 100%);
           color: #fff; padding: 24px 40px; display: flex;
           align-items: center; justify-content: space-between; }}
.header-title {{ font-size: 1.4rem; font-weight: 700; letter-spacing: 0.5px; }}
.header-sub {{ font-size: 0.82rem; opacity: 0.75; margin-top: 4px; }}
.header-date {{ font-size: 0.85rem; opacity: 0.8; text-align: right; }}

/* KPI bar */
.kpi-bar {{ background: #1e3a5c; color: #fff;
            display: flex; gap: 0; border-bottom: 3px solid #e8b800; }}
.kpi {{ flex: 1; padding: 18px 24px; border-right: 1px solid rgba(255,255,255,0.1); }}
.kpi:last-child {{ border-right: none; }}
.kpi-val {{ font-size: 1.9rem; font-weight: 700; }}
.kpi-date {{ font-size: 1.1rem; }}
.kpi-lbl {{ font-size: 0.7rem; opacity: 0.75; text-transform: uppercase;
            letter-spacing: 0.8px; margin-top: 2px; }}

/* Layout */
.container {{ max-width: 1200px; margin: 28px auto; padding: 0 20px 50px;
              display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
.full-width {{ grid-column: 1 / -1; }}

/* Section */
.section {{ background: #fff; border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,.07); overflow: hidden; }}
.section-title {{ background: #1a3a5c; color: #fff; padding: 12px 20px;
                  font-size: 0.88rem; font-weight: 700;
                  text-transform: uppercase; letter-spacing: 0.8px; }}
.section-count {{ font-weight: 400; opacity: 0.75; }}
.empty-card {{ padding: 24px 20px; color: #7f8c8d;
               font-size: 0.88rem; text-align: center; }}

/* Case cards */
.case-card {{ padding: 16px 20px; border-bottom: 1px solid #f0f2f5; }}
.case-card:last-child {{ border-bottom: none; }}
.case-header {{ display: flex; justify-content: space-between;
                align-items: flex-start; margin-bottom: 8px; gap: 12px; }}
.case-id {{ font-size: 0.7rem; font-weight: 700; color: #95a5a6;
            background: #f0f2f5; padding: 2px 7px; border-radius: 8px;
            margin-right: 6px; }}
.case-title {{ font-size: 0.95rem; font-weight: 700; color: #1a3a5c;
               margin-right: 8px; }}
.case-value {{ font-size: 0.88rem; font-weight: 700; color: #27ae60;
               white-space: nowrap; }}
.case-meta {{ font-size: 0.8rem; color: #666; margin-top: 4px; }}
.case-note {{ font-size: 0.78rem; color: #7f8c8d; margin-top: 4px;
              font-style: italic; }}

/* Task cards */
.task-card {{ padding: 14px 20px; border-bottom: 1px solid #f0f2f5;
              border-left: 4px solid #ddd; }}
.task-card:last-child {{ border-bottom: none; }}
.task-header {{ display: flex; justify-content: space-between;
                align-items: center; margin-bottom: 6px; gap: 10px;
                font-size: 0.8rem; color: #666; }}
.task-id {{ font-size: 0.7rem; font-weight: 700; color: #95a5a6;
            background: #f0f2f5; padding: 2px 7px; border-radius: 8px;
            margin-right: 4px; }}
.task-dosar {{ font-size: 0.75rem; font-weight: 700; color: #2980b9;
               margin-right: 4px; }}
.task-desc {{ font-size: 0.88rem; font-weight: 600; color: #2c3e50; }}
.task-meta {{ font-size: 0.78rem; color: #7f8c8d; margin-top: 4px; }}

/* ECHR cards */
.echr-card {{ padding: 16px 20px; border-bottom: 1px solid #f0f2f5; }}
.echr-card:last-child {{ border-bottom: none; }}
.echr-title {{ font-size: 0.9rem; font-weight: 700; color: #1a3a5c;
               margin-bottom: 6px; }}
.echr-title a {{ color: inherit; text-decoration: none; }}
.echr-title a:hover {{ text-decoration: underline; }}
.echr-meta {{ font-size: 0.78rem; color: #7f8c8d; margin-bottom: 6px; }}
.echr-conclusion {{ font-size: 0.8rem; color: #555;
                    background: #f8f9fa; border-radius: 6px;
                    padding: 8px 12px; margin: 6px 0; }}
.echr-link {{ display: inline-block; margin-top: 8px; font-size: 0.78rem;
              color: #1a3a5c; font-weight: 600; text-decoration: none; }}
.echr-link:hover {{ text-decoration: underline; }}

/* Footer */
.footer {{ text-align: center; font-size: 0.73rem; color: #999;
           padding: 20px; }}

@media (max-width: 768px) {{
  .container {{ grid-template-columns: 1fr; }}
  .full-width {{ grid-column: 1; }}
  .kpi-bar {{ flex-wrap: wrap; }}
  .kpi {{ flex: 1 1 45%; }}
  .header {{ flex-direction: column; gap: 8px; }}
}}
</style>
</head>
<body>

<div class="header">
  <div>
    <div class="header-title">⚖️ ARBI — Dashboard Operațional</div>
    <div class="header-sub">Agenția de Recuperare a Bunurilor Infracționale</div>
  </div>
  <div class="header-date">
    Generat: {generated_at}<br>
    <small style="opacity:0.6">Actualizat automat zilnic la 09:00 EEST</small>
  </div>
</div>

{kpi_bar}

<div class="container">

  <div class="full-width">
    {echr_section}
  </div>

  <div>
    {cases_section}
  </div>

  <div>
    {tasks_section}
  </div>

</div>

<div class="footer">
  ARBI Dashboard · Generat automat · {generated_at} UTC
</div>

</body>
</html>
"""


def build() -> None:
    DASHBOARD_DIR.mkdir(exist_ok=True)

    cases_data = load_cases()
    echr_latest = load_latest_echr()
    echr_week = load_echr_week()

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%d.%m.%Y")
    generated_at = now_utc.strftime("%Y-%m-%d %H:%M")

    html = HTML_TEMPLATE.format(
        today=today_str,
        generated_at=generated_at,
        kpi_bar=render_kpi_bar(cases_data, echr_latest, echr_week),
        echr_section=render_echr_section(echr_latest),
        cases_section=render_active_cases(cases_data),
        tasks_section=render_tasks(cases_data),
    )

    output = DASHBOARD_DIR / "index.html"
    output.write_text(html, encoding="utf-8")
    print(f"✅ Dashboard generat: {output}")


if __name__ == "__main__":
    build()
