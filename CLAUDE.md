# ARBI — Agenția de Recuperare a Bunurilor Infracționale

Sistem automat de monitorizare juridică și gestiune operațională pentru recuperarea bunurilor infracționale.

## Arhitectura sistemului

```
ARBI/
├── main.py                    # Bot zilnic hotărâri penale → Telegram
├── scraper.py                 # Scraper instante.justice.md (Playwright)
├── analyzer.py                # Statistici hotărâri
├── formatter.py               # Formatare mesaje Telegram
├── pdf_analyzer.py            # Analiză PDF-uri confiscare/sechestru → Excel
│
├── scripts/
│   ├── echr_checker.py        # Interogare HUDOC API (CEDO)
│   ├── generate_html_report.py# Raport HTML CEDO
│   └── send_report.py         # Trimitere raport Telegram
│
├── workspace/
│   ├── cases.json             # Baza de date dosare active
│   ├── manage.py              # CLI gestiune dosare & sarcini
│   └── build_dashboard.py     # Generare dashboard HTML unificat
│
├── results/                   # JSON-uri ECHR zilnice (echr_YYYY-MM-DD.json)
├── reports/                   # Rapoarte HTML CEDO (raport_cedo_YYYY-MM-DD.html)
├── dashboard/                 # Dashboard unificat generat automat
│
└── .github/workflows/
    ├── court_decisions.yml    # 07:30 EEST — hotărâri penale zilnice
    ├── echr_monitor.yml       # 22:00 + 07:30 EEST — monitorizare CEDO
    ├── analyze-confiscation.yml # 08:30 EEST — analiză PDF confiscare
    └── build-dashboard.yml    # 09:00 EEST — dashboard unificat zilnic
```

## Fluxuri automate zilnice

| Ora (EEST) | Workflow | Output |
|---|---|---|
| 07:30 | `court_decisions.yml` | Telegram: hotărâri penale |
| 07:30 | `echr_monitor.yml` (raport) | HTML + Telegram: decizii CEDO |
| 08:30 | `analyze-confiscation.yml` | Excel: confiscare/sechestru |
| 09:00 | `build-dashboard.yml` | HTML: dashboard integrat |
| 22:00 | `echr_monitor.yml` (fetch) | JSON: rezultate HUDOC |

## Secrets GitHub necesare

| Secret | Utilizat de |
|---|---|
| `TELEGRAM_BOT_TOKEN` | CEDO monitor (send_report.py) |
| `TELEGRAM_CHAT_ID` | CEDO monitor |
| `COURT_BOT_TOKEN` | Bot hotărâri penale |
| `COURT_CHAT_ID` | Bot hotărâri penale |

## Gestiune dosare (workspace/manage.py)

```bash
# Adaugă dosar nou
python workspace/manage.py add-case --nr "12/2024" --titlu "Popescu Ion" --valoare 850000 --stadiu activ

# Adaugă sarcină
python workspace/manage.py add-task --dosar "12/2024" --desc "Notificare instituție bancară" --termen "2026-06-01" --prioritate inalta

# Listează dosare active
python workspace/manage.py list-cases

# Listează sarcini urgente
python workspace/manage.py list-tasks --urgente

# Generează dashboard
python workspace/build_dashboard.py
```

## Comenzi utile

```bash
# Rulare manuală bot hotărâri
python main.py

# Rulare manuală checker CEDO
python scripts/echr_checker.py

# Rulare manuală analiză PDF
python pdf_analyzer.py

# Build dashboard local
python workspace/build_dashboard.py
```
