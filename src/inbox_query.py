from __future__ import annotations

import email
import imaplib
import re
from datetime import date, timedelta
from email import policy
from email.message import EmailMessage, Message
from email.utils import parsedate_to_datetime

from app_config import decode_mime_value, load_mail_settings


INBOX_MAILBOX = "inbox"
DEFAULT_RELATED_MAIL_TERMS = (
    "발주서",
    "발주",
    "구매요청",
    "구매 요청",
    "주문서",
    "purchase order",
    "po-",
    "po_",
    "p/o",
    "견적서",
    "견적",
    "계약서",
    "납품요청",
    "납품 요청",
    "검수요청",
    "검수 요청",
    "rfp",
    "제안요청",
    "제안 요청",
    "제안요청서",
    "검토요청",
    "검토 요청",
)


def open_inbox() -> imaplib.IMAP4_SSL:
    settings = load_mail_settings()
    mail = imaplib.IMAP4_SSL(settings.imap_server)
    mail.login(settings.email_address, settings.password)
    result, _ = mail.select(INBOX_MAILBOX)
    if result != "OK":
        mail.logout()
        raise RuntimeError("inbox 메일함을 열 수 없습니다.")
    return mail


def imap_since_date(period: str) -> str | None:
    if period == "all":
        return None
    try:
        days = max(int(period), 1)
    except ValueError:
        days = 7
    since = date.today() - timedelta(days=days - 1)
    return since.strftime("%d-%b-%Y")


def decode_text_part(part: Message | EmailMessage) -> str:
    try:
        content = part.get_content()
        return content if isinstance(content, str) else ""
    except Exception:
        payload = part.get_payload(decode=True)
        if not payload:
            return ""
        charset = part.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")


def body_preview(message: Message | EmailMessage, max_length: int = 260) -> str:
    candidates: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.is_multipart():
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() == "text/plain":
                candidates.append(decode_text_part(part))
    elif message.get_content_type() == "text/plain":
        candidates.append(decode_text_part(message))

    text = " ".join(" ".join(candidate.split()) for candidate in candidates if candidate)
    return text[:max_length]


def byte_size_label(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size} B"


def list_attachments(message: Message | EmailMessage) -> list[dict[str, object]]:
    attachments: list[dict[str, object]] = []
    for part in message.walk() if message.is_multipart() else [message]:
        filename = part.get_filename()
        if not filename:
            continue

        filename = decode_mime_value(filename)
        payload = part.get_payload(decode=True) or b""
        content_type = part.get_content_type()
        is_pdf = filename.lower().endswith(".pdf") or content_type == "application/pdf"
        attachments.append(
            {
                "name": filename,
                "size": len(payload),
                "sizeLabel": byte_size_label(len(payload)),
                "contentType": content_type,
                "isPdf": is_pdf,
            }
        )
    return attachments


def formatted_mail_date(value: str | None) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone()
        return parsed.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return value


def fetch_message_by_uid(mail: imaplib.IMAP4_SSL, uid: str) -> Message | EmailMessage | None:
    if not uid.isdigit():
        raise RuntimeError(f"잘못된 메일 UID입니다: {uid}")

    result, data = mail.uid("fetch", uid, "(RFC822)")
    if result != "OK":
        return None

    for item in data:
        if isinstance(item, tuple) and item[1]:
            return email.message_from_bytes(item[1], policy=policy.default)
    return None


def search_mail_uids(mail: imaplib.IMAP4_SSL, period: str) -> list[str]:
    since = imap_since_date(period)
    if since:
        result, data = mail.uid("search", None, "SINCE", since)
    else:
        result, data = mail.uid("search", None, "ALL")

    if result != "OK":
        raise RuntimeError("메일 검색에 실패했습니다.")
    return [uid.decode("ascii") for uid in data[0].split()]


def compact_search_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.lower())


def split_search_terms(search_text: str) -> list[str]:
    raw_terms = [term.strip() for term in re.split(r"[,;/\n]+", search_text) if term.strip()]
    if not raw_terms:
        return list(DEFAULT_RELATED_MAIL_TERMS)

    normalized_raw_terms = {compact_search_text(term) for term in raw_terms}
    default_triggers = {"발주서", "발주", "purchaseorder", "po", "rfp", "제안요청", "검토요청"}
    if normalized_raw_terms & default_triggers:
        terms = [*raw_terms, *DEFAULT_RELATED_MAIL_TERMS]
    else:
        terms = raw_terms

    deduplicated: list[str] = []
    seen: set[str] = set()
    for term in terms:
        key = compact_search_text(term)
        if not key or key in seen:
            continue
        seen.add(key)
        deduplicated.append(term)
    return deduplicated


def matched_search_terms(haystack: str, terms: list[str]) -> list[str]:
    normalized_haystack = haystack.lower()
    compact_haystack = compact_search_text(haystack)
    matched: list[str] = []
    for term in terms:
        normalized_term = term.lower()
        compact_term = compact_search_text(term)
        if normalized_term in normalized_haystack or (compact_term and compact_term in compact_haystack):
            matched.append(term)
    return matched


def message_to_summary(uid: str, message: Message | EmailMessage) -> dict[str, object]:
    subject = decode_mime_value(str(message.get("Subject", "")))
    from_value = decode_mime_value(str(message.get("From", "")))
    preview = body_preview(message)
    attachments = list_attachments(message)
    return {
        "id": uid,
        "receivedAt": formatted_mail_date(str(message.get("Date", ""))),
        "from": from_value,
        "subject": subject,
        "body": preview,
        "attachments": attachments,
    }


def list_inbox_mails(search_text: str, period: str, limit: int = 50) -> list[dict[str, object]]:
    search_terms = split_search_terms(search_text)
    mails: list[dict[str, object]] = []
    mail = open_inbox()
    try:
        for uid in reversed(search_mail_uids(mail, period)):
            message = fetch_message_by_uid(mail, uid)
            if message is None:
                continue

            summary = message_to_summary(uid, message)
            attachment_names = " ".join(str(item["name"]) for item in summary["attachments"])
            haystack = " ".join(
                [
                    str(summary["subject"]),
                    str(summary["from"]),
                    str(summary["body"]),
                    attachment_names,
                ]
            ).lower()
            matched_terms = matched_search_terms(haystack, search_terms)
            if search_terms and not matched_terms:
                continue

            if not any(attachment["isPdf"] for attachment in summary["attachments"]):
                continue

            summary["matchedTerms"] = matched_terms
            mails.append(summary)
            if len(mails) >= limit:
                break
    finally:
        mail.logout()

    return mails
