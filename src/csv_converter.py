from __future__ import annotations

import sys
from pathlib import Path

from app_config import BASE_DIR, DOWNLOAD_DIR


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

    # 호출 시점에만 임원 보고서 생성 모듈을 로드한다.
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    from executive_report_converter import generate_executive_xlsx_reports

    report_files = generate_executive_xlsx_reports(pdf_paths)
    if not report_files:
        raise RuntimeError("임원 보고용 XLSX 생성에 실패했습니다.")

    primary_report = report_files[0]
    report_paths_by_file = {
        files[index]: report_files[index].relative_to(BASE_DIR).as_posix()
        for index in range(min(len(files), len(report_files)))
    }
    return {
        "convertedFiles": files,
        "reportPath": primary_report.relative_to(BASE_DIR).as_posix(),
        "reportPathsByFile": report_paths_by_file,
    }
