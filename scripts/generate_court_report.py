"""
Generează un raport HTML cu analiza PDF-urilor hotărârilor penale
care conțin cuvinte cheie despre confiscare, sechestru și bunuri.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def generate(analyses: list[dict], target_date: date | None = None) -> Path:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")
    date_ro  = _date_ro(target_date)
    out_path = REPORTS_DIR / f"raport_instante_{date_str}.html"

    total        = len(analyses)
    cu_pdf       = sum(1 for a in analyses if a["pdf_disponibil"])
    cu_text      = sum(1 for a in analyses if a["text_extras"])
    cu_confiscare = sum(1 for a in analyses if a["sectiuni_confiscare"])
    cu_bunuri    = sum(1 for a in analyses if a["sectiuni_bunuri"])

    cards_html = "\n".join(_build_card(a, i + 1) for i, a in enumerate(analyses))

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Raport Hotărâri Penale — {date_ro}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f4f6f9; color: #222; }}
  .header {{ background: linear-gradient(135deg, #1a3a5c, #2e6da4); color: #fff; padding: 28px 32px; }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; }}
  .header p  {{ font-size: 0.9rem; opacity: .8; margin-top: 4px; }}
  .stats {{ display: flex; gap: 16px; flex-wrap: wrap; padding: 20px 32px; background: #fff; border-bottom: 1px solid #e0e0e0; }}
  .stat {{ background: #f0f4fa; border-radius: 8px; padding: 12px 20px; text-align: center; min-width: 110px; }}
  .stat .num {{ font-size: 1.8rem; font-weight: 700; color: #1a3a5c; }}
  .stat .lbl {{ font-size: 0.75rem; color: #666; margin-top: 2px; }}
  .container {{ max-width: 1100px; margin: 24px auto; padding: 0 16px; }}
  .card {{ background: #fff; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-bottom: 20px; overflow: hidden; }}
  .card-header {{ background: #1a3a5c; color: #fff; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center; }}
  .card-header .idx {{ font-size: 0.8rem; opacity: .7; }}
  .card-header .name {{ font-weight: 600; font-size: 1rem; }}
  .card-body {{ padding: 16px 20px; }}
  .meta {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; margin-bottom: 14px; }}
  .meta-item {{ background: #f8f9fb; border-radius: 6px; padding: 8px 12px; }}
  .meta-item .key {{ font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: .5px; }}
  .meta-item .val {{ font-size: 0.9rem; font-weight: 600; margin-top: 2px; }}
  .section-title {{ font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: #2e6da4; margin: 14px 0 6px; border-bottom: 2px solid #e8f0fb; padding-bottom: 4px; }}
  .excerpt {{ background: #fffbf0; border-left: 3px solid #f0a500; border-radius: 0 6px 6px 0; padding: 10px 14px; margin-bottom: 8px; font-size: 0.88rem; line-height: 1.6; }}
  .excerpt-confiscare {{ border-color: #d9534f; background: #fff5f5; }}
  .excerpt-decizie {{ border-color: #5cb85c; background: #f5fff5; }}
  .tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }}
  .tag {{ background: #e8f0fb; color: #1a3a5c; border-radius: 20px; padding: 3px 10px; font-size: 0.75rem; font-weight: 600; }}
  .tag-warn {{ background: #fff3cd; color: #856404; }}
  .pdf-link {{ display: inline-block; background: #2e6da4; color: #fff; border-radius: 6px; padding: 6px 14px; font-size: 0.82rem; text-decoration: none; margin-top: 10px; }}
  .pdf-link:hover {{ background: #1a3a5c; }}
  .no-text {{ background: #f8f9fb; border: 1px dashed #ccc; border-radius: 6px; padding: 12px; color: #888; font-size: 0.85rem; text-align: center; }}
  .empty-state {{ text-align: center; padding: 60px; color: #888; }}
  details summary {{ cursor: pointer; padding: 6px 0; font-size: 0.82rem; color: #2e6da4; user-select: none; }}
  details[open] summary {{ margin-bottom: 8px; }}
</style>
</head>
<body>

<div class="header">
  <h1>⚖️ Raport Hotărâri Penale — Confiscare &amp; Sechestru</h1>
  <p>📅 {date_ro} &nbsp;|&nbsp; Analiză automată PDF hotărâri judecătorești</p>
</div>

<div class="stats">
  <div class="stat"><div class="num">{total}</div><div class="lbl">Dosare analizate</div></div>
  <div class="stat"><div class="num">{cu_pdf}</div><div class="lbl">Cu PDF disponibil</div></div>
  <div class="stat"><div class="num">{cu_text}</div><div class="lbl">Text extras</div></div>
  <div class="stat"><div class="num">{cu_confiscare}</div><div class="lbl">Mențiuni confiscare</div></div>
  <div class="stat"><div class="num">{cu_bunuri}</div><div class="lbl">Mențiuni bunuri</div></div>
</div>

<div class="container">
{"".join([cards_html]) if analyses else '<div class="empty-state"><p>Nu au fost găsite dosare care să corespundă cuvintelor cheie pentru această dată.</p></div>'}
</div>

</body>
</html>"""

    out_path.write_text(html, encoding="utf-8")
    return out_path


