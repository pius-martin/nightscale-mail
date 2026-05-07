#!/usr/bin/env python3
"""Versendet vorgeschriebene Mails an eine Kontaktliste via Microsoft (SMTP)."""

import csv
import os
import smtplib
import ssl
import sys
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path


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


def build_message(
    *,
    sender_name: str,
    sender_email: str,
    recipient_email: str,
    subject: str,
    body: str,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def main() -> int:
    root = Path(__file__).resolve().parent
    load_env(root / ".env")

    sender_email = os.environ.get("SMTP_USER")
    sender_password = os.environ.get("SMTP_PASSWORD")
    sender_name = os.environ.get("SENDER_NAME", "").strip()
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    if not sender_email or not sender_password:
        print("Fehler: SMTP_USER und SMTP_PASSWORD in .env setzen.", file=sys.stderr)
        return 1
    if not sender_name:
        print("Fehler: SENDER_NAME in .env setzen (dein angezeigter Name).", file=sys.stderr)
        return 1

    contacts_path = root / (sys.argv[1] if len(sys.argv) > 1 else "contacts.csv")
    template_path = root / (sys.argv[2] if len(sys.argv) > 2 else "template.txt")

    contacts = load_contacts(contacts_path)
    subject_tpl, body_tpl = load_template(template_path)

    if not contacts:
        print("Keine Kontakte gefunden.", file=sys.stderr)
        return 1

    print(f"Sende {len(contacts)} Mail(s) als '{sender_name}' <{sender_email}>")
    print(f"SMTP: {smtp_host}:{smtp_port}")
    confirm = input("Weiter? [j/N] ").strip().lower()
    if confirm not in ("j", "ja", "y", "yes"):
        print("Abgebrochen.")
        return 0

    context = ssl.create_default_context()
    sent, failed = 0, 0
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(sender_email, sender_password)

        for i, contact in enumerate(contacts, 1):
            subject = render(subject_tpl, contact["firmenname"])
            body = render(body_tpl, contact["firmenname"])
            msg = build_message(
                sender_name=sender_name,
                sender_email=sender_email,
                recipient_email=contact["email"],
                subject=subject,
                body=body,
            )
            try:
                server.send_message(msg)
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
