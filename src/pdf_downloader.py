from __future__ import annotations

import re
from pathlib import Path

from app_config import BASE_DIR, DOWNLOAD_DIR, decode_mime_value
from inbox_query import byte_size_label, fetch_message_by_uid, open_inbox


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name or "attachment.pdf"


def unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = directory / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def download_pdf_attachments(mail_ids: list[str]) -> list[dict[str, object]]:
    if not mail_ids:
        return []

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: list[dict[str, object]] = []
    mail = open_inbox()
    try:
        for uid in mail_ids:
            message = fetch_message_by_uid(mail, uid)
            if message is None:
                continue

            subject = decode_mime_value(str(message.get("Subject", "")))
            for part in message.walk() if message.is_multipart() else [message]:
                filename = part.get_filename()
                if not filename:
                    continue

                filename = safe_filename(decode_mime_value(filename))
                content_type = part.get_content_type()
                if not (filename.lower().endswith(".pdf") or content_type == "application/pdf"):
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                destination = unique_path(DOWNLOAD_DIR, filename)
                destination.write_bytes(payload)
                relative_path = destination.relative_to(BASE_DIR).as_posix()
                downloaded.append(
                    {
                        "id": relative_path,
                        "name": destination.name,
                        "relativePath": relative_path,
                        "size": len(payload),
                        "sizeLabel": byte_size_label(len(payload)),
                        "sourceMailId": uid,
                        "sourceSubject": subject,
                    }
                )
    finally:
        mail.logout()

    return downloaded
