#!/usr/bin/env python3
"""
Generare raport HTML + trimitere Telegram pentru monitorizarea jurnalismului de investigație.
Citește cel mai recent JSON din results/journalism/ și produce raportul zilnic.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results" / "journalism"
REPORTS_DIR = BASE_DIR / "reports"

TELEGRAM_API = "https://api.telegram.org"
MAX_MSG_LEN = 4096
SEPARATOR = "━" * 22

PREVIEW_BASE = (
    "https://htmlpreview.github.io/?https://github.com/nracu59-art/ARBI/blob/main/reports"
)

# ─── HTML Template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Monitorizare Jurnalism Investigativ Moldova – {date_ro}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #2c3e50; }}
  .header {{ background: #1b4332; color: #fff; padding: 28px 40px; }}
  .header h1 {{ font-size: 1.6rem; font-weight: 700; letter-spacing: 0.5px; }}
  .header .subtitle {{ margin-top: 6px; font-size: 0.9rem; opacity: 0.85; }}
  .stats-bar {{ background: #2d6a4f; color: #fff; padding: 16px 40px;
                display: flex; gap: 36px; flex-wrap: wrap; }}
  .stat {{ display: flex; flex-direction: column; }}
  .stat .val {{ font-size: 1.8rem; font-weight: 700; }}
  .stat .lbl {{ font-size: 0.72rem; opacity: 0.82; text-transform: uppercase; letter-spacing: 0.8px; }}
  .cat-bar {{ background: #40916c; color: #fff; padding: 12px 40px;
              display: flex; gap: 16px; flex-wrap: wrap; align-items: center; }}
  .cat-chip {{ background: rgba(255,255,255,0.18); border-radius: 20px;
               padding: 4px 14px; font-size: 0.78rem; font-weight: 600;
               white-space: nowrap; }}
  .container {{ max-width: 1040px; margin: 30px auto; padding: 0 20px 40px; }}
  .section-title {{ font-size: 0.95rem; font-weight: 700; color: #1b4332;
                    text-transform: uppercase; letter-spacing: 1px;
                    margin: 28px 0 14px; border-bottom: 2px solid #1b4332;
                    padding-bottom: 6px; display: flex; align-items: center; gap: 8px; }}
  .card {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.08);
           padding: 18px 22px; margin-bottom: 14px; border-left: 5px solid #1b4332;
           transition: box-shadow .15s; }}
  .card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,.13); }}
  .card.investigativ {{ border-left-color: #d62828; }}
  .card-title {{ font-size: 1rem; font-weight: 700; color: #1b4332; margin-bottom: 8px; }}
  .card-title a {{ color: inherit; text-decoration: none; }}
  .card-title a:hover {{ text-decoration: underline; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;
           font-size: 0.8rem; color: #555; }}
  .badge {{ display: inline-block; font-size: 0.68rem; font-weight: 700;
            padding: 2px 8px; border-radius: 12px; color: #fff;
            margin-right: 4px; vertical-align: middle; }}
  .badge-inv {{ background: #d62828; }}
  .source-tag {{ background: #e8f4ec; color: #1b4332; border-radius: 4px;
                 padding: 1px 8px; font-size: 0.75rem; font-weight: 600; }}
  .summary {{ font-size: 0.85rem; color: #444; line-height: 1.55; margin-top: 6px; }}
  .cat-tags {{ margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }}
  .cat-tag {{ font-size: 0.72rem; padding: 2px 10px; border-radius: 10px;
              font-weight: 600; background: #e8f4ec; color: #1b4332; }}
  .link-btn {{ display: inline-block; margin-top: 10px; padding: 5px 14px;
               background: #1b4332; color: #fff; border-radius: 5px;
               font-size: 0.78rem; text-decoration: none; font-weight: 600; }}
  .link-btn:hover {{ background: #2d6a4f; }}
  .empty-box {{ background: #fff; border-radius: 8px; padding: 30px 24px;
                text-align: center; color: #7f8c8d; font-size: 0.95rem;
                box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
  .source-grid {{ display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 24px; }}
  .source-box {{ background: #fff; border-radius: 8px; padding: 12px 18px;
                 box-shadow: 0 2px 6px rgba(0,0,0,.07); min-width: 140px;
                 border-top: 3px solid #1b4332; }}
  .source-box .sname {{ font-size: 0.78rem; font-weight: 700; color: #1b4332; }}
  .source-box .scount {{ font-size: 1.4rem; font-weight: 700; color: #2d6a4f; margin-top: 2px; }}
  .footer {{ text-align: center; font-size: 0.75rem; color: #999;
             margin-top: 40px; padding-bottom: 20px; }}
  @media (max-width: 600px) {{
    .header, .stats-bar, .cat-bar {{ padding: 18px 16px; }}
    .stats-bar {{ gap: 20px; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>🔍 Monitorizare Jurnalism Investigativ – Moldova</h1>
  <div class="subtitle">
    Surse monitorizate: {sources_count} &nbsp;|&nbsp;
    Ultimele {lookback_hours} ore &nbsp;|&nbsp;
    Generat: {generated_at} UTC
  </div>
</div>
<div class="stats-bar">
  <div class="stat"><span class="val">{total}</span><span class="lbl">Articole noi</span></div>
  <div class="stat"><span class="val">{investigative}</span><span class="lbl">Investigative</span></div>
  <div class="stat"><span class="val">{sources_ok}</span><span class="lbl">Surse active</span></div>
  <div class="stat"><span class="val">{date_ro}</span><span class="lbl">Data raportului</span></div>
</div>
<div class="cat-bar">
  <span style="font-size:.8rem;opacity:.85;margin-right:4px">Categorii:</span>
  {cat_chips}
</div>
<div class="container">
{body}
</div>
<div class="footer">
  Raport generat automat zilnic &nbsp;·&nbsp; ARBI – Monitorizare Jurnalism Investigativ Moldova
</div>
</body>
</html>
"""


