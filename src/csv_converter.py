from __future__ import annotations

from pathlib import Path

from app_config import BASE_DIR, DOWNLOAD_DIR, REPORT_OUTPUT
from send_purchase_orders import export_purchase_orders_to_csv_report


def resolve_downloaded_pdf(relative_path: str) -> Path:
    candidate = (BASE_DIR / relative_path).resolve()
    download_root = DOWNLOAD_DIR.resolve()
    if not candidate.is_relative_to(download_root):
        raise RuntimeError(f"다운로드 폴더 밖의 파일은 변환할 수 없습니다: {relative_path}")
    if candidate.suffix.lower() != ".pdf":
        raise RuntimeError(f"PDF 파일만 변환할 수 있습니다: {relative_path}")
    if not candidate.exists():
        raise RuntimeError(f"파일을 찾을 수 없습니다: {relative_path}")
    return candidate


def convert_pdfs_to_csv(files: list[str]) -> dict[str, object]:
    if not files:
        raise RuntimeError("CSV로 변환할 PDF를 선택하세요.")

    pdf_paths = [resolve_downloaded_pdf(file_path) for file_path in files]
    report_path = export_purchase_orders_to_csv_report(pdf_paths, REPORT_OUTPUT)
    return {
        "convertedFiles": files,
        "reportPath": report_path.relative_to(BASE_DIR).as_posix(),
    }
