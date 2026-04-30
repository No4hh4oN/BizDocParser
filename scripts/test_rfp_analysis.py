"""
RFP 분석 기능 통합 검증 스크립트 (Verification Script)

이 스크립트는 구현된 RFP 분석 파이프라인과 CLI 도구가 정상적으로 작동하는지 확인합니다.
샘플 PDF를 대상으로 분석을 실행하고, 결과 폴더 및 파일들이 올바르게 생성되었는지 체크합니다.
"""

import os
import sys
import subprocess
from pathlib import Path

# 루트 경로를 시스템 경로에 추가
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

def run_verification():
    """
    RFP 분석 검증 프로세스를 실행합니다.
    """
    print("=== RFP 분석 기능 검증 시작 ===")
    
    # 1. 샘플 PDF 파일 확인
    sample_pdf = ROOT_DIR / "rfp_dummy_pdf" / "rfp_genai_civil_service_chatbot.pdf"
    if not sample_pdf.exists():
        print(f"[실패] 샘플 PDF를 찾을 수 없습니다: {sample_pdf}")
        return

    # 2. main.py 실행 (CLI 검증)
    # 학습용 주석: subprocess를 사용하여 실제 사용자와 동일한 환경에서 명령어를 실행합니다.
    print(f"\n[Step 1] main.py 분석 실행: {sample_pdf.name}")
    try:
        result = subprocess.run(
            [sys.executable, "main.py", "--analyze", str(sample_pdf)],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            check=True
        )
        print("[성공] main.py 실행 완료")
        # print(result.stdout) # 필요 시 출력 확인
    except subprocess.CalledProcessError as e:
        print(f"[실패] main.py 실행 중 오류 발생: {e}")
        print(f"Error Output: {e.stderr}")
        return

    # 3. 결과 파일 존재 확인
    # 가장 최근에 생성된 outputs 하위 폴더 탐색
    print("\n[Step 2] 결과 산출물 확인")
    outputs_root = ROOT_DIR / "outputs"
    if not outputs_root.exists():
        print("[실패] outputs 폴더가 생성되지 않았습니다.")
        return

    # 타임스탬프 폴더 중 가장 최근 것 선택
    subdirs = sorted([d for d in outputs_root.iterdir() if d.is_dir()], key=os.path.getmtime, reverse=True)
    if not subdirs:
        print("[실패] 타임스탬프 결과 폴더를 찾을 수 없습니다.")
        return

    latest_output_dir = subdirs[0] / sample_pdf.stem
    print(f"최신 결과 폴더: {latest_output_dir}")

    expected_files = [
        "executive_summary.md",
        "llm_ready_rfp_context.json",
        "project_summary.csv",
        "requirements_detail.csv",
        "requirement_statistics.csv",
        "risk_candidates.csv"
    ]

    for file_name in expected_files:
        file_path = latest_output_dir / file_name
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"[확인] {file_name} 생성됨 ({size} bytes)")
        else:
            print(f"[실패] {file_name} 파일이 누락되었습니다.")

    print("\n=== 검증 프로세스 완료 ===")

if __name__ == "__main__":
    run_verification()
