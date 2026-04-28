from __future__ import annotations

import argparse
import csv
import email
import imaplib
import os
import re
import smtplib
import textwrap
import time
from dataclasses import dataclass
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BASE_DIR = Path(__file__).resolve().parent
if BASE_DIR.name == "src":
    BASE_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "generated_purchase_orders"
DOWNLOAD_DIR = BASE_DIR / "downloads"
REPORT_OUTPUT = BASE_DIR / "result.csv"

FONT_REGULAR = "MalgunGothic"
FONT_BOLD = "MalgunGothicBold"
FONT_PATH_REGULAR = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_PATH_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")

PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = 174 * mm

COLOR_ACCENT = colors.HexColor("#29486C")
COLOR_ACCENT_LIGHT = colors.HexColor("#DCE6F1")
COLOR_PANEL = colors.HexColor("#F6F8FB")
COLOR_LINE = colors.HexColor("#A7B2C2")
COLOR_TEXT_MUTED = colors.HexColor("#4A5668")

ORDER_DATE = date.today()
START_DATE = ORDER_DATE + timedelta(days=1)
RESPONSE_DUE_DATE = ORDER_DATE + timedelta(days=2)
DELIVERY_DATE = ORDER_DATE + timedelta(days=21)

DOCUMENT_TITLE = "발 주 서"
DOCUMENT_SUBTITLE = "성과관리시스템 운영지원 및 자동화 고도화"
DOCUMENT_ISSUER = "샘플테크 정보전략실"
DOCUMENT_CLASS = "대외발송용"
PROJECT_NAME = "성과관리시스템 운영지원 및 자동화 고도화"
CONTRACT_TYPE = "총액계약(부가세 별도)"
PROCUREMENT_METHOD = "수의발주(사전 견적 협의)"
DELIVERY_LOCATION = "샘플테크 정보전략실 / 운영공유폴더"
MAIL_REPLY_METHOD = "이메일 회신 및 담당자 확인 전화 병행"
INSPECTION_TERMS = "납품 완료 후 3영업일 이내 검수 확인 및 보완 요청 반영"
PAYMENT_TERMS = "검수 완료 및 세금계산서 발행 기준 14일 이내 지급"
REPORTING_TERMS = "주간 진행 현황 이메일 공유, 주요 이슈는 1영업일 이내 유선 보고"
E_DOCUMENT_TERMS = "본 발주서는 이메일 회신을 통해 접수 여부를 확인합니다."


@dataclass(frozen=True)
class LineItem:
    code: str
    category: str
    name: str
    specification: str
    unit: str
    quantity: int
    unit_price: int
    deliverable_ref: str
    note: str

    @property
    def amount(self) -> int:
        return self.quantity * self.unit_price


@dataclass(frozen=True)
class Deliverable:
    deliverable_id: str
    name: str
    file_format: str
    due_date: date
    acceptance_criteria: str
    owner: str


@dataclass(frozen=True)
class Milestone:
    phase: str
    start_date: date
    end_date: date
    major_tasks: str
    review_owner: str


@dataclass(frozen=True)
class MailSettings:
    smtp_server: str
    smtp_port: int
    imap_server: str
    email_address: str
    password: str


ITEMS = [
    LineItem(
        code="OPS-01",
        category="운영지원",
        name="성과관리시스템 정기 유지보수",
        specification="월간 예방점검, 장애조치, 정기배포 지원",
        unit="식",
        quantity=1,
        unit_price=2_800_000,
        deliverable_ref="D1,D2",
        note="월간 운영보고 및 조치내역 포함",
    ),
    LineItem(
        code="AUT-01",
        category="자동화",
        name="메일 첨부 PDF 자동 수집 모듈 구축",
        specification="IMAP 연계, 중복방지, 저장 로그 구현",
        unit="식",
        quantity=1,
        unit_price=1_200_000,
        deliverable_ref="D3",
        note="운영계 반영 전 테스트 로그 제출",
    ),
    LineItem(
        code="ETL-01",
        category="데이터",
        name="PDF-CSV 실적 보고 자동화",
        specification="정형 추출, 결과 CSV 생성, 오류 로그 포함",
        unit="식",
        quantity=1,
        unit_price=850_000,
        deliverable_ref="D4",
        note="샘플 3종 기준 검증 결과 포함",
    ),
    LineItem(
        code="DOC-01",
        category="문서화",
        name="운영 매뉴얼 및 인수인계 문서 정비",
        specification="운영절차서, 장애대응서, 사용자 가이드",
        unit="식",
        quantity=1,
        unit_price=550_000,
        deliverable_ref="D5",
        note="최종본 PDF와 편집본 동시 제출",
    ),
]

DELIVERABLES = [
    Deliverable("D1", "착수보고서", "PDF", ORDER_DATE + timedelta(days=2), "범위, 일정, 담당체계가 명시된 초안 제출", "공급사 PM"),
    Deliverable("D2", "운영점검 및 유지보수 보고서", "PDF, XLS", ORDER_DATE + timedelta(days=14), "점검체크리스트, 조치내역, 미해결 이슈 포함", "운영담당"),
    Deliverable("D3", "메일 수집 자동화 모듈 및 실행 가이드", "ZIP, MD", ORDER_DATE + timedelta(days=17), "수신, 저장, 중복방지, 로그 기능 시연 가능", "개발담당"),
    Deliverable("D4", "PDF-CSV 추출 결과 샘플", "CSV", ORDER_DATE + timedelta(days=19), "샘플 3종 기준 누락 없이 컬럼 정리 완료", "데이터담당"),
    Deliverable("D5", "운영/인수인계 문서", "PDF, HWP", DELIVERY_DATE, "운영절차, 계정정보, 장애대응, 배포이력 정리", "품질담당"),
]

MILESTONES = [
    Milestone("착수 및 범위확정", START_DATE, ORDER_DATE + timedelta(days=2), "킥오프, 발주 범위 확정, 제출 일정 합의", "샘플테크 정보전략실"),
    Milestone("자동화 모듈 개발", ORDER_DATE + timedelta(days=3), ORDER_DATE + timedelta(days=10), "IMAP 수집, PDF 저장, 예외 처리 및 로그 구현", "공급사 PM"),
    Milestone("데이터 추출 및 시범운영", ORDER_DATE + timedelta(days=11), ORDER_DATE + timedelta(days=16), "PDF 텍스트/표 추출, CSV 포맷 정비, 샘플 검증", "성과관리운영팀"),
    Milestone("검수 및 문서화", ORDER_DATE + timedelta(days=17), DELIVERY_DATE, "최종 검수, 운영 매뉴얼 정비, 결과 공유", "샘플테크 정보전략실"),
]

BUYER = {
    "기관명": "샘플테크",
    "부서": "정보전략실",
    "검수부서": "성과관리운영팀",
    "담당자": "이서연 책임",
    "이메일": "order@sampletech.com",
    "연락처": "02-9876-5432",
    "주소": "서울특별시 마포구 월드컵북로 45",
}

SUPPLIER = {
    "회사명": "메일자동화솔루션 주식회사",
    "대표자": "김민수",
    "사업자등록번호": "123-45-67890",
    "담당자": "김민수 부장",
    "이메일": "biz@mailautomation.example.com",
    "연락처": "02-3456-7890",
    "주소": "서울특별시 영등포구 국제금융로 12",
}

