from datetime import date

MAX_MSG_LEN = 4096

FIELD_LABELS = {
    "nr_dosar": "Nr. dosar",
    "data": "Data",
    "instanta": "Instanța",
    "judecator": "Judecător",
    "tip_dosar": "Tip cauză",
    "solutie": "Soluție",
}

FIELD_EMOJIS = {
    "nr_dosar": "⚖️",
    "data": "📅",
    "instanta": "🏛",
    "judecator": "👨‍⚖️",
    "tip_dosar": "📋",
    "solutie": "✅",
}

EXTRA_FIELD_EMOJI = "🔹"
DIVIDER = "─" * 20


def format_messages(decisions: list[dict], target_date: date | None = None) -> list[str]:
    if target_date is None:
        from datetime import timedelta
        target_date = date.today() - timedelta(days=1)

    date_display = target_date.strftime("%d.%m.%Y")

    if not decisions:
        return [
            f"⚖️ <b>Hotărâri penale — {date_display}</b>\n\n"
            f"ℹ️ Nu au fost găsite hotărâri în dosare penale pentru această dată."
        ]

    header = (
        f"⚖️ <b>Hotărâri penale — {date_display}</b>\n"
        f"📊 Total: <b>{len(decisions)}</b> hotărâri\n"
    )

    blocks = [_format_decision(i + 1, d) for i, d in enumerate(decisions)]

    return _split_into_messages(header, blocks)


def _format_decision(idx: int, d: dict) -> str:
    lines = [f"<b>#{idx}</b>"]

    # Known fields in preferred order
    for key in ["nr_dosar", "data", "instanta", "judecator", "tip_dosar", "solutie"]:
        value = d.get(key, "").strip()
        if value:
            label = FIELD_LABELS[key]
            emoji = FIELD_EMOJIS[key]
            lines.append(f"{emoji} <b>{label}:</b> {_escape(value)}")

    # Any extra fields not in the known set
    known = set(FIELD_LABELS.keys()) | {"link", "raw_text"}
    for key, value in d.items():
        if key not in known and value and str(value).strip():
            label = key.replace("_", " ").title()
            lines.append(f"{EXTRA_FIELD_EMOJI} <b>{label}:</b> {_escape(str(value).strip())}")

    # Raw text fallback (div-based scraped results)
    if "raw_text" in d and not any(k in d for k in FIELD_LABELS):
        lines.append(f"📄 {_escape(d['raw_text'])}")

    # Link
    if d.get("link"):
        lines.append(f"🔗 <a href=\"{d['link']}\">Detalii hotărâre</a>")

    lines.append(DIVIDER)
    return "\n".join(lines)


def _split_into_messages(header: str, blocks: list[str]) -> list[str]:
    messages = []
    current = header + "\n"

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


def _escape(text: str) -> str:
    # Escape HTML special chars for Telegram HTML parse mode
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
