from __future__ import annotations

import os
from dataclasses import dataclass
from email.header import decode_header, make_header
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "src":
    BASE_DIR = BASE_DIR.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
REPORT_OUTPUT = BASE_DIR / "result.csv"


@dataclass(frozen=True)
class MailSettings:
    smtp_server: str
    smtp_port: int
    imap_server: str
    email_address: str
    password: str


def load_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def bootstrap_env() -> None:
    for key, value in load_env(BASE_DIR / ".env").items():
        os.environ.setdefault(key, value)


def load_mail_settings() -> MailSettings:
    bootstrap_env()

    email_address = os.getenv("SMTP_EMAIL") or os.getenv("IMAP_EMAIL")
    password = os.getenv("SMTP_PASSWORD") or os.getenv("IMAP_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")

    if not email_address or not password:
        raise RuntimeError(
            "Missing mail credentials. Set SMTP_EMAIL/SMTP_PASSWORD or IMAP_EMAIL/IMAP_PASSWORD in .env."
        )

    return MailSettings(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        imap_server=imap_server,
        email_address=email_address,
        password=password,
    )


def decode_mime_value(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))
