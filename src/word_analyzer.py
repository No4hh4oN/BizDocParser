from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from csv_converter import resolve_downloaded_pdf
from send_purchase_orders import extract_pdf_assets

# Kiwi 형태소 분석기 연동 (학습용 주석: 정규식보다 정확한 한국어 분석을 위해 선택적으로 사용합니다)
try:
    from kiwipiepy import Kiwi
    kiwi = Kiwi()
    KIWI_AVAILABLE = True
except ImportError:
    KIWI_AVAILABLE = False


STOPWORDS = {
    # General particles / connective words
    "그리고",
    "또는",
    "대한",
    "기준",
    "관련",
    "아래",
    "위와",
    "같이",
    "통해",
    "경우",
    "이내",
    "발주서",
    "발주",
    "문서",
    "확인",
    "제출",
    "포함",
    "합니다",
    "있습니다",
    "수",
    "및",
    "등",
    "하는",
    "하여",
    "하며",
    "하고",
    "해야",
    "한다",
    "있다",
    "있는",
    "있어야",
    "따라",
    "위해",
    "통한",
    "대해",
    "각",
    "본",
    "해당",
    "전반",
    "일부",
    "전체",
    "내역",
    "사항",
    "한다는",
    # RFP / document boilerplate
    "rfp",
    "더미",
    "제안",
    "제안서",
    "제안요청",
    "제안요청서",
    "제안사가",
    "제안사는",
    "제시",
    "제시하여야",
    "작성",
    "작성하여야",
    "제출물",
    "산출물",
    "산출정보",
    "요구",
    "요구사항",
    "요구사항명",
    "항목",
    "구분",
    "내용",
    "설명",
    "기준서",
    "명세서",
    "기능명세서",
    "테스트결과서",
    "보고서",
    "매뉴얼",
    "문서는",
    "문서화",
    "키워드",
    "id",
    "sfr",
    "dar",
    "ser",
    "qur",
    "pmr",
    "psr",
    # Generic project / management terms that dominated all five RFPs
    "사업",
    "시스템",
    "관리",
    "운영",
    "기능",
    "방안",
    "방안을",
    "주요",
    "단계",
    "절차",
    "절차를",
    "범위",
    "기반",
    "수행",
    "처리",
    "지원",
    "서비스",
    "담당자",
    "기관",
    "업무",
    "계약",
    "기간",
    "일정",
    "현황",
    "조회",
    "입력",
    "결과",
    "검증",
    "테스트",
    "품질",
    "품질관리",
    "개선",
    "변경",
    "설계",
    "정책",
    "이력",
    "로그",
    "오류",
    "누락",
    "실패",
    "지연",
    "리스크",
    "위험",
    "대응",
    "조치",
    "안정화",
    "보관",
    "가상",
    "it",
    # Second pass after reviewing the five dummy RFP PDFs
    "분석",
    "데이터",
    "사용자",
    "보안",
    "장애",
    "관리자",
    "개인정보",
    "점검",
    "승인",
    "권한",
    "문의",
    "이슈",
    "대시보드",
    "보호",
    "마스킹",
    "생성",
    "내부",
    "연계",
    "샘플",
    "공공",
    "세부",
    "미흡",
    "목적의",
    "지정",
    "전략",
    "전환",
    "현행",
    "보안관리",
    "성능",
    "종료",
    "가능",
    "기술능력평가",
    "접근",
    "대상",
    "결과를",
    "파일",
    "다운로드",
    "포함하여야",
    "인력",
    "양식",
    "결과서",
    "정보",
    "추진",
    "관리할",
    "기능을",
    "부서",
    "기준을",
    "개발",
    "표준화",
    "외부",
    "중복",
    "착수",
    "저하",
    "이해도",
    "가격평가",
    "월간",
    "일정관리",
    "응답",
    "보고",
    "계정",
    "발주기관",
    "개요",
    "자동",
    "유형",
    "검수",
    "기준에",
    "불일치",
    "필요",
    "실제",
    "목적",
    "알림",
    "상태",
    "제공하여야",
    "화면설계서",
    "접속",
    "검색",
    "재발",
    "관리하여야",
    # RFP phrasing / evaluation boilerplate left after the second pass
    "기대효과",
    "포함하여",
    "구축",
    "기존",
    "교육자료",
    "권한관리",
    "접근성",
    "별도",
    "가능한",
    "표준",
    "기준으로",
    "여부",
    "증가",
    "정기",
    "위한",
    "역량",
    "사업수행계획서",
    "제한",
    "수정",
    "요구사항별",
    "배점",
    "방안은",
    "등록",
    "로그관리",
    "문제",
    "행위",
    "안정화보고서",
    "반복",
    "의사결정",
    "부족",
    "제출하여야",
    "체계를",
    "사업의",
    "합계",
    "제외",
    "이력을",
    "여부를",
    "현황을",
    "보안관리계획서",
    "형식",
    "있도록",
    "수행하여야",
    "명확히",
    "단계별",
    "투입",
    "적용하여야",
    "샘플입니다",
    "제안요청서입니다",
    "시스템은",
    "the",
    "and",
    "for",
    "with",
}


