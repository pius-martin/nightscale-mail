# Project Rules

nightscale-mail — Standalone-CLI-Script für Massen-Mail über Microsoft Graph (Device-Code-Flow, kein SMTP, keine Admin-Rechte).

## Quick Start ("Start nightscale-mail")
- **Repo:** `/Users/piusmartin/nightscale-mail`. Noch keine `.claude/settings.local.json` — beim ersten Start die Standard-Allowlist anlegen (siehe globaler Repo-Schnellstart).
- **Ausführen:** `source .venv/bin/activate && python send_emails.py` (erster Lauf fragt Device-Code-Login ab). venv fehlt? `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.
- **Env** (`.env`): `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`.
- **Input:** `contacts.csv` (Empfänger) + `template.txt` (Mailtext mit Platzhaltern).

## Besonderheiten
- `.token_cache.bin` = Login-Session, sensibel, gitignored — nie committen.
- Kein Deployment — läuft lokal (bei Bedarf via cron).
