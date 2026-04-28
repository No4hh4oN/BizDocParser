from __future__ import annotations

import smtplib
import sys
from email.headerregistry import Address
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from app_config import load_mail_settings  # noqa: E402


PDF_DIR = ROOT / "rfp_dummy_pdf"

SENDERS = [
    ("김하준 과장", "전략기획팀"),
    ("박서연 책임", "디지털교육사업팀"),
    ("이도윤 매니저", "공공AI사업팀"),
    ("최민지 선임", "인프라운영팀"),
    ("정우진 PM", "성과관리혁신팀"),
]


def address(display_name: str, email_address: str) -> Address:
    username, domain = email_address.rsplit("@", 1)
    return Address(display_name=display_name, username=username, domain=domain)


def build_message(
    sender_email: str,
    recipient: str,
    pdf_path: Path,
    sender_name: str,
    team: str,
) -> EmailMessage:
    message = EmailMessage(policy=SMTP)
    message["Subject"] = f"[RFP 검토요청/재발송] {pdf_path.stem}"
    message["From"] = address(f"{sender_name} ({team})", sender_email)
    message["To"] = address("", recipient)
    message["Reply-To"] = address(sender_name, sender_email)
    message.set_content(
        "\n".join(
            [
                f"안녕하세요. {team} {sender_name}입니다.",
                "",
                "RFP 검토용 더미 PDF를 전달드립니다.",
                "첨부파일 확인 후 메일 조회/다운로드/분석 UI에서 테스트해 주세요.",
                "",
                f"첨부: {pdf_path.name}",
            ]
        ),
        charset="utf-8",
    )
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return message


def main() -> None:
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        raise RuntimeError(f"{PDF_DIR} 폴더에 PDF가 없습니다.")

    settings = load_mail_settings()
    recipient = settings.email_address

    with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port) as smtp:
        smtp.login(settings.email_address, settings.password)
        for index, pdf_path in enumerate(pdf_files, start=1):
            sender_name, team = SENDERS[(index - 1) % len(SENDERS)]
            message = build_message(settings.email_address, recipient, pdf_path, sender_name, team)
            smtp.send_message(message)
            print(f"sent {index}/{len(pdf_files)}: {pdf_path.name} as {sender_name} ({team})")

    print(f"done: sent {len(pdf_files)} messages to {recipient}")


if __name__ == "__main__":
    main()