# ─── HTML Helpers ─────────────────────────────────────────────────────────────

def format_date_ro(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return dt.strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return date_str or "–"


def render_article_card(article: dict, categories_cfg: dict) -> str:
    title = article.get("title", "Articol")
    url = article.get("url", "")
    source = article.get("source", "")
    pub = format_date_ro(article.get("published_date", ""))
    summary = article.get("summary", "")
    cats = article.get("categories", [])
    inv_score = article.get("investigative_score", 0)

    title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
    inv_badge = '<span class="badge badge-inv">🔍 Investigativ</span>' if inv_score > 0 else ""
    card_cls = "card investigativ" if inv_score > 0 else "card"

    cat_tags = ""
    for cat_key in cats:
        cat_cfg = categories_cfg.get(cat_key, {})
        label = cat_cfg.get("label", cat_key)
        emoji = cat_cfg.get("emoji", "")
        cat_tags += f'<span class="cat-tag">{emoji} {label}</span>'

    link_btn = f'<a class="link-btn" href="{url}" target="_blank">Citește articolul →</a>' if url else ""

    return f"""
  <div class="{card_cls}">
    <div class="card-title">{title_html} {inv_badge}</div>
    <div class="meta">
      <span class="source-tag">📰 {source}</span>
      {"<span>📅 " + pub + "</span>" if pub else ""}
    </div>
    {"<div class='summary'>" + summary[:400] + ("…" if len(summary) > 400 else "") + "</div>" if summary else ""}
    {"<div class='cat-tags'>" + cat_tags + "</div>" if cat_tags else ""}
    {link_btn}
  </div>"""


def build_html_body(data: dict, categories_cfg: dict) -> str:
    articles = data.get("articles", [])
    stats = data.get("stats", {})

    if not articles:
        return (
            '<div class="empty-box">'
            '❌ Nu au fost găsite articole noi de investigație în perioada analizată.<br>'
            '<small style="margin-top:8px;display:block">Verificați din nou mâine.</small>'
            '</div>'
        )

    sections = []

    # Source summary grid
    by_source = stats.get("by_source", {})
    if by_source:
        boxes = "".join(
            f'<div class="source-box"><div class="sname">{v["name"]}</div>'
            f'<div class="scount">{v["count"]}</div></div>'
            for v in sorted(by_source.values(), key=lambda x: -x["count"])
        )
        sections.append(
            '<div class="section-title">📊 Articole pe surse</div>'
            f'<div class="source-grid">{boxes}</div>'
        )

    # Investigative articles first
    inv_articles = [a for a in articles if a.get("investigative_score", 0) > 0]
    if inv_articles:
        sections.append(
            f'<div class="section-title">🔍 Articole Investigative ({len(inv_articles)})</div>'
        )
        for art in inv_articles[:20]:
            sections.append(render_article_card(art, categories_cfg))

    # By category
    by_category = stats.get("by_category", {})
    for cat_key, cat_info in sorted(by_category.items(), key=lambda x: -x[1]["count"]):
        cat_articles = [a for a in articles if cat_key in a.get("categories", [])
                        and a.get("investigative_score", 0) == 0]
        if not cat_articles:
            continue
        cat_cfg = categories_cfg.get(cat_key, {})
        emoji = cat_cfg.get("emoji", "")
        label = cat_cfg.get("label", cat_key)
        count = len(cat_articles)
        sections.append(
            f'<div class="section-title">{emoji} {label} ({count})</div>'
        )
        for art in cat_articles[:10]:
            sections.append(render_article_card(art, categories_cfg))

    # Uncategorized
    other = [a for a in articles if not a.get("categories") and a.get("investigative_score", 0) == 0]
    if other:
        sections.append(f'<div class="section-title">📌 Alte articole ({len(other)})</div>')
        for art in other[:10]:
            sections.append(render_article_card(art, categories_cfg))

    return "\n".join(sections)


def generate_html(data: dict, cfg: dict) -> str:
    categories_cfg = cfg["categories"]
    stats = data.get("stats", {})
    now_utc = datetime.now(timezone.utc)
    date_ro = format_date_ro(data.get("date", ""))
    generated_at = now_utc.strftime("%Y-%m-%d %H:%M")

    by_category = stats.get("by_category", {})
    cat_chips = "".join(
        f'<span class="cat-chip">{v["emoji"]} {v["label"]} ({v["count"]})</span>'
        for v in sorted(by_category.values(), key=lambda x: -x["count"])
    )

    body = build_html_body(data, categories_cfg)

    return HTML_TEMPLATE.format(
        date_ro=date_ro,
        generated_at=generated_at,
        sources_count=data.get("sources_checked", 0),
        sources_ok=data.get("sources_ok", 0),
        lookback_hours=data.get("lookback_hours", 26),
        total=stats.get("total", 0),
        investigative=stats.get("investigative", 0),
        cat_chips=cat_chips or "–",
        body=body,
    )


# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, text: str) -> None:
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML",
              "disable_web_page_preview": True},
        timeout=30,
    )
    resp.raise_for_status()


