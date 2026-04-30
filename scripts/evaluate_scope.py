"""
수행 범위 추출 품질 평가 스크립트

평가 지표:
  - noise_rate   : 출력 bullet 중 노이즈 패턴 포함 비율 (0에 가까울수록 좋음)
  - coverage     : 7개 카테고리(운영/기능/데이터/보안/품질/연계/교육) 중 포함된 수
  - groundedness : 출력 문장과 원문 후보군의 최대 유사도 평균 (1에 가까울수록 좋음)
  - item_count   : 출력 bullet 수

안정성 측정:
  - 동일 PDF 10회 반복 시 item_count 표준편차
  - 10회 run 간 자카드 유사도 평균
"""

import sys
import os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import re
import math
from pathlib import Path
from typing import List, Dict, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(ROOT_DIR / "src"))

from rfp_analysis.pipeline import RfpAnalysisPipeline
from rfp_analysis.extractors.scope_extractor import ScopeExtractor


# ------------------------------------------------------------------ #
# 지표 계산
# ------------------------------------------------------------------ #

CATEGORIES = [
    ("운영지원", ["운영", "점검", "장애", "문의", "보고", "기술지원", "유지관리", "SLA"]),
    ("핵심기능", ["기능", "고도화", "개선", "개설", "신청", "승인", "출결", "성과", "챗봇", "자동화", "대시보드"]),
    ("데이터",   ["데이터", "정합성", "표준화", "수집", "전처리", "저장", "이력", "백업", "복구"]),
    ("보안",     ["보안", "권한", "인증", "개인정보", "로그", "접근제어", "마스킹", "취약점"]),
    ("품질",     ["품질", "테스트", "성능", "검증", "오류", "환각"]),
    ("연계",     ["연계", "통합", "포털", "API", "이관", "알림", "인터페이스"]),
    ("교육",     ["교육", "매뉴얼", "안정화", "운영전환"]),
]

NOISE_REGEXES = [
    r"(SFR|DAR|SER|QUR|PMR|PSR|MMY)-\d+",
    r"^요구사항\s*설명",
    r"^더미\s*RFP",
    r"^제안사(는|가|이)?",
    r"^발주기관(은|이)?",
]
NOISE_KEYWORDS = [
    "입찰", "제안유의", "보완자료", "제출서류", "공고사항",
    "범위 외", "포함하지 않", "허위", "과장",
    "하여야 한다", "하여야한다", "해야 한다", "하여야합니다",
    "작성하여야", "제시하여야", "수행하여야", "포함하여야", "명시하여야",
    "부족", "미흡", "문제점", "필요가 있음", "지연됨",
    "사업수행계획서", "운영지원계획서", "명세서", "관리대장", "정의서",
    "제안요청서", "교육계획서", "발주기관 승인 후", "본 사업은",
]


def _similarity(a: str, b: str) -> float:
    tokens_a = set(re.findall(r"[가-힣A-Za-z0-9]+", a))
    tokens_b = set(re.findall(r"[가-힣A-Za-z0-9]+", b))
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _is_noise(line: str) -> bool:
    for p in NOISE_REGEXES:
        if re.search(p, line):
            return True
    return any(kw in line for kw in NOISE_KEYWORDS)


def compute_noise_rate(lines: List[str]) -> float:
    if not lines:
        return 0.0
    return sum(1 for ln in lines if _is_noise(ln)) / len(lines)


def compute_coverage(lines: List[str]) -> int:
    covered = 0
    for _name, kws in CATEGORIES:
        if any(any(kw in ln for kw in kws) for ln in lines):
            covered += 1
    return covered


def compute_groundedness(output_lines: List[str], raw_candidates: List[str]) -> float:
    if not output_lines:
        return 0.0
    if not raw_candidates:
        return 0.0
    scores = [
        max((_similarity(out, cand) for cand in raw_candidates), default=0.0)
        for out in output_lines
    ]
    return sum(scores) / len(scores)


def _run_single(pipeline: RfpAnalysisPipeline, pdf_path: Path) -> Dict[str, Any]:
    result = pipeline.run(str(pdf_path))
    scope_ext: ScopeExtractor = pipeline.scope_extractor
    output = result["data"]["scope"].get("included_scope", [])
    raw_cands = scope_ext._last_raw_candidates

    return {
        "output": output,
        "raw_candidates": raw_cands,
        "noise_rate": compute_noise_rate(output),
        "coverage": compute_coverage(output),
        "groundedness": compute_groundedness(output, raw_cands),
        "item_count": len(output),
    }


# ------------------------------------------------------------------ #
# 안정성 계산
# ------------------------------------------------------------------ #

