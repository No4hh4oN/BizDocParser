import os
import argparse
from datetime import datetime
from pathlib import Path
from llm.staff_llm_evaluator import evaluate_staff_with_llm

def main():
    parser = argparse.ArgumentParser(description="BizDocParser - 인력 참여 가능성 단독 평가 도구")
    parser.add_argument("--file", type=str, help="평가할 llm_ready_rfp_context.json 파일 경로")
    parser.add_argument("--dir", type=str, help="분석 결과 폴더(outputs/YYYYMMDD_HHMMSS 등) 경로")
    parser.add_argument("--model", type=str, default="gpt-4o-mini", help="사용할 OpenAI 모델명")
    
    args = parser.parse_args()
    
    if not args.file and not args.dir:
        parser.print_help()
        return

    # 프로젝트 루트 경로 설정
    ROOT_DIR = Path(__file__).resolve().parent
    staff_pool = ROOT_DIR / "llm_inputs" / "company_staff_pool.json"
    staff_policy = ROOT_DIR / "llm_inputs" / "staff_evaluation_policy.json"

    target_files = []

    # 1. 단일 파일 모드
    if args.file:
        path = Path(args.file)
        if path.exists():
            target_files.append(path)
        else:
            print(f"[Error] 파일을 찾을 수 없습니다: {args.file}")
            return
    
    # 2. 일괄 폴더 모드 (outputs 폴더 구조 대응)
    elif args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"[Error] 폴더를 찾을 수 없습니다: {args.dir}")
            return
            
        # 하위 폴더에서 llm_ready_rfp_context.json 파일을 모두 찾음
        target_files = list(dir_path.glob("**/llm_ready_rfp_context.json"))

    if not target_files:
        print("[Error] 분석할 대상 JSON 파일을 찾지 못했습니다.")
        return

    print(f"[RunEval] 총 {len(target_files)}개의 파일을 평가합니다.")

    for json_path in target_files:
        try:
            print(f"[RunEval] 평가 시작: {json_path}")
            
            # 결과물은 입력 JSON 파일이 있는 동일한 폴더에 저장
            output_dir = json_path.parent
            
            # 파일명에 포함할 타임스탬프 및 모델명 정제
            eval_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = args.model.replace("-", "_").replace(".", "_")
            base_name = f"staff_participation_{model_name}_{eval_time}"

            evaluate_staff_with_llm(
                rfp_json_path=json_path,
                staff_pool_json_path=staff_pool,
                staff_policy_json_path=staff_policy,
                output_json_path=output_dir / f"{base_name}.json",
                output_md_path=output_dir / f"{base_name}.md",
                output_xlsx_path=output_dir / f"{base_name}.xlsx",
                model=args.model,
            )
            print(f"[RunEval] 완료: {output_dir.name}")
            
        except Exception as e:
            print(f"[Error] {json_path} 평가 중 오류 발생: {e}")

    print("\n[RunEval] 모든 평가 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()
