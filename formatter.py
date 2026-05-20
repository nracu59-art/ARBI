from datetime import date, timedelta

MAX_MSG_LEN = 4096
TOP_N = 15   # max entries shown in each ranking


def format_messages(decisions: list[dict], stats: dict, target_date: date | None = None) -> list[str]:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_display = target_date.strftime("%d.%m.%Y")

    if not decisions:
        return [
            f"⚖️ <b>Hotărâri penale — {date_display}</b>\n\n"
            "ℹ️ Nu au fost găsite hotărâri în dosare penale pentru această dată."
        ]

    parts: list[str] = []

    # ── Mesaj 1: Sumar + analiză ──────────────────────────────────────────────
    parts.append(_build_summary(date_display, stats))

    # ── Mesaje 2+: Hotărârile individuale ─────────────────────────────────────
    decision_blocks = [_format_decision(i + 1, d) for i, d in enumerate(decisions)]
    parts.extend(_split_decision_blocks(decision_blocks))

    return parts


# ─────────────────────────────────────────────────────────────────────────────
# Summary / analysis message
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(date_display: str, stats: dict) -> str:
    total = stats["total"]
    lines = [
        f"⚖️ <b>Hotărâri penale — {date_display}</b>",
        f"📊 <b>Total hotărâri: {total}</b>",
        "",
    ]

    # Classification by Tematica
    if stats["by_theme"]:
        lines.append("📋 <b>Clasificare după tematică:</b>")
        for theme, count in list(stats["by_theme"].items())[:TOP_N]:
            bar = _bar(count, total)
            lines.append(f"  {bar} {_esc(theme)} — <b>{count}</b>")
        remaining = total - sum(list(stats["by_theme"].values())[:TOP_N])
        if remaining > 0:
            lines.append(f"  … și alte <b>{remaining}</b> hotărâri")
        lines.append("")

    # Classification by Article
    if stats["by_article"]:
        lines.append("📌 <b>Articole CP frecvente:</b>")
        for art, count in list(stats["by_article"].items())[:10]:
            lines.append(f"  • {_esc(art)}: <b>{count}</b>")
        lines.append("")

    # Classification by Court
    if stats["by_court"]:
        lines.append("🏛 <b>Instanțe judecătorești:</b>")
        for court, count in list(stats["by_court"].items())[:10]:
            lines.append(f"  • {_esc(court)}: <b>{count}</b>")
        lines.append("")

    # Top judges (only if meaningful)
    if stats["by_judge"] and len(stats["by_judge"]) > 1:
        lines.append("👨‍⚖️ <b>Judecători (top 5):</b>")
        for judge, count in list(stats["by_judge"].items())[:5]:
            lines.append(f"  • {_esc(judge)}: <b>{count}</b>")

    return "\n".join(lines)


def _bar(count: int, total: int, width: int = 8) -> str:
    filled = round((count / total) * width) if total else 0
    return "█" * filled + "░" * (width - filled)


# ─────────────────────────────────────────────────────────────────────────────
# Individual decision blocks
# ─────────────────────────────────────────────────────────────────────────────

DIVIDER = "─" * 22

def _format_decision(idx: int, d: dict) -> str:
    # Header: index + person/case name as title
    name = (d.get("denumirea_dosarului") or "").strip()
    header = f"<b>#{idx} — {_esc(name)}</b>" if name else f"<b>#{idx}</b>"
    lines = [header]

    def row(emoji: str, label: str, key: str) -> None:
        val = (d.get(key) or "").strip()
        if val:
            lines.append(f"{emoji} <b>{label}:</b> {_esc(val)}")

    row("🔢", "Nr. dosar", "numarul_dosarului")
    row("🏛", "Instanța", "instanta_judecatoreasca")
    row("👨‍⚖️", "Judecător", "judecator")
    row("📅", "Data pronunțării", "data_pronuntarii")
    row("📆", "Data înregistrării", "data_inregistrarii")
    row("🗓", "Data publicării", "data_publicarii")
    row("📋", "Tematica", "tematica_dosarului")

    if d.get("act_judecatoresc_url"):
        lines.append(f"🔗 <a href=\"{d['act_judecatoresc_url']}\">Act judecătoresc (PDF)</a>")

    lines.append(DIVIDER)
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Message splitting
# ─────────────────────────────────────────────────────────────────────────────

def _split_decision_blocks(blocks: list[str]) -> list[str]:
    messages: list[str] = []
    current = ""
    for block in blocks:
        candidate = current + block + "\n"
        if len(candidate) > MAX_MSG_LEN:
            if current.strip():
                messages.append(current.rstrip())
            current = block + "\n"
        else:
            current = candidate
    if current.strip():
        messages.append(current.rstrip())
    return messages


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
