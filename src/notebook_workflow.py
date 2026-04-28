from __future__ import annotations

import email
import imaplib
import os
import re
from email.header import decode_header, make_header
from pathlib import Path

import pdfplumber


DEFAULT_PURCHASE_MAIL_TERMS = (
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


def load_notebook_env(env_path: Path = Path(".env")) -> dict[str, str]:
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

    imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")
    email_address = os.getenv("IMAP_EMAIL")
    password = os.getenv("IMAP_PASSWORD", "").replace(" ", "")
    save_dir = os.getenv("SAVE_DIR", "./downloads")

    if not email_address or not password:
        raise RuntimeError("IMAP_EMAIL and IMAP_PASSWORD must be set in .env")

    return {
        "IMAP_SERVER": imap_server,
        "EMAIL": email_address,
        "PASSWORD": password,
        "SAVE_DIR": save_dir,
    }


def connect_inbox(imap_server: str, email_address: str, password: str) -> imaplib.IMAP4_SSL:
    # 1. IMAP 접속
    mail = imaplib.IMAP4_SSL(imap_server)
    mail.login(email_address, password)
    mail.select("inbox")
    print("Connected to mailbox")
    return mail


def compact_search_text(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", value.lower())


def build_purchase_mail_terms(subject_keywords: str | list[str] | tuple[str, ...] = "[발주서]") -> list[str]:
    if isinstance(subject_keywords, str):
        raw_terms = [term.strip() for term in re.split(r"[,;/\n]+", subject_keywords) if term.strip()]
    else:
        raw_terms = [term.strip() for term in subject_keywords if term.strip()]

    if not raw_terms:
        raw_terms = list(DEFAULT_PURCHASE_MAIL_TERMS)

    normalized_raw_terms = {compact_search_text(term) for term in raw_terms}
    default_triggers = {"발주서", "발주", "purchaseorder", "po", "rfp", "제안요청", "검토요청"}
    if normalized_raw_terms & default_triggers:
        terms = [*raw_terms, *DEFAULT_PURCHASE_MAIL_TERMS]
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


def subject_matches_terms(subject: str, terms: list[str]) -> list[str]:
    normalized_subject = subject.lower()
    compact_subject = compact_search_text(subject)
    matched: list[str] = []
    for term in terms:
        normalized_term = term.lower()
        compact_term = compact_search_text(term)
        if normalized_term in normalized_subject or (compact_term and compact_term in compact_subject):
            matched.append(term)
    return matched


def find_latest_purchase_order_mail(
    mail: imaplib.IMAP4_SSL,
    subject_keywords: str | list[str] | tuple[str, ...] = "[발주서]",
) -> email.message.Message | None:
    # 2. 메일 검색 (제목 필터는 직접 처리)
    result, data = mail.search(None, "ALL")
    if result != "OK":
        raise RuntimeError("메일 검색에 실패했습니다.")

    terms = build_purchase_mail_terms(subject_keywords)
    mail_ids = data[0].split()
    target_mail = None
    # 최근 메일부터 역순 탐색
    for mail_id in reversed(mail_ids):
        result, data = mail.fetch(mail_id, "(RFC822)")
        if result != "OK" or not data or not isinstance(data[0], tuple):
            continue

        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        # 제목 디코딩
        subject = str(make_header(decode_header(msg["Subject"])))
        matched_terms = subject_matches_terms(subject, terms)
        if matched_terms:
            print("대상 메일:", subject)
            print("매칭 키워드:", ", ".join(matched_terms))
            target_mail = msg
            break

    if target_mail is None:
        print("조건에 맞는 메일 없음")
    return target_mail


def download_pdf_attachments_from_message(target_mail: email.message.Message, save_dir: str = "./downloads") -> list[str]:
    # 3. PDF 첨부파일 다운로드
    os.makedirs(save_dir, exist_ok=True)

    pdf_files: list[str] = []
    for part in target_mail.walk():
        content_disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()

        if not filename or "attachment" not in content_disposition:
            continue

        filename = str(make_header(decode_header(filename)))

        if not filename.lower().endswith(".pdf"):
            continue

        filepath = os.path.join(save_dir, filename)
        with open(filepath, "wb") as f:
            f.write(part.get_payload(decode=True))
        print(f"다운로드 완료: {filepath}")
        pdf_files.append(filepath)

    if not pdf_files:
        print("PDF 첨부파일을 찾지 못했습니다.")

    return pdf_files


def extract_pdf_texts(pdf_files: list[str]) -> dict[str, str]:
    # 4. PDF 텍스트 추출
    extracted: dict[str, str] = {}
    for pdf_path in pdf_files:
        print(f"\n텍스트 추출: {pdf_path}")
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        print("---- 추출 텍스트 ----")
        print(full_text[:])
        extracted[pdf_path] = full_text
    return extracted


def run_notebook_purchase_order_flow(subject_keywords: str | list[str] | tuple[str, ...] = "[발주서]") -> dict[str, object]:
    settings = load_notebook_env()
    mail = connect_inbox(settings["IMAP_SERVER"], settings["EMAIL"], settings["PASSWORD"])
    try:
        target_mail = find_latest_purchase_order_mail(mail, subject_keywords)
        if target_mail is None:
            return {"mail": None, "pdf_files": [], "texts": {}}

        pdf_files = download_pdf_attachments_from_message(target_mail, settings["SAVE_DIR"])
        texts = extract_pdf_texts(pdf_files)
        return {
            "mail": target_mail,
            "pdf_files": pdf_files,
            "texts": texts,
        }
    finally:
        mail.logout()
