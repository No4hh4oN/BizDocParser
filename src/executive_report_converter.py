from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app_config import BASE_DIR


def _build_summary_frames(data: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """RFP 분석 결과에서 임원 보고용 XLSX 생성에 필요한 데이터프레임을 구성한다."""
    info = data.get("project_info", {})
    summary_rows = []
    order = [
        "project_name",
        "agency",
        "budget",
        "project_period",
        "contract_method",
        "submission_deadline",
        "evaluation_ratio",
    ]

    for field in order:
        detail = info.get(field, {"value": "not_found", "source_section": "not_found"})
        summary_rows.append(
            {
                "field": field,
                "value": detail.get("value", "not_found"),
                "source_section": detail.get("source_section", "not_found"),
            }
        )

    df_info = pd.DataFrame(summary_rows)
    df_stats = pd.DataFrame(data.get("requirements", {}).get("statistics", []))
    included_scope = data.get("scope", {}).get("included_scope", [])
    return df_info, df_stats, included_scope


def _save_supporting_outputs(target_dir: Path, analysis_data: dict[str, Any], llm_context: str) -> None:
    """main.py와 동일한 형태의 보조 산출물을 저장한다."""
    info = analysis_data.get("project_info", {})
    summary_rows = []
    order = [
        "project_name",
        "agency",
        "budget",
        "project_period",
        "contract_method",
        "submission_deadline",
        "evaluation_ratio",
    ]
    for field in order:
        detail = info.get(field, {"value": "not_found", "source_section": "not_found"})
        summary_rows.append(
            {
                "field": field,
                "value": detail.get("value", "not_found"),
                "source_section": detail.get("source_section", "not_found"),
            }
        )

    df_info = pd.DataFrame(summary_rows)
    df_info.to_csv(target_dir / "project_summary.csv", index=False, encoding="utf-8-sig")

    req_stats = analysis_data.get("requirements", {}).get("statistics", [])
    df_stats = pd.DataFrame(req_stats) if req_stats else pd.DataFrame()
    if not df_stats.empty:
        df_stats.to_csv(target_dir / "requirement_statistics.csv", index=False, encoding="utf-8-sig")

    req_details = analysis_data.get("requirements", {}).get("details", [])
    df_details = pd.DataFrame(req_details) if req_details else pd.DataFrame()
    if not df_details.empty:
        df_details.to_csv(target_dir / "requirements_detail.csv", index=False, encoding="utf-8-sig")

    (target_dir / "llm_ready_rfp_context.json").write_text(llm_context, encoding="utf-8")


def generate_executive_xlsx_reports(pdf_paths: list[Path]) -> list[Path]:
    """
    다운로드된 PDF 목록을 받아 임원 보고용 XLSX만 생성한다.
    반환값은 생성된 XLSX 절대경로 목록이다.
    """
    if not pdf_paths:
        return []

    # 지연 import: 호출 시점에만 파이프라인을 로드하여 의존성 충돌을 줄인다.
    from rfp_analysis.pipeline import RfpAnalysisPipeline

    pipeline = RfpAnalysisPipeline()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = BASE_DIR / "outputs" / "executive_reports" / timestamp
    output_root.mkdir(parents=True, exist_ok=True)

    output_files: list[Path] = []
    for pdf_path in pdf_paths:
        result = pipeline.run(str(pdf_path))
        df_info, df_stats, included_scope = _build_summary_frames(result["data"])

        target_dir = output_root / pdf_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)
        report_path = target_dir / "executive_summary.xlsx"

        _save_supporting_outputs(
            target_dir=target_dir,
            analysis_data=result["data"],
            llm_context=result["reports"]["llm_ready_rfp_context"],
        )

        pipeline.summary_builder.build_xlsx(
            df_info=df_info,
            df_stats=df_stats,
            included_scope=included_scope,
            output_path=str(report_path),
        )
        output_files.append(report_path)

    return output_files
