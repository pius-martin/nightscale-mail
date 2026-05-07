#!/usr/bin/env python3
"""Versendet Mails ueber Microsoft Graph API (kein SMTP, keine Admin-Rechte noetig)."""

import csv
import json
import os
import sys
import time
from pathlib import Path

import msal
import requests


GRAPH_SCOPE = ["https://graph.microsoft.com/Mail.Send"]
GRAPH_SENDMAIL = "https://graph.microsoft.com/v1.0/me/sendMail"
TOKEN_CACHE = Path(__file__).resolve().parent / ".token_cache.bin"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_template(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    if "\n" not in text:
        raise ValueError("Template braucht eine Betreffzeile, dann Leerzeile, dann Body.")
    subject, _, body = text.partition("\n\n")
    return subject.strip(), body


def load_contacts(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        contacts = []
        for row in reader:
            firmenname = (row.get("firmenname") or row.get("company") or "").strip()
            mail = (row.get("email") or row.get("mail") or "").strip()
            if not firmenname or not mail:
                continue
            contacts.append({"firmenname": firmenname, "email": mail})
        return contacts


def render(text: str, firmenname: str) -> str:
    return text.replace("{firmenname}", firmenname)


def get_access_token(client_id: str, tenant_id: str) -> str:
    cache = msal.SerializableTokenCache()
    if TOKEN_CACHE.exists():
        cache.deserialize(TOKEN_CACHE.read_text())

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    result = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(GRAPH_SCOPE, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=GRAPH_SCOPE)
        if "user_code" not in flow:
            raise RuntimeError(f"Device flow fehlgeschlagen: {json.dumps(flow, indent=2)}")
        print("\n" + "=" * 60)
        print(flow["message"])
        print("=" * 60 + "\n")
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(f"Login fehlgeschlagen: {result.get('error_description', result)}")

    if cache.has_state_changed:
        TOKEN_CACHE.write_text(cache.serialize())
        try:
            os.chmod(TOKEN_CACHE, 0o600)
        except OSError:
            pass

    return result["access_token"]


def send_mail(token: str, recipient: str, subject: str, body: str) -> None:
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": recipient}}],
        },
        "saveToSentItems": True,
    }
    r = requests.post(
        GRAPH_SENDMAIL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text}")


def main() -> int:
    root = Path(__file__).resolve().parent
    load_env(root / ".env")

    client_id = os.environ.get("AZURE_CLIENT_ID")
    tenant_id = os.environ.get("AZURE_TENANT_ID", "common")

    if not client_id:
        print("Fehler: AZURE_CLIENT_ID in .env setzen.", file=sys.stderr)
        print("Anleitung zum Anlegen der App-Registrierung: siehe Kommentar in .env.example", file=sys.stderr)
        return 1

    contacts_path = root / (sys.argv[1] if len(sys.argv) > 1 else "contacts.csv")
    template_path = root / (sys.argv[2] if len(sys.argv) > 2 else "template.txt")

    contacts = load_contacts(contacts_path)
    subject_tpl, body_tpl = load_template(template_path)

    if not contacts:
        print("Keine Kontakte gefunden.", file=sys.stderr)
        return 1

    print(f"Sende {len(contacts)} Mail(s) ueber Microsoft Graph API")
    confirm = input("Weiter? [j/N] ").strip().lower()
    if confirm not in ("j", "ja", "y", "yes"):
        print("Abgebrochen.")
        return 0

    token = get_access_token(client_id, tenant_id)

    sent, failed = 0, 0
    for i, contact in enumerate(contacts, 1):
        subject = render(subject_tpl, contact["firmenname"])
        body = render(body_tpl, contact["firmenname"])
        try:
            send_mail(token, contact["email"], subject, body)
            sent += 1
            print(f"[{i}/{len(contacts)}] OK   -> {contact['firmenname']} <{contact['email']}>")
        except Exception as e:
            failed += 1
            print(f"[{i}/{len(contacts)}] FEHL -> {contact['email']}: {e}", file=sys.stderr)
        time.sleep(1)

    print(f"\nFertig. Gesendet: {sent}, Fehlgeschlagen: {failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
