"""
Analizează lista de hotărâri penale și returnează statistici structurate.
"""
from collections import Counter
import re


def analyze(decisions: list[dict]) -> dict:
    total = len(decisions)
    by_theme = _count_by_theme(decisions)
    by_court = _count_by_court(decisions)
    by_judge = _count_by_judge(decisions)
    by_article = _count_by_article(decisions)

    return {
        "total": total,
        "by_theme": by_theme,        # {theme_label: count}
        "by_court": by_court,        # {court_name: count}
        "by_judge": by_judge,        # {judge_name: count}
        "by_article": by_article,    # {article_ref: count}
    }


def _count_by_theme(decisions: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for d in decisions:
        raw = (d.get("tematica_dosarului") or "").strip()
        label = raw if raw else "Nespecificată"
        counter[label] += 1
    return dict(counter.most_common())


def _count_by_court(decisions: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for d in decisions:
        court = (d.get("instanta_judecatoreasca") or "").strip()
        if court:
            counter[court] += 1
    return dict(counter.most_common())


def _count_by_judge(decisions: list[dict]) -> dict[str, int]:
    counter: Counter = Counter()
    for d in decisions:
        judge = (d.get("judecator") or "").strip()
        if judge:
            counter[judge] += 1
    return dict(counter.most_common())


def _count_by_article(decisions: list[dict]) -> dict[str, int]:
    """
    Extrage referințele la articole din CP/CPP din câmpul Tematica dosarului.
    Ex: "art. 186 al.2 lit. b)" → "art. 186"
        "Articolul 186. Furtul" → "art. 186"
    """
    counter: Counter = Counter()
    pattern = re.compile(r"(?:art(?:icolul)?\.?\s*)(\d+)", re.IGNORECASE)
    for d in decisions:
        raw = (d.get("tematica_dosarului") or "").strip()
        matches = pattern.findall(raw)
        if matches:
            for m in set(matches):
                counter[f"art. {m}"] += 1
        elif raw:
            counter[raw[:50]] += 1  # fallback: first 50 chars as key
    return dict(counter.most_common())