def tokenize_text(text: str) -> list[str]:
    """
    텍스트를 토큰화합니다. Kiwi가 사용 가능하면 Kiwi를 사용하고, 그렇지 않으면 정규식을 사용합니다.
    학습용 주석: 하위 호환성과 환경 유연성을 위해 두 가지 방식을 모두 지원합니다.
    """
    if KIWI_AVAILABLE:
        # Kiwi를 사용한 형태소 분석 및 명사 추출
        tokens = []
        result = kiwi.tokenize(text)
        for token in result:
            # 명사(NNG, NNP)와 영문(SL) 위주로 추출
            if token.tag in {"NNG", "NNP", "SL"} and len(token.form) >= 2:
                word = token.form.lower() if token.tag == "SL" else token.form
                if word not in STOPWORDS:
                    tokens.append(word)
        return tokens

    # 기존 정규식 기반 토큰화 (Kiwi가 없을 때를 대비한 Fallback)
    tokens: list[str] = []
    for raw_token in re.findall(r"[가-힣A-Za-z0-9]+", text):
        token = raw_token.lower() if raw_token.isascii() else raw_token
        if len(token) < 2 or token in STOPWORDS:
            continue
        if token.isdigit():
            continue
        tokens.append(token)
    return tokens


def analyze_word_counts(files: list[str], top_n: int = 80) -> dict[str, object]:
    if not files:
        raise RuntimeError("분석할 PDF를 선택하세요.")

    pdf_paths = [resolve_downloaded_pdf(file_path) for file_path in files]
    return analyze_word_counts_from_paths(pdf_paths, top_n=top_n)


def _to_top_words(counter: Counter[str], top_n: int) -> list[dict[str, object]]:
    max_count = max(counter.values(), default=1)
    return [
        {
            "word": word,
            "count": count,
            "weight": round(count / max_count, 4),
        }
        for word, count in counter.most_common(top_n)
    ]


def analyze_word_counts_from_paths(pdf_paths: list[Path], top_n: int = 80) -> dict[str, object]:
    if not pdf_paths:
        raise RuntimeError("분석할 PDF를 선택하세요.")

    total_counter: Counter[str] = Counter()
    per_file: list[dict[str, object]] = []

    for pdf_path in pdf_paths:
        assets = extract_pdf_assets(pdf_path)
        file_counter: Counter[str] = Counter()
        file_counter.update(tokenize_text(str(assets.get("text", ""))))
        total_counter.update(file_counter)

        per_file.append(
            {
                "fileId": pdf_path.name,
                "fileName": pdf_path.name,
                "relativePath": str(pdf_path),
                "totalWords": sum(file_counter.values()),
                "uniqueWords": len(file_counter),
                "topWords": _to_top_words(file_counter, top_n),
            }
        )

    return {
        "fileCount": len(pdf_paths),
        "totalWords": sum(total_counter.values()),
        "uniqueWords": len(total_counter),
        "topWords": _to_top_words(total_counter, top_n),
        "perFile": per_file,
    }
