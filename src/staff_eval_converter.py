from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from app_config import BASE_DIR
from csv_converter import resolve_downloaded_pdf

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from llm.staff_llm_evaluator import evaluate_staff_with_llm


def evaluate_staff_participation_for_files(files: list[str], model: str | None = None) -> dict[str, object]:
    if not files:
        raise RuntimeError("평가할 PDF를 선택하세요.")

    from rfp_analysis.pipeline import RfpAnalysisPipeline

    pipeline = RfpAnalysisPipeline()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = BASE_DIR / "outputs" / "staff_evaluations" / timestamp
    output_root.mkdir(parents=True, exist_ok=True)

    staff_pool_path = BASE_DIR / "llm_inputs" / "company_staff_pool.json"
    staff_policy_path = BASE_DIR / "llm_inputs" / "staff_evaluation_policy.json"
    if not staff_pool_path.exists() or not staff_policy_path.exists():
        raise RuntimeError("직원 풀/정책 파일을 찾을 수 없습니다.")

    resolved_files = [resolve_downloaded_pdf(file_path) for file_path in files]
    model_name = (model or "gpt-5-mini").replace("-", "_").replace(".", "_")

    xlsx_by_file: dict[str, str] = {}
    json_by_file: dict[str, str] = {}
    md_by_file: dict[str, str] = {}
    result_by_file: dict[str, dict[str, object]] = {}

    for source_id, pdf_path in zip(files, resolved_files):
        result = pipeline.run(str(pdf_path))

        target_dir = output_root / pdf_path.stem
        target_dir.mkdir(parents=True, exist_ok=True)

        llm_context_path = target_dir / "llm_ready_rfp_context.json"
        llm_context_path.write_text(result["reports"]["llm_ready_rfp_context"], encoding="utf-8")

        base_name = f"staff_participation_{model_name}_{timestamp}"
        out_json = target_dir / f"{base_name}.json"
        out_md = target_dir / f"{base_name}.md"
        out_xlsx = target_dir / f"{base_name}.xlsx"

        result_obj = evaluate_staff_with_llm(
            rfp_json_path=llm_context_path,
            staff_pool_json_path=staff_pool_path,
            staff_policy_json_path=staff_policy_path,
            output_json_path=out_json,
            output_md_path=out_md,
            output_xlsx_path=out_xlsx,
            model=model,
        )

        xlsx_by_file[source_id] = out_xlsx.relative_to(BASE_DIR).as_posix()
        json_by_file[source_id] = out_json.relative_to(BASE_DIR).as_posix()
        md_by_file[source_id] = out_md.relative_to(BASE_DIR).as_posix()
        result_by_file[source_id] = result_obj

    first_xlsx = next(iter(xlsx_by_file.values()))
    return {
        "evaluatedFiles": files,
        "resultPath": first_xlsx,
        "resultPathsByFile": xlsx_by_file,
        "resultJsonByFile": json_by_file,
        "resultMdByFile": md_by_file,
        "resultByFile": result_by_file,
    }