def _build_card(a: dict, idx: int) -> str:
    d = a["dosar"]
    name     = _esc(d.get("denumirea_dosarului") or "—")
    nr       = _esc(d.get("numarul_dosarului") or "—")
    instanta = _esc(d.get("instanta_judecatoreasca") or "—")
    judecator = _esc(d.get("judecator") or "—")
    tematica = _esc(d.get("tematica_dosarului") or "—")
    d_pron   = _esc(d.get("data_pronuntarii") or "—")
    d_pub    = _esc(d.get("data_publicarii") or "—")

    # Tags pentru keywords găsite
    tags_html = ""
    if a["keywords_gasite"]:
        tags = "".join(f'<span class="tag">{_esc(k)}</span>' for k in a["keywords_gasite"][:8])
        tags_html = f'<div class="section-title">Cuvinte cheie identificate</div><div class="tags">{tags}</div>'
    elif a["eroare"]:
        tags_html = f'<div class="tags"><span class="tag tag-warn">⚠ {_esc(a["eroare"])}</span></div>'

    # Secțiuni confiscare
    conf_html = ""
    if a["sectiuni_confiscare"]:
        items = "".join(
            f'<div class="excerpt excerpt-confiscare">{_esc(s)}</div>'
            for s in a["sectiuni_confiscare"]
        )
        conf_html = f'''
        <details open>
          <summary>🔴 Confiscare / Sechestru ({len(a["sectiuni_confiscare"])} secțiuni)</summary>
          {items}
        </details>'''

    # Secțiuni bunuri
    bunuri_html = ""
    if a["sectiuni_bunuri"]:
        items = "".join(
            f'<div class="excerpt">{_esc(s)}</div>'
            for s in a["sectiuni_bunuri"]
        )
        bunuri_html = f'''
        <details>
          <summary>🏠 Bunuri menționate ({len(a["sectiuni_bunuri"])} secțiuni)</summary>
          {items}
        </details>'''

    # Secțiuni decizie
    decizie_html = ""
    if a["sectiuni_decizie"]:
        items = "".join(
            f'<div class="excerpt excerpt-decizie">{_esc(s)}</div>'
            for s in a["sectiuni_decizie"]
        )
        decizie_html = f'''
        <details>
          <summary>✅ Dispozitiv / Decizie ({len(a["sectiuni_decizie"])} secțiuni)</summary>
          {items}
        </details>'''

    # Fallback dacă nu s-a extras text
    content_html = conf_html + bunuri_html + decizie_html
    if not content_html and a["pdf_disponibil"]:
        msg = a["eroare"] or "Nicio secțiune relevantă identificată în text"
        content_html = f'<div class="no-text">{_esc(msg)}</div>'

    # Link PDF
    pdf_link = ""
    if a["pdf_url"]:
        pdf_link = f'<a class="pdf-link" href="{a["pdf_url"]}" target="_blank">📄 Deschide PDF</a>'

    pagini = f' &nbsp;|&nbsp; {a["pagini"]} pag.' if a["pagini"] else ""

    return f'''
<div class="card">
  <div class="card-header">
    <span class="name">{idx}. {name}</span>
    <span class="idx">Nr. {nr}</span>
  </div>
  <div class="card-body">
    <div class="meta">
      <div class="meta-item"><div class="key">Instanța</div><div class="val">{instanta}</div></div>
      <div class="meta-item"><div class="key">Judecător</div><div class="val">{judecator}</div></div>
      <div class="meta-item"><div class="key">Tematică</div><div class="val">{tematica}</div></div>
      <div class="meta-item"><div class="key">Data pronunțării</div><div class="val">{d_pron}</div></div>
      <div class="meta-item"><div class="key">Data publicării</div><div class="val">{d_pub}</div></div>
    </div>
    {tags_html}
    {content_html}
    {pdf_link}
    <div style="font-size:0.75rem;color:#aaa;margin-top:8px;">PDF{pagini}</div>
  </div>
</div>'''


_MONTHS_RO = [
    "", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]

def _date_ro(d: date) -> str:
    return f"{d.day} {_MONTHS_RO[d.month]} {d.year}"

def _esc(t: str) -> str:
    return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