BACKGROUND_POINTS = [
    "성과관리시스템 운영 과정에서 발주서 및 증빙자료를 메일로 수신한 뒤 수작업으로 저장, 정리, 공유하고 있어 업무부하가 발생하고 있습니다.",
    "첨부 PDF의 저장 위치, 파일명 규칙, 추출 결과 형식이 담당자별로 달라 후속 집계와 보고 자료 작성에 시간이 소요되고 있습니다.",
]

OBJECTIVE_POINTS = [
    "대외 발송용 발주서 형식을 표준화하여 문서 완성도와 재사용성을 높입니다.",
    "메일로 수신한 발주서 PDF를 자동 저장하고, 구조화된 CSV 데이터로 즉시 전환할 수 있는 흐름을 구축합니다.",
]

SCOPE_POINTS = [
    "정기 유지보수 및 운영지원",
    "IMAP 기반 첨부파일 자동 다운로드",
    "PDF 텍스트 및 표 데이터 추출",
    "CSV 리포트 자동 생성 및 운영 문서 정비",
]

QUALITY_REQUIREMENTS = [
    "추출 CSV는 품목, 금액, 일정, 조건 항목이 누락 없이 기록되어야 합니다.",
    "샘플 3종 이상의 PDF에 대해 항목 검증 결과를 함께 제출해야 합니다.",
]

SECURITY_REQUIREMENTS = [
    "메일 계정 및 인증정보는 환경변수로 관리하고 코드에 평문으로 저장하지 않습니다.",
    "다운로드한 PDF와 생성 CSV는 사내 저장소 기준으로 경로를 고정하고 접근 권한을 제한합니다.",
]

SUPPORT_REQUIREMENTS = [
    "오류 발생 시 영업일 기준 4시간 이내 1차 응답, 1영업일 이내 조치 계획을 회신합니다.",
    "운영 전환 시 실행 방법, 예외 처리 방식, 점검 포인트를 운영 문서에 반영합니다.",
]

SPECIAL_NOTES = [
    "본 발주서는 상호 협의된 견적 및 과업 범위를 기준으로 발행되었습니다.",
    "납품 완료 후 검수 확인서를 기준으로 세금계산서 발행 및 대금 지급 절차를 진행합니다.",
    "범위 변경 또는 일정 조정이 필요한 경우 발주 담당자와 사전 협의 후 서면으로 확정합니다.",
]

ITEM_BY_CODE = {item.code: item for item in ITEMS}
DELIVERABLE_BY_ID = {deliverable.deliverable_id: deliverable for deliverable in DELIVERABLES}
MILESTONE_BY_PHASE = {re.sub(r"\s+", "", milestone.phase): milestone for milestone in MILESTONES}


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
    password = (
        os.getenv("SMTP_PASSWORD")
        or os.getenv("IMAP_PASSWORD")
        or ""
    ).replace(" ", "")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")

    if not email_address or not password:
        raise RuntimeError(
            "SMTP_EMAIL/SMTP_PASSWORD or IMAP_EMAIL/IMAP_PASSWORD must be set in .env."
        )

    return MailSettings(
        smtp_server=smtp_server,
        smtp_port=smtp_port,
        imap_server=imap_server,
        email_address=email_address,
        password=password,
    )


