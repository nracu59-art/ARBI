"""
CLI pentru gestiunea dosarelor active și sarcinilor operative ale ARBI.

Utilizare:
  python workspace/manage.py add-case    Adaugă dosar nou
  python workspace/manage.py add-task    Adaugă sarcină nouă
  python workspace/manage.py list-cases  Listează dosarele
  python workspace/manage.py list-tasks  Listează sarcinile
  python workspace/manage.py update-case Actualizează stadiu dosar
  python workspace/manage.py close-case  Marchează dosar ca închis
  python workspace/manage.py close-task  Marchează sarcină ca realizată
"""

import argparse
import json
import os
import sys
from datetime import date, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "cases.json")

STADII_VALIDE = ["activ", "suspendat", "inchis", "executare", "contestat"]
PRIORITATI_VALIDE = ["inalta", "medie", "scazuta"]
TIPURI_VALIDE = [
    "confiscare",
    "sechestru",
    "recuperare_creanta",
    "cooperare_internationala",
    "altele",
]


# ─────────────────────────────────────────────────────────────────────────────
# I/O baza de date
# ─────────────────────────────────────────────────────────────────────────────

def load_db() -> dict:
    if not os.path.exists(DB_PATH):
        return {"meta": {}, "dosare": [], "sarcini": []}
    with open(DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_db(db: dict) -> None:
    db["meta"]["ultima_actualizare"] = date.today().isoformat()
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def _next_id(items: list, prefix: str) -> str:
    existing = [x.get("id", "") for x in items if x.get("id", "").startswith(prefix)]
    nums = [int(x[len(prefix):]) for x in existing if x[len(prefix):].isdigit()]
    return f"{prefix}{(max(nums) + 1) if nums else 1:04d}"


# ─────────────────────────────────────────────────────────────────────────────
# Dosare
# ─────────────────────────────────────────────────────────────────────────────

def cmd_add_case(args: argparse.Namespace) -> None:
    db = load_db()
    dosar_id = _next_id(db["dosare"], "D")
    dosar = {
        "id": dosar_id,
        "nr_dosar": args.nr,
        "titlu": args.titlu,
        "tip": args.tip,
        "stadiu": args.stadiu,
        "valoare_ron": args.valoare,
        "instanta": args.instanta or "",
        "judecator": args.judecator or "",
        "data_deschidere": args.data or date.today().isoformat(),
        "termen_urm": args.termen or "",
        "note": args.note or "",
        "creat_la": datetime.now().isoformat(timespec="seconds"),
    }
    db["dosare"].append(dosar)
    save_db(db)
    print(f"✅ Dosar adăugat: [{dosar_id}] {args.titlu} (nr. {args.nr})")


def cmd_list_cases(args: argparse.Namespace) -> None:
    db = load_db()
    dosare = db["dosare"]

    if args.stadiu:
        dosare = [d for d in dosare if d.get("stadiu") == args.stadiu]
    if not args.toate:
        dosare = [d for d in dosare if d.get("stadiu") != "inchis"]

    if not dosare:
        print("ℹ️  Nu există dosare cu criteriile selectate.")
        return

    total_val = sum(d.get("valoare_ron", 0) or 0 for d in dosare)
    print(f"\n{'─'*70}")
    print(f"  DOSARE ARBI  ({len(dosare)} dosare  |  valoare totală: {total_val:,.0f} RON)")
    print(f"{'─'*70}")
    for d in sorted(dosare, key=lambda x: x.get("stadiu", "")):
        stadiu_icon = {"activ": "🟢", "suspendat": "🟡", "executare": "🔵",
                       "contestat": "🔴", "inchis": "⚫"}.get(d.get("stadiu", ""), "⚪")
        val = f"{d.get('valoare_ron', 0):,.0f} RON" if d.get("valoare_ron") else "—"
        termen = f"  ⏰ {d['termen_urm']}" if d.get("termen_urm") else ""
        print(f"  {stadiu_icon} [{d['id']}] {d['titlu']}")
        print(f"       Nr: {d.get('nr_dosar','—')}  |  Tip: {d.get('tip','—')}  |  Valoare: {val}{termen}")
        if d.get("instanta"):
            print(f"       Instanță: {d['instanta']}")
    print(f"{'─'*70}\n")


def cmd_update_case(args: argparse.Namespace) -> None:
    db = load_db()
    for d in db["dosare"]:
        if d["id"] == args.id:
            if args.stadiu:
                d["stadiu"] = args.stadiu
            if args.termen:
                d["termen_urm"] = args.termen
            if args.note:
                d["note"] = args.note
            if args.judecator:
                d["judecator"] = args.judecator
            save_db(db)
            print(f"✅ Dosar {args.id} actualizat.")
            return
    print(f"❌ Dosar cu ID {args.id} nu a fost găsit.", file=sys.stderr)
    sys.exit(1)


def cmd_close_case(args: argparse.Namespace) -> None:
    db = load_db()
    for d in db["dosare"]:
        if d["id"] == args.id:
            d["stadiu"] = "inchis"
            d["data_inchidere"] = date.today().isoformat()
            if args.note:
                d["note"] = (d.get("note", "") + f" | {args.note}").strip(" |")
            save_db(db)
            print(f"✅ Dosar {args.id} marcat ca închis.")
            return
    print(f"❌ Dosar cu ID {args.id} nu a fost găsit.", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Sarcini
# ─────────────────────────────────────────────────────────────────────────────

def cmd_add_task(args: argparse.Namespace) -> None:
    db = load_db()
    task_id = _next_id(db["sarcini"], "T")

    if args.dosar:
        ids = [d["id"] for d in db["dosare"]]
        if args.dosar not in ids:
            print(f"⚠️  Dosarul {args.dosar} nu există. Sarcina va fi creată fără dosar asociat.")

    task = {
        "id": task_id,
        "dosar_id": args.dosar or "",
        "descriere": args.desc,
        "responsabil": args.responsabil or "",
        "prioritate": args.prioritate,
        "termen": args.termen or "",
        "status": "deschis",
        "creat_la": datetime.now().isoformat(timespec="seconds"),
    }
    db["sarcini"].append(task)
    save_db(db)
    print(f"✅ Sarcină adăugată: [{task_id}] {args.desc}")


def cmd_list_tasks(args: argparse.Namespace) -> None:
    db = load_db()
    sarcini = db["sarcini"]

    if not args.toate:
        sarcini = [t for t in sarcini if t.get("status") == "deschis"]
    if args.urgente:
        sarcini = [t for t in sarcini if t.get("prioritate") == "inalta"]
    if args.dosar:
        sarcini = [t for t in sarcini if t.get("dosar_id") == args.dosar]

    today = date.today().isoformat()

    def sort_key(t):
        p_ord = {"inalta": 0, "medie": 1, "scazuta": 2}
        return (p_ord.get(t.get("prioritate", ""), 9), t.get("termen", "9999"))

    sarcini = sorted(sarcini, key=sort_key)

    if not sarcini:
        print("ℹ️  Nu există sarcini cu criteriile selectate.")
        return

    print(f"\n{'─'*70}")
    print(f"  SARCINI ARBI  ({len(sarcini)} sarcini deschise)")
    print(f"{'─'*70}")
    for t in sarcini:
        prio_icon = {"inalta": "🔴", "medie": "🟡", "scazuta": "🟢"}.get(t.get("prioritate", ""), "⚪")
        termen = t.get("termen", "")
        termen_str = f"  ⏰ {termen}" if termen else ""
        overdue = " ‼️ DEPĂȘIT" if termen and termen < today else ""
        dosar_str = f"  [{t['dosar_id']}]" if t.get("dosar_id") else ""
        resp = f"  → {t['responsabil']}" if t.get("responsabil") else ""
        print(f"  {prio_icon} [{t['id']}]{dosar_str} {t['descriere']}")
        print(f"       Prioritate: {t.get('prioritate','—')}{termen_str}{overdue}{resp}")
    print(f"{'─'*70}\n")


def cmd_close_task(args: argparse.Namespace) -> None:
    db = load_db()
    for t in db["sarcini"]:
        if t["id"] == args.id:
            t["status"] = "realizat"
            t["realizat_la"] = date.today().isoformat()
            save_db(db)
            print(f"✅ Sarcina {args.id} marcată ca realizată.")
            return
    print(f"❌ Sarcina cu ID {args.id} nu a fost găsită.", file=sys.stderr)
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Parser CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="manage.py",
        description="ARBI — Gestiune dosare și sarcini operative",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # add-case
    p_ac = sub.add_parser("add-case", help="Adaugă dosar nou")
    p_ac.add_argument("--nr", required=True, help="Numărul dosarului (ex: 12/2024)")
    p_ac.add_argument("--titlu", required=True, help="Titlul dosarului (ex: Popescu Ion)")
    p_ac.add_argument("--tip", choices=TIPURI_VALIDE, default="confiscare")
    p_ac.add_argument("--stadiu", choices=STADII_VALIDE, default="activ")
    p_ac.add_argument("--valoare", type=float, default=0, help="Valoare estimată (RON)")
    p_ac.add_argument("--instanta", help="Instanța judecătorească")
    p_ac.add_argument("--judecator", help="Judecătorul cauzei")
    p_ac.add_argument("--data", help="Data deschiderii (YYYY-MM-DD)")
    p_ac.add_argument("--termen", help="Termenul următor (YYYY-MM-DD)")
    p_ac.add_argument("--note", help="Note suplimentare")

    # list-cases
    p_lc = sub.add_parser("list-cases", help="Listează dosarele active")
    p_lc.add_argument("--stadiu", choices=STADII_VALIDE, help="Filtrare după stadiu")
    p_lc.add_argument("--toate", action="store_true", help="Include și dosarele închise")

    # update-case
    p_uc = sub.add_parser("update-case", help="Actualizează un dosar")
    p_uc.add_argument("--id", required=True, help="ID dosar (ex: D0001)")
    p_uc.add_argument("--stadiu", choices=STADII_VALIDE)
    p_uc.add_argument("--termen", help="Nou termen (YYYY-MM-DD)")
    p_uc.add_argument("--note")
    p_uc.add_argument("--judecator")

    # close-case
    p_cc = sub.add_parser("close-case", help="Marchează dosar ca închis")
    p_cc.add_argument("--id", required=True)
    p_cc.add_argument("--note", help="Motiv închidere")

    # add-task
    p_at = sub.add_parser("add-task", help="Adaugă sarcină nouă")
    p_at.add_argument("--desc", required=True, help="Descrierea sarcinii")
    p_at.add_argument("--dosar", help="ID dosar asociat (ex: D0001)")
    p_at.add_argument("--prioritate", choices=PRIORITATI_VALIDE, default="medie")
    p_at.add_argument("--termen", help="Termen limită (YYYY-MM-DD)")
    p_at.add_argument("--responsabil", help="Persoana responsabilă")

    # list-tasks
    p_lt = sub.add_parser("list-tasks", help="Listează sarcinile")
    p_lt.add_argument("--urgente", action="store_true", help="Doar sarcini cu prioritate înaltă")
    p_lt.add_argument("--dosar", help="Filtrare după dosar (ex: D0001)")
    p_lt.add_argument("--toate", action="store_true", help="Include și sarcinile realizate")

    # close-task
    p_ct = sub.add_parser("close-task", help="Marchează sarcină ca realizată")
    p_ct.add_argument("--id", required=True, help="ID sarcină (ex: T0001)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "add-case": cmd_add_case,
        "list-cases": cmd_list_cases,
        "update-case": cmd_update_case,
        "close-case": cmd_close_case,
        "add-task": cmd_add_task,
        "list-tasks": cmd_list_tasks,
        "close-task": cmd_close_task,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