def send_long_telegram(token: str, chat_id: str, text: str) -> None:
    if len(text) <= MAX_MSG_LEN:
        send_telegram(token, chat_id, text)
        return
    chunks = []
    while text:
        if len(text) <= MAX_MSG_LEN:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, MAX_MSG_LEN)
        if split_at == -1:
            split_at = MAX_MSG_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    for i, chunk in enumerate(chunks, 1):
        prefix = f"<b>[{i}/{len(chunks)}]</b>\n" if len(chunks) > 1 else ""
        send_telegram(token, chat_id, prefix + chunk)


def format_telegram_report(data: dict, cfg: dict) -> str:
    stats = data.get("stats", {})
    date_ro = format_date_ro(data.get("date", ""))
    total = stats.get("total", 0)
    investigative = stats.get("investigative", 0)
    sources_ok = data.get("sources_ok", 0)
    lookback = data.get("lookback_hours", 26)

    date_iso = data.get("date", "")
    report_url = f"{PREVIEW_BASE}/raport_jurnalism_{date_iso}.html"
    index_url = f"{PREVIEW_BASE}/index.html"

    lines = [
        f"🔍 <b>Jurnalism Investigativ Moldova – {date_ro}</b>",
        f"📊 Articole noi: <b>{total}</b> &nbsp;|&nbsp; Investigative: <b>{investigative}</b>",
        f"📡 Surse monitorizate: <b>{sources_ok}</b> &nbsp;|&nbsp; Ultimele <b>{lookback}h</b>",
        f'📄 <a href="{report_url}">Raport complet HTML</a>  📂 <a href="{index_url}">Toate rapoartele</a>',
        SEPARATOR,
    ]

    if total == 0:
        lines.append("❌ Nu au fost găsite articole noi în perioada monitorizată.")
        lines.append(SEPARATOR)
        lines.append("🔍 Surse: RISE Moldova, ZdG, Anticorupție.md și altele")
        return "\n".join(lines)

    # Category summary
    by_category = stats.get("by_category", {})
    if by_category:
        lines.append("")
        lines.append("<b>📋 Rezumat pe categorii:</b>")
        for cat_key, cat_info in sorted(by_category.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"  {cat_info['emoji']} {cat_info['label']}: <b>{cat_info['count']}</b>")

    # Source summary
    by_source = stats.get("by_source", {})
    if by_source:
        lines.append("")
        lines.append("<b>📰 Articole pe surse:</b>")
        for src_info in sorted(by_source.values(), key=lambda x: -x["count"]):
            lines.append(f"  • {src_info['name']}: <b>{src_info['count']}</b>")

    lines.append("")
    lines.append(SEPARATOR)

    # Top investigative articles
    articles = data.get("articles", [])
    inv_articles = [a for a in articles if a.get("investigative_score", 0) > 0][:5]
    if inv_articles:
        lines.append("")
        lines.append(f"<b>🔍 Top articole investigative ({len(inv_articles)}):</b>")
        for i, art in enumerate(inv_articles, 1):
            title = art.get("title", "")[:120]
            url = art.get("url", "")
            source = art.get("source", "")
            pub = format_date_ro(art.get("published_date", ""))
            cats_labels = [cfg["categories"].get(c, {}).get("label", c) for c in art.get("categories", [])[:2]]
            cats_str = " · ".join(cats_labels) if cats_labels else ""
            lines.append("")
            lines.append(f"<b>{i}.</b> <a href=\"{url}\">{title}</a>")
            lines.append(f"   📰 {source}{' · 📅 ' + pub if pub else ''}")
            if cats_str:
                lines.append(f"   🏷 {cats_str}")

    lines.append("")
    lines.append(SEPARATOR)
    lines.append("🔍 Surse: RISE Moldova, ZdG, Anticorupție.md și altele")

    return "\n".join(lines)