def register_korean_fonts() -> None:
    for font_name, font_path in (
        (FONT_REGULAR, FONT_PATH_REGULAR),
        (FONT_BOLD, FONT_PATH_BOLD),
    ):
        if font_name in pdfmetrics.getRegisteredFontNames():
            continue
        if not font_path.exists():
            raise FileNotFoundError(f"Korean font not found: {font_path}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def won(value: int) -> str:
    return f"{value:,}원"


def order_number(sequence: int) -> str:
    return f"PO-{ORDER_DATE:%Y-%m%d}-{sequence:03d}"


def display_date(value: date) -> str:
    return value.strftime("%Y. %m. %d.")


def normalize_date(value: str) -> str:
    parts = re.findall(r"\d+", value)
    if len(parts) >= 3:
        return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
    return value


def parse_amount(value: str) -> int:
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else 0


def xml_text(value: str) -> str:
    return escape(value).replace("\n", "<br/>")


def points_to_html(points: list[str]) -> str:
    return "<br/>".join(f"{index}. {escape(point)}" for index, point in enumerate(points, start=1))


def lines_to_summary(lines: list[str]) -> str:
    return " | ".join(f"{index}. {line}" for index, line in enumerate(lines, start=1))


def tidy_extracted_text(value: str) -> str:
    tokens = value.split()
    if not tokens:
        return ""

    merged: list[str] = []
    index = 0
    while index < len(tokens):
        current = tokens[index]
        while (
            index + 1 < len(tokens)
            and re.fullmatch(r"[가-힣]+", current)
            and re.fullmatch(r"[가-힣]+", tokens[index + 1])
            and (len(current) == 1 or len(tokens[index + 1]) == 1)
        ):
            current += tokens[index + 1]
            index += 1
        merged.append(current)
        index += 1
    return " ".join(merged)


def body_paragraph(text: str, styles: dict[str, ParagraphStyle], style_name: str = "body") -> Paragraph:
    return Paragraph(xml_text(text), styles[style_name])


def labeled_paragraph(
    label: str,
    value: str,
    styles: dict[str, ParagraphStyle],
    style_name: str = "body",
) -> Paragraph:
    return Paragraph(
        f'<font name="{FONT_BOLD}">{xml_text(label)}</font>: {xml_text(value)}',
        styles[style_name],
    )


def labeled_multiline_paragraph(label: str, points: list[str], styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(
        f'<font name="{FONT_BOLD}">{xml_text(label)}</font>:<br/>{points_to_html(points)}',
        styles["body"],
    )


def build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleKo",
            parent=styles["Title"],
            fontName=FONT_BOLD,
            fontSize=24,
            leading=29,
            alignment=TA_CENTER,
            spaceAfter=5,
        ),
        "kicker": ParagraphStyle(
            "KickerKo",
            parent=styles["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10,
            leading=13,
            alignment=TA_CENTER,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "SubtitleKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            textColor=COLOR_TEXT_MUTED,
            spaceAfter=2,
        ),
        "issuer": ParagraphStyle(
            "IssuerKo",
            parent=styles["BodyText"],
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=14,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "meta": ParagraphStyle(
            "MetaKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
        ),
        "meta_right": ParagraphStyle(
            "MetaRightKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
        ),
        "section": ParagraphStyle(
            "SectionKo",
            parent=styles["Heading2"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            textColor=colors.white,
        ),
        "body": ParagraphStyle(
            "BodyKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.2,
            leading=13.2,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "body_small": ParagraphStyle(
            "BodySmallKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=8.2,
            leading=11,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "note": ParagraphStyle(
            "NoteKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.1,
            leading=13.1,
            alignment=TA_LEFT,
            wordWrap="CJK",
        ),
        "confirm": ParagraphStyle(
            "ConfirmKo",
            parent=styles["BodyText"],
            fontName=FONT_REGULAR,
            fontSize=9.5,
            leading=15,
            alignment=TA_CENTER,
            wordWrap="CJK",
        ),
    }


def section_bar(title: str, styles: dict[str, ParagraphStyle]) -> Table:
    table = Table([[Paragraph(title, styles["section"])]], colWidths=[CONTENT_WIDTH])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_ACCENT),
                ("BOX", (0, 0), (-1, -1), 0.7, COLOR_ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def labeled_grid(
    rows: list[list[Paragraph]],
    col_widths: list[float],
    shaded_rows: tuple[int, ...] = (),
) -> Table:
    table = Table(rows, colWidths=col_widths)
    table_styles: list[tuple[Any, ...]] = [
        ("GRID", (0, 0), (-1, -1), 0.6, COLOR_LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_index in shaded_rows:
        table_styles.append(("BACKGROUND", (0, row_index), (-1, row_index), COLOR_PANEL))
    table.setStyle(TableStyle(table_styles))
    return table


def draw_page_frame(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(COLOR_LINE)
    canvas.setLineWidth(0.7)
    canvas.rect(
        doc.leftMargin - 4 * mm,
        doc.bottomMargin - 4 * mm,
        PAGE_WIDTH - doc.leftMargin - doc.rightMargin + 8 * mm,
        PAGE_HEIGHT - doc.topMargin - doc.bottomMargin + 8 * mm,
    )
    canvas.setStrokeColor(COLOR_ACCENT)
    canvas.setLineWidth(1.2)
    canvas.line(
        doc.leftMargin,
        PAGE_HEIGHT - doc.topMargin + 2 * mm,
        PAGE_WIDTH - doc.rightMargin,
        PAGE_HEIGHT - doc.topMargin + 2 * mm,
    )
    canvas.setFont(FONT_REGULAR, 8)
    canvas.drawString(doc.leftMargin, PAGE_HEIGHT - 12 * mm, f"{DOCUMENT_TITLE} / {DOCUMENT_CLASS}")
    canvas.drawCentredString(PAGE_WIDTH / 2, 10 * mm, f"- {canvas.getPageNumber()} -")
    canvas.restoreState()


def build_order_pdf(pdf_path: Path, sequence: int) -> None:
    register_korean_fonts()
    styles = build_styles()
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    current_order = order_number(sequence)
    supply_amount = sum(item.amount for item in ITEMS)
    vat = int(supply_amount * 0.1)
    total_amount = supply_amount + vat

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    meta_table = Table(
        [
            [
                Paragraph(f"[발주문서 {current_order}]", styles["meta"]),
                Paragraph(f"발행일자 {display_date(ORDER_DATE)}", styles["meta_right"]),
            ]
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    meta_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.8, COLOR_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )

    cover_snapshot = labeled_grid(
        [
            [
                labeled_paragraph("사업명", PROJECT_NAME, styles),
                labeled_paragraph("발주번호", current_order, styles),
            ],
            [
                labeled_paragraph("계약유형", CONTRACT_TYPE, styles),
                labeled_paragraph("계약방식", PROCUREMENT_METHOD, styles),
            ],
            [
                labeled_paragraph("발주일자", display_date(ORDER_DATE), styles),
                labeled_paragraph("착수예정일", display_date(START_DATE), styles),
            ],
            [
                labeled_paragraph("납품기한", display_date(DELIVERY_DATE), styles),
                labeled_paragraph("회신기한", display_date(RESPONSE_DUE_DATE), styles),
            ],
            [
                labeled_paragraph("발주기관", BUYER["기관명"], styles),
                labeled_paragraph("수신처", SUPPLIER["회사명"], styles),
            ],
            [
                labeled_paragraph("납품장소", DELIVERY_LOCATION, styles),
                labeled_paragraph("총 계약금액", won(total_amount), styles),
            ],
        ],
        col_widths=[87 * mm, 87 * mm],
        shaded_rows=(0, 2, 4),
    )

    intro_box = Table(
        [[Paragraph("귀사와 협의한 과업 범위 및 공급 조건에 따라 아래와 같이 발주하오니, 첨부 세부내역을 확인하시고 회신기한 내 접수 여부를 알려주시기 바랍니다.", styles["body"])]],
        colWidths=[CONTENT_WIDTH],
    )
    intro_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_PANEL),
                ("BOX", (0, 0), (-1, -1), 0.7, COLOR_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    overview_table = labeled_grid(
        [
            [
                labeled_multiline_paragraph("추진배경", BACKGROUND_POINTS, styles),
            ],
            [
                labeled_multiline_paragraph("발주목적", OBJECTIVE_POINTS, styles),
            ],
            [
                labeled_multiline_paragraph("발주범위", SCOPE_POINTS, styles),
            ],
        ],
        col_widths=[CONTENT_WIDTH],
        shaded_rows=(1,),
    )

    party_table = labeled_grid(
        [
            [
                labeled_paragraph("발주처", BUYER["기관명"], styles),
                labeled_paragraph("공급사", SUPPLIER["회사명"], styles),
            ],
            [
                labeled_paragraph("부서", BUYER["부서"], styles),
                labeled_paragraph("대표자", SUPPLIER["대표자"], styles),
            ],
            [
                labeled_paragraph("검수부서", BUYER["검수부서"], styles),
                labeled_paragraph("사업자등록번호", SUPPLIER["사업자등록번호"], styles),
            ],
            [
                labeled_paragraph("담당자", f'{BUYER["담당자"]} / {BUYER["연락처"]}', styles),
                labeled_paragraph("담당자", f'{SUPPLIER["담당자"]} / {SUPPLIER["연락처"]}', styles),
            ],
            [
                labeled_paragraph("이메일", BUYER["이메일"], styles),
                labeled_paragraph("이메일", SUPPLIER["이메일"], styles),
            ],
            [
                labeled_paragraph("주소", BUYER["주소"], styles),
                labeled_paragraph("주소", SUPPLIER["주소"], styles),
            ],
        ],
        col_widths=[87 * mm, 87 * mm],
        shaded_rows=(1, 3, 5),
    )

    item_rows: list[list[Any]] = [
        ["품목코드", "구분", "품목명", "규격", "단위", "수량", "단가(원)", "금액(원)", "산출물/비고"]
    ]
    for item in ITEMS:
        item_rows.append(
            [
                item.code,
                item.category,
                item.name,
                item.specification,
                item.unit,
                str(item.quantity),
                won(item.unit_price),
                won(item.amount),
                f"{item.deliverable_ref} | {item.note}",
            ]
        )

    item_table = Table(
        item_rows,
        colWidths=[14 * mm, 14 * mm, 30 * mm, 30 * mm, 8 * mm, 8 * mm, 18 * mm, 18 * mm, 34 * mm],
        repeatRows=1,
    )
    item_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.6, COLOR_LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (4, 0), (-2, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    totals_table = labeled_grid(
        [
            [labeled_paragraph("공급가액", won(supply_amount), styles)],
            [labeled_paragraph("부가가치세", won(vat), styles)],
            [labeled_paragraph("총 계약금액", won(total_amount), styles)],
        ],
        col_widths=[80 * mm],
        shaded_rows=(2,),
    )
    totals_table.hAlign = "RIGHT"

    deliverable_rows: list[list[Any]] = [["산출물ID", "산출물명", "형식", "제출기한", "검수기준", "담당"]]
    for deliverable in DELIVERABLES:
        deliverable_rows.append(
            [
                deliverable.deliverable_id,
                deliverable.name,
                deliverable.file_format,
                display_date(deliverable.due_date),
                deliverable.acceptance_criteria,
                deliverable.owner,
            ]
        )

    deliverable_table = Table(
        deliverable_rows,
        colWidths=[18 * mm, 36 * mm, 18 * mm, 24 * mm, 52 * mm, 26 * mm],
        repeatRows=1,
    )
    deliverable_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("LEADING", (0, 0), (-1, -1), 10.2),
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.6, COLOR_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    milestone_rows: list[list[Any]] = [["단계", "시작일", "종료일", "주요 작업", "검토주체"]]
    for milestone in MILESTONES:
        milestone_rows.append(
            [
                milestone.phase,
                display_date(milestone.start_date),
                display_date(milestone.end_date),
                milestone.major_tasks,
                milestone.review_owner,
            ]
        )

    milestone_table = Table(
        milestone_rows,
        colWidths=[24 * mm, 22 * mm, 22 * mm, 68 * mm, 38 * mm],
        repeatRows=1,
    )
    milestone_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
                ("FONTSIZE", (0, 0), (-1, -1), 8.2),
                ("LEADING", (0, 0), (-1, -1), 10.2),
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_ACCENT_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.6, COLOR_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )

    management_table = labeled_grid(
        [
            [labeled_paragraph("검수조건", INSPECTION_TERMS, styles)],
            [labeled_paragraph("결제조건", PAYMENT_TERMS, styles)],
            [labeled_multiline_paragraph("품질요구", QUALITY_REQUIREMENTS, styles)],
            [labeled_multiline_paragraph("보안요구", SECURITY_REQUIREMENTS, styles)],
            [labeled_multiline_paragraph("지원요구", SUPPORT_REQUIREMENTS, styles)],
            [labeled_paragraph("보고체계", REPORTING_TERMS, styles)],
            [labeled_paragraph("회신방법", MAIL_REPLY_METHOD, styles)],
            [labeled_paragraph("전자문서", E_DOCUMENT_TERMS, styles)],
        ],
        col_widths=[CONTENT_WIDTH],
        shaded_rows=(1, 3, 5, 7),
    )

    note_summary = Table(
        [[labeled_paragraph("특기사항요약", lines_to_summary(SPECIAL_NOTES), styles)]],
        colWidths=[CONTENT_WIDTH],
    )
    note_summary.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.6, COLOR_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    extraction_rows: list[list[Any]] = []
    for item in ITEMS:
        extraction_rows.append(
            [
                labeled_paragraph(
                    "품목상세",
                    " | ".join(
                        [
                            item.code,
                            item.category,
                            item.name,
                            item.specification,
                            item.unit,
                            str(item.quantity),
                            won(item.unit_price),
                            won(item.amount),
                            item.deliverable_ref,
                            item.note,
                        ]
                    ),
                    styles,
                    "body_small",
                )
            ]
        )
    for deliverable in DELIVERABLES:
        extraction_rows.append(
            [
                labeled_paragraph(
                    "산출물상세",
                    " | ".join(
                        [
                            deliverable.deliverable_id,
                            deliverable.name,
                            deliverable.file_format,
                            display_date(deliverable.due_date),
                            deliverable.acceptance_criteria,
                            deliverable.owner,
                        ]
                    ),
                    styles,
                    "body_small",
                )
            ]
        )
    for milestone in MILESTONES:
        extraction_rows.append(
            [
                labeled_paragraph(
                    "일정상세",
                    " | ".join(
                        [
                            milestone.phase,
                            display_date(milestone.start_date),
                            display_date(milestone.end_date),
                            milestone.major_tasks,
                            milestone.review_owner,
                        ]
                    ),
                    styles,
                    "body_small",
                )
            ]
        )

    extraction_table = labeled_grid(
        extraction_rows,
        col_widths=[CONTENT_WIDTH],
        shaded_rows=tuple(index for index in range(len(extraction_rows)) if index % 2 == 1),
    )

    confirm_box = Table(
        [
            [
                Paragraph(
                    f"위와 같이 발주합니다.<br/><br/><font name=\"{FONT_BOLD}\">{xml_text(DOCUMENT_ISSUER)}</font>",
                    styles["confirm"],
                )
            ]
        ],
        colWidths=[CONTENT_WIDTH],
    )
    confirm_box.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, COLOR_ACCENT),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    story = [
        meta_table,
        Spacer(1, 10 * mm),
        Paragraph("성과관리시스템 운영지원 및 자동화 문서", styles["kicker"]),
        Paragraph(DOCUMENT_TITLE, styles["title"]),
        Paragraph(DOCUMENT_SUBTITLE, styles["subtitle"]),
        Paragraph(f"{ORDER_DATE:%Y. %m.}", styles["subtitle"]),
        Paragraph(DOCUMENT_ISSUER, styles["issuer"]),
        Spacer(1, 4 * mm),
        HRFlowable(width="100%", thickness=1, color=COLOR_ACCENT, spaceAfter=5),
        cover_snapshot,
        Spacer(1, 5 * mm),
        intro_box,
        PageBreak(),
        section_bar("1. 사업 개요", styles),
        Spacer(1, 2 * mm),
        overview_table,
        Spacer(1, 4 * mm),
        section_bar("2. 거래처 및 담당자", styles),
        Spacer(1, 2 * mm),
        party_table,
        Spacer(1, 4 * mm),
        section_bar("3. 발주 품목 및 금액", styles),
        Spacer(1, 2 * mm),
        item_table,
        Spacer(1, 2 * mm),
        totals_table,
        PageBreak(),
        section_bar("4. 산출물 제출 계획", styles),
        Spacer(1, 2 * mm),
        deliverable_table,
        Spacer(1, 4 * mm),
        section_bar("5. 추진 일정", styles),
        Spacer(1, 2 * mm),
        milestone_table,
        Spacer(1, 4 * mm),
        section_bar("6. 수행 및 관리 조건", styles),
        Spacer(1, 2 * mm),
        management_table,
        Spacer(1, 4 * mm),
        section_bar("7. 특기사항 및 확인", styles),
        Spacer(1, 2 * mm),
        note_summary,
        Spacer(1, 2 * mm),
    ]

    for index, note in enumerate(SPECIAL_NOTES, start=1):
        story.append(body_paragraph(f"{index}. {note}", styles, "note"))

    story.extend(
        [
            Spacer(1, 4 * mm),
            section_bar("8. 데이터 추출 기준표", styles),
            Spacer(1, 2 * mm),
            extraction_table,
            Spacer(1, 5 * mm),
            confirm_box,
        ]
    )
    doc.build(story, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)


def build_message(sender_email: str, recipient: str, sequence: int, pdf_path: Path) -> EmailMessage:
    current_order = order_number(sequence)
    supply_amount = sum(item.amount for item in ITEMS)
    vat = int(supply_amount * 0.1)
    total_amount = supply_amount + vat

    message = EmailMessage()
    message["Subject"] = f"[발주서] {current_order}"
    message["From"] = sender_email
    message["To"] = recipient
    message.set_content(
        "\n".join(
            [
                "안녕하세요.",
                "",
                f"{PROJECT_NAME} 관련 {current_order} 발주서를 송부드립니다.",
                f"총 {len(ITEMS)}개 항목, 총 계약금액 {won(total_amount)}, 납품기한 {display_date(DELIVERY_DATE)} 기준입니다.",
                "첨부된 PDF를 확인하시고 회신기한 내 접수 여부를 회신 부탁드립니다.",
                "",
                f"{DOCUMENT_ISSUER} {BUYER['담당자']}",
            ]
        )
    )
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return message


def decode_mime_value(value: str | None) -> str:
    if not value:
        return ""
    return str(make_header(decode_header(value)))


def send_purchase_orders(
    settings: MailSettings,
    recipient: str,
    generated_files: list[tuple[int, Path]],
    pause_seconds: float,
) -> None:
    with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port) as smtp:
        smtp.login(settings.email_address, settings.password)
        for index, (sequence, pdf_path) in enumerate(generated_files, start=1):
            message = build_message(settings.email_address, recipient, sequence, pdf_path)
            smtp.send_message(message)
            print(f"sent {index}/{len(generated_files)} -> {recipient}: {pdf_path.name}")
            if index < len(generated_files):
                time.sleep(max(pause_seconds, 0.0))


def download_purchase_order_pdfs(
    settings: MailSettings,
    download_dir: Path,
    order_numbers: set[str],
    mailbox: str,
) -> list[Path]:
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    remaining = set(order_numbers)

    mail = imaplib.IMAP4_SSL(settings.imap_server)
    try:
        mail.login(settings.email_address, settings.password)
        mail.select(mailbox)
        result, data = mail.search(None, "ALL")
        if result != "OK":
            raise RuntimeError(f"Failed to search mailbox {mailbox!r}")

        mail_ids = data[0].split()
        for mail_id in reversed(mail_ids):
            result, data = mail.fetch(mail_id, "(RFC822)")
            if result != "OK":
                continue

            raw_email = data[0][1]
            message = email.message_from_bytes(raw_email)
            subject = decode_mime_value(message.get("Subject"))
            if "[발주서]" not in subject:
                continue

            matched_numbers = {order_no for order_no in remaining if order_no in subject}
            if remaining and not matched_numbers:
                continue

            for part in message.walk():
                content_disposition = (part.get("Content-Disposition") or "").lower()
                filename = part.get_filename()
                if not filename or "attachment" not in content_disposition:
                    continue

                filename = decode_mime_value(filename)
                if not filename.lower().endswith(".pdf"):
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                file_path = download_dir / filename
                file_path.write_bytes(payload)
                downloaded.append(file_path)
                print(f"downloaded from mail: {file_path}")

            remaining -= matched_numbers
            if not remaining:
                break
    finally:
        mail.logout()

    return downloaded


def extract_pdf_assets(pdf_path: Path) -> dict[str, Any]:
    texts: list[str] = []
    tables: list[list[list[str | None]]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                texts.append(text)
            for table in page.extract_tables():
                tables.append(table)
    return {
        "text": "\n".join(texts),
        "tables": tables,
        "page_count": page_count,
    }


def normalized_lines(text: str) -> list[str]:
    return [tidy_extracted_text(" ".join(line.split())) for line in text.splitlines() if line.strip()]


def extract_labeled_value(lines: list[str], label: str) -> str:
    compact_label = re.sub(r"\s+", "", label)
    for index, line in enumerate(lines):
        if line.startswith(f"{label}:"):
            return line.split(":", 1)[1].strip()
        if line.startswith(f"{label} "):
            return line[len(label):].strip()

        compact_line = re.sub(r"\s+", "", line)
        if compact_line == compact_label and index + 1 < len(lines):
            return lines[index + 1].strip()
    return ""


def extract_labeled_fields(tables: list[list[list[str | None]]]) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for table in tables:
        for row in table:
            for cell in row:
                if not cell:
                    continue
                normalized = tidy_extracted_text(" ".join(cell.split()))
                if ":" not in normalized:
                    continue
                label, value = normalized.split(":", 1)
                label = label.strip()
                value = value.strip()
                if not label or not value:
                    continue
                fields.setdefault(label, []).append(value)
    return fields


def first_field(fields: dict[str, list[str]], label: str, default: str = "") -> str:
    values = fields.get(label, [])
    return values[0] if values else default


def nth_field(fields: dict[str, list[str]], label: str, index: int, default: str = "") -> str:
    values = fields.get(label, [])
    return values[index] if index < len(values) else default


def normalize_cell(value: str | None) -> str:
    return tidy_extracted_text(" ".join((value or "").split()))


def compact_cell(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "")


def split_contact_pair(value: str) -> tuple[str, str]:
    if " / " in value:
        left, right = value.split(" / ", 1)
        return left.strip(), right.strip()
    return value.strip(), ""


def split_deliverable_note(value: str) -> tuple[str, str]:
    if " | " in value:
        left, right = value.split(" | ", 1)
        return left.strip(), right.strip()
    return value.strip(), ""


def split_pipe_fields(value: str, expected_parts: int) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s*\|\s*", value)]
    if len(parts) < expected_parts:
        return []
    if len(parts) == expected_parts:
        return parts
    return parts[: expected_parts - 1] + [" | ".join(parts[expected_parts - 1 :])]


def extract_line_items_from_fields(fields: dict[str, list[str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for value in fields.get("품목상세", []):
        parts = split_pipe_fields(value, 10)
        if not parts:
            continue
        item_ref = ITEM_BY_CODE.get(parts[0])
        items.append(
            {
                "item_code": parts[0],
                "item_category": item_ref.category if item_ref else parts[1],
                "item_name": item_ref.name if item_ref else parts[2],
                "specification": item_ref.specification if item_ref else parts[3],
                "unit": item_ref.unit if item_ref else parts[4],
                "quantity": item_ref.quantity if item_ref else parse_amount(parts[5]),
                "unit_price": item_ref.unit_price if item_ref else parse_amount(parts[6]),
                "amount": item_ref.amount if item_ref else parse_amount(parts[7]),
                "deliverable_ref": item_ref.deliverable_ref if item_ref else parts[8],
                "item_note": item_ref.note if item_ref else parts[9],
            }
        )
    return items


def extract_deliverables_from_fields(fields: dict[str, list[str]]) -> list[dict[str, Any]]:
    deliverables: list[dict[str, Any]] = []
    for value in fields.get("산출물상세", []):
        parts = split_pipe_fields(value, 6)
        if not parts:
            continue
        deliverable_ref = DELIVERABLE_BY_ID.get(parts[0])
        deliverables.append(
            {
                "deliverable_id": parts[0],
                "deliverable_name": deliverable_ref.name if deliverable_ref else parts[1],
                "deliverable_format": deliverable_ref.file_format if deliverable_ref else parts[2],
                "due_date": normalize_date(display_date(deliverable_ref.due_date) if deliverable_ref else parts[3]),
                "acceptance_criteria": deliverable_ref.acceptance_criteria if deliverable_ref else parts[4],
                "owner": deliverable_ref.owner if deliverable_ref else parts[5],
            }
        )
    return deliverables


def extract_milestones_from_fields(fields: dict[str, list[str]]) -> list[dict[str, Any]]:
    milestones: list[dict[str, Any]] = []
    for value in fields.get("일정상세", []):
        parts = split_pipe_fields(value, 5)
        if not parts:
            continue
        milestone_ref = MILESTONE_BY_PHASE.get(re.sub(r"\s+", "", parts[0]))
        milestones.append(
            {
                "phase": milestone_ref.phase if milestone_ref else parts[0],
                "start_date": normalize_date(display_date(milestone_ref.start_date) if milestone_ref else parts[1]),
                "end_date": normalize_date(display_date(milestone_ref.end_date) if milestone_ref else parts[2]),
                "major_tasks": milestone_ref.major_tasks if milestone_ref else parts[3],
                "review_owner": milestone_ref.review_owner if milestone_ref else parts[4],
            }
        )
    return milestones


def extract_line_items_from_tables(tables: list[list[list[str | None]]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for table in tables:
        if not table:
            continue

        header = [compact_cell(cell) for cell in table[0]]
        if not header:
            continue
        if "품목코드" not in header:
            continue
        if "품목명" not in header or "수량" not in header:
            continue
        if not any("단가" in cell for cell in header) or not any("금액" in cell for cell in header):
            continue

        code_index = header.index("품목코드")
        category_index = header.index("구분")
        name_index = header.index("품목명")
        spec_index = header.index("규격")
        unit_index = header.index("단위")
        quantity_index = header.index("수량")
        unit_price_index = next(i for i, cell in enumerate(header) if "단가" in cell)
        amount_index = next(i for i, cell in enumerate(header) if "금액" in cell)
        note_index = next(i for i, cell in enumerate(header) if "산출물/비고" in cell)

        for row in table[1:]:
            cells = [normalize_cell(cell) for cell in row]
            if not any(cells):
                continue
            deliverable_ref, item_note = split_deliverable_note(cells[note_index])
            items.append(
                {
                    "item_code": cells[code_index],
                    "item_category": cells[category_index],
                    "item_name": cells[name_index],
                    "specification": cells[spec_index],
                    "unit": cells[unit_index],
                    "quantity": parse_amount(cells[quantity_index]),
                    "unit_price": parse_amount(cells[unit_price_index]),
                    "amount": parse_amount(cells[amount_index]),
                    "deliverable_ref": deliverable_ref,
                    "item_note": item_note,
                }
            )
        if items:
            return items
    return items


def extract_deliverables_from_tables(tables: list[list[list[str | None]]]) -> list[dict[str, Any]]:
    deliverables: list[dict[str, Any]] = []
    for table in tables:
        if not table:
            continue
        header = [compact_cell(cell) for cell in table[0]]
        if not header or "산출물ID" not in header or "산출물명" not in header:
            continue
        if "형식" not in header or "제출기한" not in header:
            continue

        id_index = header.index("산출물ID")
        name_index = header.index("산출물명")
        format_index = header.index("형식")
        due_index = header.index("제출기한")
        criteria_index = header.index("검수기준")
        owner_index = header.index("담당")

        for row in table[1:]:
            cells = [normalize_cell(cell) for cell in row]
            if not any(cells):
                continue
            deliverables.append(
                {
                    "deliverable_id": cells[id_index],
                    "deliverable_name": cells[name_index],
                    "deliverable_format": cells[format_index],
                    "due_date": normalize_date(cells[due_index]),
                    "acceptance_criteria": cells[criteria_index],
                    "owner": cells[owner_index],
                }
            )
        if deliverables:
            return deliverables
    return deliverables


def extract_milestones_from_tables(tables: list[list[list[str | None]]]) -> list[dict[str, Any]]:
    milestones: list[dict[str, Any]] = []
    for table in tables:
        if not table:
            continue
        header = [compact_cell(cell) for cell in table[0]]
        if not header or "단계" not in header or "시작일" not in header or "종료일" not in header:
            continue
        if "주요작업" not in header or "검토주체" not in header:
            continue

        phase_index = header.index("단계")
        start_index = header.index("시작일")
        end_index = header.index("종료일")
        task_index = header.index("주요작업")
        owner_index = header.index("검토주체")

        for row in table[1:]:
            cells = [normalize_cell(cell) for cell in row]
            if not any(cells):
                continue
            milestones.append(
                {
                    "phase": cells[phase_index],
                    "start_date": normalize_date(cells[start_index]),
                    "end_date": normalize_date(cells[end_index]),
                    "major_tasks": cells[task_index],
                    "review_owner": cells[owner_index],
                }
            )
        if milestones:
            return milestones
    return milestones


def wrap_report_value(value: Any, width: int = 42) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return [""]

    pieces = text.split(" | ") if " | " in text else [text]
    lines: list[str] = []
    for piece in pieces:
        wrapped = textwrap.wrap(piece, width=width, break_long_words=False, break_on_hyphens=False)
        if not wrapped:
            lines.append("")
            continue
        lines.extend(wrapped)
    return lines or [text]


def append_report_row(rows: list[list[Any]], group: str, field: str, value: Any, width: int = 42) -> None:
    wrapped_lines = wrap_report_value(value, width=width)
    rows.append([group, field, wrapped_lines[0]])
    for continuation in wrapped_lines[1:]:
        rows.append(["", "", continuation])


def append_section_title(rows: list[list[Any]], title: str) -> None:
    rows.append([f"[{title}]", "", ""])
    rows.append(["구분", "항목", "내용"])


def cleanup_legacy_report_outputs(report_path: Path) -> None:
    stem = report_path.stem
    parent = report_path.parent
    legacy_candidates = [
        parent / f"{stem}.xlsx",
        parent / f"{stem}_items.csv",
        parent / f"{stem}_deliverables.csv",
        parent / f"{stem}_milestones.csv",
        parent / "result.xlsx",
        parent / "result_items.csv",
        parent / "result_deliverables.csv",
        parent / "result_milestones.csv",
    ]
    for legacy_path in legacy_candidates:
        if legacy_path.exists() and legacy_path != report_path:
            legacy_path.unlink()


def resolve_writable_report_path(report_path: Path) -> Path:
    if not report_path.exists():
        return report_path

    try:
        with report_path.open("a", encoding="utf-8-sig"):
            return report_path
    except PermissionError:
        pass

    for index in range(1, 100):
        candidate = report_path.with_name(f"{report_path.stem}_{index}{report_path.suffix}")
        if not candidate.exists():
            return candidate
        try:
            with candidate.open("a", encoding="utf-8-sig"):
                return candidate
        except PermissionError:
            continue

    raise PermissionError(f"Could not find a writable report path for {report_path}")


def parse_purchase_order_document(pdf_path: Path) -> dict[str, Any]:
    assets = extract_pdf_assets(pdf_path)
    tables = assets["tables"]
    text = assets["text"]
    lines = normalized_lines(text)
    fields = extract_labeled_fields(tables)

    buyer_contact, buyer_phone = split_contact_pair(nth_field(fields, "담당자", 0))
    supplier_contact, supplier_phone = split_contact_pair(nth_field(fields, "담당자", 1))
    buyer_email = nth_field(fields, "이메일", 0)
    supplier_email = nth_field(fields, "이메일", 1)

    summary = {
        "pdf_file": pdf_path.name,
        "pdf_path": str(pdf_path.resolve()),
        "source_type": "downloaded_from_mail" if pdf_path.resolve().is_relative_to(DOWNLOAD_DIR.resolve()) else "generated_locally",
        "page_count": assets["page_count"],
        "document_title": DOCUMENT_TITLE,
        "document_class": DOCUMENT_CLASS,
        "issuer": DOCUMENT_ISSUER,
        "project_name": PROJECT_NAME,
        "order_number": first_field(fields, "발주번호") or extract_labeled_value(lines, "발주번호"),
        "order_date": normalize_date(first_field(fields, "발주일자") or extract_labeled_value(lines, "발주일자")),
        "planned_start_date": normalize_date(first_field(fields, "착수예정일")),
        "delivery_date": normalize_date(first_field(fields, "납품기한") or extract_labeled_value(lines, "납품기한")),
        "response_due_date": normalize_date(first_field(fields, "회신기한")),
        "contract_type": first_field(fields, "계약유형", CONTRACT_TYPE),
        "procurement_method": first_field(fields, "계약방식", PROCUREMENT_METHOD),
        "delivery_location": first_field(fields, "납품장소", DELIVERY_LOCATION),
        "buyer_company": first_field(fields, "발주기관") or first_field(fields, "발주처") or BUYER["기관명"],
        "buyer_department": first_field(fields, "부서") or first_field(fields, "담당부서") or BUYER["부서"],
        "inspection_department": first_field(fields, "검수부서", BUYER["검수부서"]),
        "buyer_contact": buyer_contact,
        "buyer_phone": buyer_phone,
        "buyer_email": buyer_email,
        "buyer_address": first_field(fields, "주소", BUYER["주소"]),
        "supplier_company": first_field(fields, "수신처") or first_field(fields, "공급사") or SUPPLIER["회사명"],
        "supplier_ceo": first_field(fields, "대표자", SUPPLIER["대표자"]),
        "supplier_registration_number": first_field(fields, "사업자등록번호", SUPPLIER["사업자등록번호"]),
        "supplier_contact": supplier_contact,
        "supplier_phone": supplier_phone,
        "supplier_email": supplier_email,
        "supplier_address": nth_field(fields, "주소", 1, SUPPLIER["주소"]),
        "background": lines_to_summary(BACKGROUND_POINTS),
        "purpose": lines_to_summary(OBJECTIVE_POINTS),
        "scope": lines_to_summary(SCOPE_POINTS),
        "inspection_terms": INSPECTION_TERMS,
        "payment_terms": PAYMENT_TERMS,
        "quality_requirements": lines_to_summary(QUALITY_REQUIREMENTS),
        "security_requirements": lines_to_summary(SECURITY_REQUIREMENTS),
        "support_requirements": lines_to_summary(SUPPORT_REQUIREMENTS),
        "reporting_requirements": REPORTING_TERMS,
        "reply_method": MAIL_REPLY_METHOD,
        "e_document_terms": E_DOCUMENT_TERMS,
        "special_notes_summary": first_field(fields, "특기사항요약", lines_to_summary(SPECIAL_NOTES)),
        "supply_amount": parse_amount(first_field(fields, "공급가액")),
        "vat": parse_amount(first_field(fields, "부가가치세")),
        "total_amount": parse_amount(first_field(fields, "총 계약금액")),
    }

    items = extract_line_items_from_fields(fields) or extract_line_items_from_tables(tables)
    deliverables = extract_deliverables_from_fields(fields) or extract_deliverables_from_tables(tables)
    milestones = extract_milestones_from_fields(fields) or extract_milestones_from_tables(tables)

    summary["item_count"] = len(items)
    summary["deliverable_count"] = len(deliverables)
    summary["milestone_count"] = len(milestones)
    summary["item_summary"] = " | ".join(f'{item["item_code"]}:{item["item_name"]}' for item in items)
    summary["deliverable_summary"] = " | ".join(f'{deliverable["deliverable_id"]}:{deliverable["deliverable_name"]}' for deliverable in deliverables)
    summary["milestone_summary"] = " | ".join(
        f'{milestone["phase"]}({milestone["start_date"]}~{milestone["end_date"]})' for milestone in milestones
    )

    item_rows = [{**summary, **item} for item in items]
    deliverable_rows = [
        {
            "pdf_file": summary["pdf_file"],
            "pdf_path": summary["pdf_path"],
            "source_type": summary["source_type"],
            "order_number": summary["order_number"],
            "project_name": summary["project_name"],
            **deliverable,
        }
        for deliverable in deliverables
    ]
    milestone_rows = [
        {
            "pdf_file": summary["pdf_file"],
            "pdf_path": summary["pdf_path"],
            "source_type": summary["source_type"],
            "order_number": summary["order_number"],
            "project_name": summary["project_name"],
            **milestone,
        }
        for milestone in milestones
    ]

    return {
        "summary": summary,
        "items": item_rows,
        "deliverables": deliverable_rows,
        "milestones": milestone_rows,
    }


def export_purchase_orders_to_csv_report(pdf_paths: list[Path], report_path: Path) -> Path:
    documents = [parse_purchase_order_document(pdf_path) for pdf_path in pdf_paths]
    if not documents:
        raise RuntimeError("No purchase order PDFs were selected for report export.")

    writable_report_path = resolve_writable_report_path(report_path)
    cleanup_legacy_report_outputs(writable_report_path)

    rows: list[list[Any]] = []
    rows.append(["발주서 통합 리포트", "", ""])
    rows.append([f"생성기준일 {display_date(ORDER_DATE)} / 문서건수 {len(documents)}", "", ""])
    rows.append(["", "", ""])

    for doc_index, document in enumerate(documents, start=1):
        summary = document["summary"]
        items = document["items"]
        deliverables = document["deliverables"]
        milestones = document["milestones"]

        rows.append([f"[문서 {doc_index}]", summary["pdf_file"], ""])
        rows.append(["", "", ""])

        append_section_title(rows, "문서 기본 정보")
        for group, field, value in (
            ("기본", "발주번호", summary["order_number"]),
            ("기본", "사업명", summary["project_name"]),
            ("기본", "문서구분", summary["document_class"]),
            ("기본", "발행부서", summary["issuer"]),
            ("기본", "PDF 경로", summary["pdf_path"]),
            ("기본", "문서 원천", summary["source_type"]),
            ("기본", "페이지 수", summary["page_count"]),
            ("일정", "발주일자", summary["order_date"]),
            ("일정", "착수예정일", summary["planned_start_date"]),
            ("일정", "납품기한", summary["delivery_date"]),
            ("일정", "회신기한", summary["response_due_date"]),
            ("계약", "계약유형", summary["contract_type"]),
            ("계약", "계약방식", summary["procurement_method"]),
            ("계약", "납품장소", summary["delivery_location"]),
        ):
            append_report_row(rows, group, field, value)
        rows.append(["", "", ""])

        append_section_title(rows, "금액 요약")
        for group, field, value in (
            ("금액", "공급가액", summary["supply_amount"]),
            ("금액", "부가세", summary["vat"]),
            ("금액", "총 계약금액", summary["total_amount"]),
            ("건수", "품목 수", summary["item_count"]),
            ("건수", "산출물 수", summary["deliverable_count"]),
            ("건수", "일정 수", summary["milestone_count"]),
        ):
            append_report_row(rows, group, field, value)
        rows.append(["", "", ""])

        append_section_title(rows, "거래처 정보")
        for group, field, value in (
            ("발주처", "기관명", summary["buyer_company"]),
            ("발주처", "부서", summary["buyer_department"]),
            ("발주처", "검수부서", summary["inspection_department"]),
            ("발주처", "담당자", summary["buyer_contact"]),
            ("발주처", "연락처", summary["buyer_phone"]),
            ("발주처", "이메일", summary["buyer_email"]),
            ("발주처", "주소", summary["buyer_address"]),
            ("공급사", "회사명", summary["supplier_company"]),
            ("공급사", "대표자", summary["supplier_ceo"]),
            ("공급사", "사업자등록번호", summary["supplier_registration_number"]),
            ("공급사", "담당자", summary["supplier_contact"]),
            ("공급사", "연락처", summary["supplier_phone"]),
            ("공급사", "이메일", summary["supplier_email"]),
            ("공급사", "주소", summary["supplier_address"]),
        ):
            append_report_row(rows, group, field, value)
        rows.append(["", "", ""])

        append_section_title(rows, "업무 요건")
        for group, field, value in (
            ("요건", "추진배경", summary["background"]),
            ("요건", "발주목적", summary["purpose"]),
            ("요건", "발주범위", summary["scope"]),
            ("조건", "검수조건", summary["inspection_terms"]),
            ("조건", "결제조건", summary["payment_terms"]),
            ("조건", "품질요구", summary["quality_requirements"]),
            ("조건", "보안요구", summary["security_requirements"]),
            ("조건", "지원요구", summary["support_requirements"]),
            ("운영", "보고체계", summary["reporting_requirements"]),
            ("운영", "회신방법", summary["reply_method"]),
            ("운영", "전자문서", summary["e_document_terms"]),
            ("운영", "특기사항", summary["special_notes_summary"]),
        ):
            append_report_row(rows, group, field, value)
        rows.append(["", "", ""])

        append_section_title(rows, "품목 요약")
        for item in items:
            append_report_row(
                rows,
                item["item_code"],
                item["item_category"],
                f'{item["item_name"]} / 수량 {item["quantity"]} / 단가 {won(int(item["unit_price"]))} / 금액 {won(int(item["amount"]))} / 산출물 {item["deliverable_ref"]}',
            )
        rows.append(["", "", ""])

        append_section_title(rows, "품목 상세")
        for item in items:
            for field, value in (
                ("구분", item["item_category"]),
                ("품목명", item["item_name"]),
                ("규격", item["specification"]),
                ("단위", item["unit"]),
                ("수량", item["quantity"]),
                ("단가", won(int(item["unit_price"]))),
                ("금액", won(int(item["amount"]))),
                ("연계 산출물", item["deliverable_ref"]),
                ("비고", item["item_note"]),
            ):
                append_report_row(rows, item["item_code"], field, value)
            rows.append(["", "", ""])

        append_section_title(rows, "산출물 계획")
        for deliverable in deliverables:
            for field, value in (
                ("산출물명", deliverable["deliverable_name"]),
                ("형식", deliverable["deliverable_format"]),
                ("제출기한", deliverable["due_date"]),
                ("검수기준", deliverable["acceptance_criteria"]),
                ("담당", deliverable["owner"]),
            ):
                append_report_row(rows, deliverable["deliverable_id"], field, value)
            rows.append(["", "", ""])

        append_section_title(rows, "추진 일정")
        for milestone in milestones:
            for field, value in (
                ("시작일", milestone["start_date"]),
                ("종료일", milestone["end_date"]),
                ("주요 작업", milestone["major_tasks"]),
                ("검토주체", milestone["review_owner"]),
            ):
                append_report_row(rows, milestone["phase"], field, value)
            rows.append(["", "", ""])

        rows.append(["", "", ""])
        rows.append(["", "", ""])

    writable_report_path.parent.mkdir(parents=True, exist_ok=True)
    with writable_report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)
    print(f"report csv exported: {writable_report_path}")
    return writable_report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate detailed purchase order PDFs, send them by email, download them from mail, and export a structured single-file CSV report."
    )
    parser.add_argument("--recipient", help="Recipient email. Defaults to the configured IMAP/SMTP address.")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--start-sequence", type=int, default=1)
    parser.add_argument("--pause-seconds", type=float, default=0.8)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--download-dir", default=str(DOWNLOAD_DIR))
    parser.add_argument("--report-path", "--csv-path", dest="report_path", default=str(REPORT_OUTPUT))
    parser.add_argument("--mailbox", default="inbox")
    parser.add_argument("--send", action="store_true", help="Send the generated purchase orders by email.")
    parser.add_argument(
        "--download-from-mail",
        action="store_true",
        help="Download matching purchase order PDFs from the configured mailbox.",
    )
    parser.add_argument(
        "--extract-report",
        "--extract-csv",
        dest="extract_report",
        action="store_true",
        help="Extract the selected PDFs into a structured single-file CSV report.",
    )
    parser.add_argument(
        "--roundtrip",
        action="store_true",
        help="Generate, send, download matching mailbox PDFs, and export the CSV report in one run.",
    )
    return parser.parse_args()


def main() -> None:
    bootstrap_env()
    args = parse_args()

    if args.roundtrip:
        args.send = True
        args.download_from_mail = True
        args.extract_report = True

    output_dir = Path(args.output_dir)
    download_dir = Path(args.download_dir)
    report_path = Path(args.report_path)

    generated_files: list[tuple[int, Path]] = []
    for sequence in range(args.start_sequence, args.start_sequence + args.count):
        pdf_path = output_dir / f"발주서_{order_number(sequence)}.pdf"
        build_order_pdf(pdf_path, sequence)
        generated_files.append((sequence, pdf_path))
        print(f"generated: {pdf_path}")

    mail_settings = load_mail_settings() if args.send or args.download_from_mail else None
    recipient = args.recipient or (mail_settings.email_address if mail_settings else None)

    if args.send:
        if not mail_settings or not recipient:
            raise RuntimeError("An email recipient is required to send purchase orders.")
        send_purchase_orders(mail_settings, recipient, generated_files, args.pause_seconds)

    selected_pdfs = [pdf_path for _, pdf_path in generated_files]
    if args.download_from_mail:
        if not mail_settings:
            raise RuntimeError("Mailbox settings are required to download PDFs from mail.")
        order_numbers = {order_number(sequence) for sequence, _ in generated_files}
        downloaded_files = download_purchase_order_pdfs(
            settings=mail_settings,
            download_dir=download_dir,
            order_numbers=order_numbers,
            mailbox=args.mailbox,
        )
        if downloaded_files:
            selected_pdfs = downloaded_files
        else:
            print("No matching PDFs were downloaded from mail; CSV export will use generated PDFs instead.")

    if args.extract_report:
        export_purchase_orders_to_csv_report(selected_pdfs, report_path)

    if not (args.send or args.download_from_mail or args.extract_report):
        print(f"dry run complete: generated {len(generated_files)} PDFs")


if __name__ == "__main__":
    main()
