"""
Formatează hotărârile penale ca un raport structurat pentru Telegram.

Structura raportului:
  Mesaj 1 — Antet + Sumar executiv
  Mesaj 2+ — Secțiuni pe tematică, cu dosarele grupate sub fiecare temă
"""
from collections import defaultdict
from datetime import date, timedelta

MAX_MSG_LEN = 4096
SEP_THICK = "━" * 24
SEP_THIN  = "─" * 24


def format_messages(decisions: list[dict], stats: dict, target_date: date | None = None) -> list[str]:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    if not decisions:
        return [_no_results(target_date)]

    parts: list[str] = []
    parts.append(_build_header(target_date, stats))
    parts.extend(_build_theme_sections(decisions))
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# Mesaj 1 — Antet + Sumar
# ─────────────────────────────────────────────────────────────────────────────

def _build_header(target_date: date, stats: dict) -> str:
    day_ro  = _day_ro(target_date)
    total   = stats["total"]
    n_inst  = len(stats["by_court"])
    n_theme = len(stats["by_theme"])

    lines = [
        f"⚖️ <b>RAPORT HOTĂRÂRI PENALE</b>",
        f"📅 <b>{day_ro}</b>",
        SEP_THICK,
        "",
        "📊 <b>SUMAR</b>",
        f"  • Total hotărâri: <b>{total}</b>",
        f"  • Instanțe active: <b>{n_inst}</b>",
        f"  • Tematici distincte: <b>{n_theme}</b>",
        "",
        SEP_THICK,
        "📋 <b>DISTRIBUȚIE PE TEMATICĂ</b>",
    ]

    for theme, count in list(stats["by_theme"].items())[:20]:
        pct = round(count / total * 100) if total else 0
        bar = _bar(count, total)
        lines.append(f"  {bar} {_esc(theme)} — <b>{count}</b> ({pct}%)")

    lines += [
        "",
        SEP_THICK,
        "🏛 <b>INSTANȚE ACTIVE</b>",
    ]
    for court, count in list(stats["by_court"].items()):
        lines.append(f"  • {_esc(court)}: <b>{count}</b>")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Mesaje 2+ — Secțiuni pe tematică
# ─────────────────────────────────────────────────────────────────────────────

def _build_theme_sections(decisions: list[dict]) -> list[str]:
    # Group by tematica, păstrând ordinea (most common first)
    groups: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        theme = (d.get("tematica_dosarului") or "Nespecificată").strip()
        groups[theme].append(d)

    # Sort groups by size descending
    sorted_groups = sorted(groups.items(), key=lambda x: -len(x[1]))

    messages: list[str] = []
    current = ""

    for theme, cases in sorted_groups:
        section = _build_section(theme, cases)
        # If section itself exceeds limit, split it internally
        if len(section) > MAX_MSG_LEN:
            chunks = _split_large_section(theme, cases)
            for chunk in chunks:
                if len(current) + len(chunk) + 1 > MAX_MSG_LEN:
                    if current.strip():
                        messages.append(current.rstrip())
                    current = chunk + "\n"
                else:
                    current += chunk + "\n"
        else:
            if len(current) + len(section) + 1 > MAX_MSG_LEN:
                if current.strip():
                    messages.append(current.rstrip())
                current = section + "\n"
            else:
                current += section + "\n"

    if current.strip():
        messages.append(current.rstrip())

    return messages


def _build_section(theme: str, cases: list[dict]) -> str:
    lines = [
        SEP_THICK,
        f"📋 <b>{_esc(theme.upper())}</b>  ({len(cases)} {'hotărâre' if len(cases) == 1 else 'hotărâri'})",
        SEP_THIN,
    ]
    for i, d in enumerate(cases, 1):
        lines.append(_format_case_row(i, d))
    return "\n".join(lines)


def _split_large_section(theme: str, cases: list[dict]) -> list[str]:
    """Split a section with many cases into multiple messages."""
    chunks = []
    header = f"{SEP_THICK}\n📋 <b>{_esc(theme.upper())}</b>  ({len(cases)} hotărâri)\n{SEP_THIN}\n"
    current = header
    for i, d in enumerate(cases, 1):
        row = _format_case_row(i, d) + "\n"
        if len(current) + len(row) > MAX_MSG_LEN:
            chunks.append(current.rstrip())
            current = f"📋 <b>{_esc(theme.upper())}</b> (continuare)\n{SEP_THIN}\n" + row
        else:
            current += row
    if current.strip():
        chunks.append(current.rstrip())
    return chunks


def _format_case_row(idx: int, d: dict) -> str:
    name    = _esc((d.get("denumirea_dosarului") or "—").strip())
    nr      = _esc((d.get("numarul_dosarului")   or "—").strip())
    court   = _esc((d.get("instanta_judecatoreasca") or "—").strip())
    d_pron  = _esc((d.get("data_pronuntarii")    or "—").strip())
    d_pub   = _esc((d.get("data_publicarii")     or "—").strip())

    return (
        f"<b>{idx}. {name}</b>\n"
        f"   🏛 {court}\n"
        f"   🔢 {nr}  |  📅 {d_pron}  |  🗓 {d_pub}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _no_results(target_date: date) -> str:
    return (
        f"⚖️ <b>RAPORT HOTĂRÂRI PENALE</b>\n"
        f"📅 <b>{_day_ro(target_date)}</b>\n"
        f"{SEP_THICK}\n\n"
        "ℹ️ Nu au fost găsite hotărâri în dosare penale pentru această dată."
    )


_MONTHS_RO = [
    "", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie",
    "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie",
]

def _day_ro(d: date) -> str:
    return f"{d.day} {_MONTHS_RO[d.month]} {d.year}"


def _bar(count: int, total: int, width: int = 6) -> str:
    filled = round((count / total) * width) if total else 0
    return "█" * filled + "░" * (width - filled)


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