# ─── Index Update ─────────────────────────────────────────────────────────────

def update_index() -> None:
    base = "https://github.com/nracu59-art/ARBI/blob/main/reports"
    raw_base = "https://raw.githubusercontent.com/nracu59-art/ARBI/main/reports"
    preview = "https://htmlpreview.github.io/?"

    def get_reports(prefix: str) -> list[str]:
        return sorted(
            [f for f in os.listdir(REPORTS_DIR) if f.startswith(prefix) and f.endswith(".html")],
            reverse=True,
        )

    rapoarte_cedo = get_reports("raport_cedo_")
    analize_cedo = get_reports("analiza_cedo_")
    rapoarte_instante = get_reports("raport_instante_")
    rapoarte_jurnalism = get_reports("raport_jurnalism_")

    def make_row(fname: str, color: str = "#1a3a5c") -> str:
        date_str = re.sub(r"^[^_]+_[^_]+_", "", fname).replace(".html", "")
        try:
            date_ro = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            date_ro = date_str
        view_url = f"{preview}{base}/{fname}"
        dl_url = f"{raw_base}/{fname}"
        return (
            f'    <div class="row" style="border-left-color:{color}">\n'
            f'      <span class="date" style="color:{color}">{date_ro}</span>\n'
            f'      <div class="btns">\n'
            f'        <a class="btn btn-view" style="background:{color}" href="{view_url}" target="_blank">&#128065; Vizualizeaz&#259;</a>\n'
            f'        <a class="btn btn-dl" href="{dl_url}" download>&#8595; Descarc&#259;</a>\n'
            f'      </div>\n'
            f'    </div>'
        )

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    sections = []
    if rapoarte_jurnalism:
        rows = "\n".join(make_row(f, "#1b4332") for f in rapoarte_jurnalism)
        sections.append(f'  <div class="section">\n    <h2>🔍 Rapoarte Jurnalism Investigativ</h2>\n{rows}\n  </div>')
    if rapoarte_cedo:
        rows = "\n".join(make_row(f, "#1a3a5c") for f in rapoarte_cedo)
        sections.append(f'  <div class="section">\n    <h2>⚖️ Rapoarte CEDO – Hotărâri Confiscare</h2>\n{rows}\n  </div>')
    if analize_cedo:
        rows = "\n".join(make_row(f, "#c0392b") for f in analize_cedo)
        sections.append(f'  <div class="section">\n    <h2>🔬 Analize PDF CEDO</h2>\n{rows}\n  </div>')
    if rapoarte_instante:
        rows = "\n".join(make_row(f, "#6c3483") for f in rapoarte_instante)
        sections.append(f'  <div class="section">\n    <h2>🏛️ Rapoarte Instanțe Moldova</h2>\n{rows}\n  </div>')

    sections_html = "\n".join(sections) if sections else '<p style="color:#999;padding:20px">Niciun raport disponibil încă.</p>'

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ARBI – Rapoarte Monitorizare Moldova</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; color: #2c3e50; }}
.hdr {{ background: #1b4332; color: #fff; padding: 24px 40px; }}
.hdr h1 {{ font-size: 1.4rem; font-weight: 700; }}
.hdr small {{ font-size: 0.82rem; opacity: .8; }}
.wrap {{ max-width: 900px; margin: 30px auto; padding: 0 18px 60px; }}
.section {{ margin-bottom: 32px; }}
.section h2 {{ font-size: .85rem; text-transform: uppercase; letter-spacing: 1px;
               color: #1b4332; border-bottom: 2px solid #1b4332;
               padding-bottom: 6px; margin-bottom: 14px; }}
.row {{ background: #fff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,.07);
       padding: 14px 20px; margin-bottom: 10px;
       display: flex; align-items: center; justify-content: space-between;
       border-left: 4px solid #1b4332; gap: 12px; flex-wrap: wrap; }}
.date {{ font-weight: 700; font-size: .95rem; min-width: 110px; }}
.btns {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.btn {{ display: inline-block; padding: 5px 14px; border-radius: 5px;
       font-size: .78rem; font-weight: 600; text-decoration: none; }}
.btn-view {{ color: #fff; }}
.btn-view:hover {{ opacity: .85; }}
.btn-dl {{ background: #e8edf2; color: #1b4332; }}
.btn-dl:hover {{ background: #d0d8e4; }}
footer {{ text-align: center; font-size: .72rem; color: #aaa; padding-bottom: 20px; }}
@media (max-width: 600px) {{ .hdr {{ padding: 16px 18px; }} .row {{ flex-direction: column; align-items: flex-start; }} }}
</style>
</head>
<body>
<div class="hdr">
  <h1>🔍 ARBI – Rapoarte Monitorizare Moldova</h1>
  <small>Monitorizare automată zilnică &nbsp;·&nbsp; Actualizat: {now_utc} UTC</small>
</div>
<div class="wrap">
{sections_html}
</div>
<footer>Actualizat automat zilnic &nbsp;·&nbsp; ARBI Monitor &nbsp;·&nbsp; Republica Moldova</footer>
</body>
</html>"""

    index_path = REPORTS_DIR / "index.html"
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("Index updated: %s", index_path)


# ─── Main ─────────────────────────────────────────────────────────────────────

def find_latest_results() -> Path | None:
    if not RESULTS_DIR.is_dir():
        return None
    files = sorted(RESULTS_DIR.glob("journalism_*.json"))
    return files[-1] if files else None


def load_config() -> dict:
    config_path = BASE_DIR / "config" / "journalism_sites.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    cfg = load_config()
    latest = find_latest_results()

    if not latest:
        logger.warning("No journalism results JSON found.")
        now_utc = datetime.now(timezone.utc)
        data = {
            "date": now_utc.strftime("%Y-%m-%d"),
            "generated_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "lookback_hours": 26,
            "sources_checked": 0,
            "sources_ok": 0,
            "stats": {"total": 0, "investigative": 0, "by_source": {}, "by_category": {}},
            "articles": [],
        }
    else:
        with open(latest, encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded results from %s", latest)

    # Generate HTML report
    html_content = generate_html(data, cfg)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_date = data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    html_path = REPORTS_DIR / f"raport_jurnalism_{report_date}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("HTML report saved: %s", html_path)

    # Update index
    update_index()

    # Send Telegram
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if token and chat_id:
        message = format_telegram_report(data, cfg)
        send_long_telegram(token, chat_id, message)
        logger.info("Telegram report sent.")
    else:
        logger.warning("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Skipping Telegram.")


if __name__ == "__main__":
    main()