def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _jaccard_sets(a: List[str], b: List[str]) -> float:
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def compute_stability(runs: List[Dict]) -> Dict[str, float]:
    counts = [r["item_count"] for r in runs]
    pairwise = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            pairwise.append(_jaccard_sets(runs[i]["output"], runs[j]["output"]))
    return {
        "item_count_stddev": _stddev([float(c) for c in counts]),
        "pairwise_jaccard_mean": sum(pairwise) / len(pairwise) if pairwise else 0.0,
    }


# ------------------------------------------------------------------ #
# 리포트 출력
# ------------------------------------------------------------------ #

def _hbar(value: float, width: int = 20, full: float = 1.0) -> str:
    filled = int(round(value / full * width))
    return "█" * filled + "░" * (width - filled)


def print_single_report(pdf_name: str, metrics: Dict, output: List[str]) -> None:
    print(f"\n{'='*60}")
    print(f"  PDF : {pdf_name}")
    print(f"{'='*60}")
    print(f"  항목 수      : {metrics['item_count']}개  (허용: 6~8)")
    print(f"  노이즈율     : {metrics['noise_rate']:.3f}  {_hbar(metrics['noise_rate'])}")
    print(f"  커버리지     : {metrics['coverage']}/7")
    print(f"  근거성       : {metrics['groundedness']:.3f}  {_hbar(metrics['groundedness'])}")
    print(f"\n  [주요 수행 범위]")
    for i, ln in enumerate(output, 1):
        print(f"  {i}. {ln}")


def print_stability_report(pdf_name: str, runs: List[Dict], stab: Dict) -> None:
    print(f"\n  [{pdf_name}] 안정성 (10회)")
    print(f"    item_count 표준편차   : {stab['item_count_stddev']:.3f}")
    print(f"    pairwise jaccard 평균 : {stab['pairwise_jaccard_mean']:.3f}")
    print(f"    run별 항목 수         : {[r['item_count'] for r in runs]}")


def print_summary_table(single_results: List[Tuple[str, Dict]]) -> None:
    print(f"\n{'='*60}")
    print("  품질 지표 요약 테이블")
    print(f"{'='*60}")
    header = f"  {'PDF명':<32} {'항목':>4} {'노이즈':>7} {'커버':>5} {'근거성':>7}"
    print(header)
    print("  " + "-" * 58)
    for name, m in single_results:
        print(
            f"  {name:<32} {m['item_count']:>4} "
            f"{m['noise_rate']:>7.3f} {m['coverage']:>5} {m['groundedness']:>7.3f}"
        )


# ------------------------------------------------------------------ #
# main
# ------------------------------------------------------------------ #

def main() -> None:
    pdf_dir = ROOT_DIR / "rfp_dummy_pdf"
    pdfs = sorted(pdf_dir.glob("*.pdf"))

    if not pdfs:
        print(f"[Error] rfp_dummy_pdf 폴더에 PDF 파일이 없습니다: {pdf_dir}")
        return

    pipeline = RfpAnalysisPipeline()

    # ── 1. 1회 실행 품질 평가 ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  [Phase 1] 5개 더미 PDF - 1회 실행 품질 평가")
    print("=" * 60)

    single_results: List[Tuple[str, Dict]] = []
    for pdf in pdfs:
        print(f"\n  >> {pdf.name} 분석 중...")
        metrics = _run_single(pipeline, pdf)
        single_results.append((pdf.stem, metrics))
        print_single_report(pdf.stem, metrics, metrics["output"])

    print_summary_table(single_results)

    # ── 2. 10회 배치 반복 안정성 평가 ────────────────────────────────
    REPEAT = 10
    print(f"\n\n{'='*60}")
    print(f"  [Phase 2] 5개 더미 PDF - {REPEAT}회 반복 안정성 평가")
    print("=" * 60)

    stability_results: List[Tuple[str, Dict, List[Dict]]] = []
    for pdf in pdfs:
        print(f"\n  >> {pdf.name} × {REPEAT}회 실행 중...")
        runs = []
        for i in range(REPEAT):
            m = _run_single(pipeline, pdf)
            runs.append(m)
            print(f"     run {i+1:2d}: items={m['item_count']}  noise={m['noise_rate']:.3f}"
                  f"  cov={m['coverage']}  grnd={m['groundedness']:.3f}")
        stab = compute_stability(runs)
        stability_results.append((pdf.stem, stab, runs))
        print_stability_report(pdf.stem, runs, stab)

    # ── 3. 안정성 요약 ───────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  안정성 요약 테이블")
    print(f"{'='*60}")
    print(f"  {'PDF명':<32} {'stddev':>8} {'jaccard':>9}")
    print("  " + "-" * 52)
    for name, stab, _ in stability_results:
        print(f"  {name:<32} {stab['item_count_stddev']:>8.3f} {stab['pairwise_jaccard_mean']:>9.3f}")

    print("\n[평가 완료]")


if __name__ == "__main__":
    main()
