"""
BizDocParser 메인 실행 파일 (CLI Entry Point)

이 스크립트는 프로젝트의 통합 진입점으로, RFP 분석 기능을 명령행 인터페이스(CLI)를 통해 제공합니다.

주요 기능:
1. 명령행 인자 처리 (파일 분석, 결과 경로 지정 등)
2. 실행 시점별 타임스탬프 기반 출력 폴더 생성 (예: outputs/20260429_1215/)
3. RFP 분석 파이프라인 실행 및 결과물(CSV, MD, JSON) 저장
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

# src 폴더를 패키지 경로에 추가 (학습용 주석: 하부 폴더의 모듈을 root에서 참조하기 위함)
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from rfp_analysis.pipeline import RfpAnalysisPipeline
from llm.staff_llm_evaluator import evaluate_staff_with_llm

def create_output_folder() -> Path:
    """
    실행 시점의 날짜와 시간을 기반으로 독립된 결과 폴더를 생성합니다.
    학습용 주석: 사용자 요청에 따라 'YYYYMMDD_HHMM' 형식을 사용하여 이력을 관리합니다.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = ROOT_DIR / "outputs" / timestamp
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path

def save_csv_results(output_dir: Path, data: dict) -> tuple:
    """
    분석 데이터를 CSV로 저장하고, 엑셀 보고서용 데이터프레임들을 반환합니다.
    """
    # 1. project_summary.csv
    info = data["project_info"]
    summary_rows = []
    order = ["project_name", "agency", "budget", "project_period", "contract_method", "submission_deadline", "evaluation_ratio"]
    for field in order:
        detail = info.get(field, {"value": "not_found", "source_section": "not_found"})
        summary_rows.append({
            "field": field,
            "value": detail["value"],
            "source_section": detail["source_section"]
        })
    df_info = pd.DataFrame(summary_rows)
    df_info.to_csv(output_dir / "project_summary.csv", index=False, encoding="utf-8-sig")

    # 2. requirement_statistics.csv
    req_stats = data["requirements"]["statistics"]
    df_stats = pd.DataFrame(req_stats) if req_stats else pd.DataFrame()
    if not df_stats.empty:
        df_stats.to_csv(output_dir / "requirement_statistics.csv", index=False, encoding="utf-8-sig")

    # 3. requirements_detail.csv
    req_details = data["requirements"]["details"]
    df_details = pd.DataFrame(req_details) if req_details else pd.DataFrame()
    if not df_details.empty:
        df_details.to_csv(output_dir / "requirements_detail.csv", index=False, encoding="utf-8-sig")

    return df_info, df_stats, df_details

def main():
    """
    메인 실행 로직
    """
    parser = argparse.ArgumentParser(description="BizDocParser - RFP Analysis Tool")
    parser.add_argument("--analyze", type=str, help="분석할 RFP PDF 파일 경로")
    parser.add_argument("--dir", type=str, help="분석할 PDF 파일들이 포함된 디렉토리 경로")
    parser.add_argument("--staff-eval", action="store_true", help="직원 참여 가능성 LLM 평가 실행")
    parser.add_argument(
        "--staff-pool",
        type=str,
        default=str(ROOT_DIR / "llm_inputs" / "company_staff_pool.json"),
        help="회사 직원 풀 JSON 경로",
    )
    parser.add_argument(
        "--staff-policy",
        type=str,
        default=str(ROOT_DIR / "llm_inputs" / "staff_evaluation_policy.json"),
        help="직급별 투입 제한/라벨 정책 JSON 경로",
    )
    parser.add_argument(
        "--staff-model",
        type=str,
        default=os.getenv("OPENAI_MODEL", "gpt-5.5"),
        help="직원 평가에 사용할 OpenAI 모델명",
    )
    
    args = parser.parse_args()

    if not args.analyze and not args.dir:
        parser.print_help()
        return

    # 파이프라인 초기화
    pipeline = RfpAnalysisPipeline()
    
    # 분석 대상 파일 목록 확정
    target_files = []
    if args.analyze:
        target_files.append(args.analyze)
    elif args.dir:
        target_files.extend(list(Path(args.dir).glob("*.pdf")))

    if not target_files:
        print("분석할 대상 파일을 찾지 못했습니다.")
        return

    # 결과 폴더 생성
    output_dir = create_output_folder()
    print(f"[Main] 결과 저장 경로: {output_dir}")

    for file_path in target_files:
        try:
            # 파이프라인 실행
            result = pipeline.run(file_path)
            
            # 파일별 서브 폴더 생성 (여러 파일 분석 시 대비)
            file_stem = Path(file_path).stem
            file_output_dir = output_dir / file_stem
            file_output_dir.mkdir(exist_ok=True)

            # 1. CSV 결과 저장 및 데이터프레임 획득
            df_info, df_stats, df_details = save_csv_results(file_output_dir, result["data"])
            
            # 2. 획득한 데이터프레임과 범위 데이터를 활용하여 Excel 보고서 생성 (골든 샘플 양식)
            included_scope = result["data"]["scope"].get("included_scope", [])
            pipeline.summary_builder.build_xlsx(df_info, df_stats, included_scope, str(file_output_dir / "executive_summary.xlsx"))
            
            # 3. JSON 컨텍스트 저장
            llm_context_path = file_output_dir / "llm_ready_rfp_context.json"
            llm_context_path.write_text(result["reports"]["llm_ready_rfp_context"], encoding="utf-8")

                # 4. 직원 참여 가능성 LLM 평가 (옵션)
            if args.staff_eval:
                staff_pool_path = Path(args.staff_pool)
                staff_policy_path = Path(args.staff_policy)
                if not staff_pool_path.exists():
                    raise FileNotFoundError(f"직원 풀 JSON 파일을 찾을 수 없습니다: {staff_pool_path}")
                if not staff_policy_path.exists():
                    raise FileNotFoundError(f"직원 정책 JSON 파일을 찾을 수 없습니다: {staff_policy_path}")

                # 파일명에 포함할 타임스탬프 및 모델명 정제
                eval_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                model_name = args.staff_model.replace("-", "_").replace(".", "_")
                base_name = f"staff_participation_{model_name}_{eval_time}"

                evaluate_staff_with_llm(
                    rfp_json_path=llm_context_path,
                    staff_pool_json_path=staff_pool_path,
                    staff_policy_json_path=staff_policy_path,
                    output_json_path=file_output_dir / f"{base_name}.json",
                    output_md_path=file_output_dir / f"{base_name}.md",
                    output_xlsx_path=file_output_dir / f"{base_name}.xlsx",
                    model=args.staff_model,
                )
            
            print(f"[Main] 완료: {file_stem}")

        except Exception as e:
            print(f"[Error] {file_path} 분석 중 오류 발생: {e}")

    print("\n[Main] 모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()
