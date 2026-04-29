"""
수행 범위 추출기 (Scope Extractor)

2단계 추출 요약:
  1단계: 사업 범위 섹션을 단락(블록)으로 쪼개고, 각 블록에서
         kiwipiepy의 키워드 추출 + 문장 분리로 대표 문장 1개를 뽑는다.
  2단계: 모인 블록 대표 문장들을 키워드 점수로 재평가하여 5~10개로 압축한다.
"""

from kiwipiepy import Kiwi
import re
import random
from typing import Dict, List, Any


class ScopeExtractor:

    def __init__(self):
        self.kiwi = Kiwi()

        # 패턴 기반 노이즈 필터
        self.noise_regexes = [
            r"(SFR|DAR|SER|QUR|PMR|PSR|MMY)-\d+",  # 요구사항 코드
            r"관련\s*리스크\s*키워드",               # 리스크 섹션 라벨
            r"더미\s*RFP",                           # 테스트용 마커
            r"^산출\s*정보",                         # 산출물 목록 헤더
        ]
        self.noise_keywords = [
            "입찰", "제안유의", "보완자료",                  # 입찰 안내
            "하여야 한다", "해야 한다", "하여야",            # 지시문
            "어야 한다",                                   # 지시문 변형 (되어야, 이어야 등)
            "부족", "미흡", "문제점", "필요가 있음", "필요함",  # 진단문
            "산출정보", "사업수행계획서", "제안요청서",        # 산출물·문서명
            "범위 외", "포함하지 않", "한정한다", "본 사업은", # 제외 범위·한정 문구
        ]

        # fallback — 2단계 결과가 5개 미만일 때 최대 3개까지 보강
        self.fallback_scope = [
            "시스템 운영, 정기 점검, 장애 대응, 사용자 문의 처리",
            "핵심 업무 기능 개선 및 신규 기능 개발",
            "데이터 수집, 정합성 점검, 이력 관리 체계 수립",
        ]

        # 평가용: 1단계 블록 대표 문장 보존
        self._last_raw_candidates: List[str] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def extract(self, text: str) -> Dict[str, Any]:
        scope_text = self._find_scope_section(text)

        # 1단계: 단락 블록별 대표 문장 추출
        blocks = self._split_into_blocks(scope_text)
        per_block = []
        for block in blocks:
            sent = self._best_sentence_in_block(block)
            if sent:
                per_block.append(sent)

        self._last_raw_candidates = list(per_block)

        # 2단계: 블록 대표 문장들에서 5~10개로 재요약
        final = self._select_top_n(per_block, n_min=5, n_max=8)

        # 결과가 5개 미만이면 fallback 보강 (최대 3개)
        if len(final) < 5:
            for line in self.fallback_scope:
                if not self._is_similar_to_any(line, final):
                    final.append(line)
                if len(final) >= 5:
                    break

        return {
            "included_scope": final,
            "excluded_scope": [
                "하드웨어 및 인프라 직접 구매",
                "상용 솔루션 라이선스 비용",
                "제안 범위 외 기능 구현",
            ],
        }

    # ------------------------------------------------------------------ #
    # 1단계: 블록 분리 + 블록별 대표 문장
    # ------------------------------------------------------------------ #

    def _split_into_blocks(self, text: str) -> List[str]:
        """
        RFP 텍스트를 블록으로 분리.
        1순위: 빈 줄(\n\n) 기준  →  충분한 블록이 나오면 사용
        2순위: 번호/불릿 앞에서 자르기
        3순위: 줄 단위 (PDF 추출 텍스트에 빈 줄이 없는 경우)
        """
        # 1순위: 빈 줄 기준
        raw = re.split(r"\n{2,}", text)
        blocks = [b.strip() for b in raw if len(b.strip()) >= 20]
        if len(blocks) >= 4:
            return blocks

        # 2순위: 번호(1. 2.)나 불릿(① ② • -)으로 시작하는 줄에서 새 블록 시작
        lines = text.split("\n")
        blocks = []
        current: List[str] = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            is_new = bool(re.match(r"^[\d①-⑩○•\-]+[\.\)\s]", line))
            if is_new and current:
                blocks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append("\n".join(current))
        blocks = [b for b in blocks if len(b) >= 20]
        if len(blocks) >= 4:
            return blocks

        # 3순위: 줄 단위
        return [ln.strip() for ln in text.split("\n") if len(ln.strip()) >= 20]

    def _best_sentence_in_block(self, block: str) -> str:
        """
        블록 안에서 kiwipiepy로 키워드·문장을 뽑아
        키워드를 가장 많이 포함한 문장 1개를 반환한다.
        단일 줄 블록은 그대로 반환(kiwi.split_into_sents 불필요).
        """
        keywords = self._extract_keywords(block, top_n=10)
        sents = self.kiwi.split_into_sents(block)

        best = ""
        best_score = -1
        for s in sents:
            txt = s.text.strip()
            if self._is_noise(txt):
                continue
            if not (15 <= len(txt) <= 120):
                continue
            score = sum(1 for kw in keywords if kw in txt)
            # 동점 시 약간의 랜덤으로 run마다 결과가 달라질 여지 부여
            score_jitter = score + random.uniform(0, 0.3)
            if score_jitter > best_score:
                best_score = score_jitter
                best = txt

        return best

    # ------------------------------------------------------------------ #
    # 2단계: 전체 재요약 (5~10개)
    # ------------------------------------------------------------------ #

    def _select_top_n(self, sentences: List[str], n_min: int, n_max: int) -> List[str]:
        """
        블록 대표 문장 전체를 모아 키워드 점수로 재평가 후 상위 n개 선택.
        동점 처리에 랜덤 jitter(0~1)를 넣어 매 실행마다 결과가 달라질 수 있다.
        """
        if not sentences:
            return []

        corpus = " ".join(sentences)
        keywords = self._extract_keywords(corpus, top_n=30)

        scored = []
        for sent in sentences:
            score = sum(1 for kw in keywords if kw in sent)
            # jitter 범위를 1.0으로 키워 근접 점수 간 순위가 run마다 달라지게 함
            scored.append((sent, score + random.uniform(0, 1.0)))

        scored.sort(key=lambda x: x[1], reverse=True)

        result = []
        for sent, _ in scored:
            cleaned = self._clean(sent)
            if not cleaned:
                continue
            if not self._is_similar_to_any(cleaned, result):
                result.append(cleaned)
            if len(result) >= n_max:
                break

        return result

    # ------------------------------------------------------------------ #
    # 공통 유틸
    # ------------------------------------------------------------------ #

    def _extract_keywords(self, text: str, top_n: int) -> List[str]:
        """kiwipiepy로 키워드 추출. extract_keywords 미지원 시 명사 빈도로 대체."""
        if hasattr(self.kiwi, "extract_keywords"):
            kws = self.kiwi.extract_keywords(text, top_n=top_n)
            return [k.form for k in kws if len(k.form) > 1]
        from collections import Counter
        counter: Counter = Counter()
        for tok in self.kiwi.tokenize(text):
            if tok.tag.startswith("NN") and len(tok.form) > 1:
                counter[tok.form] += 1
        return [w for w, _ in counter.most_common(top_n)]

    def _find_scope_section(self, text: str) -> str:
        for pat in [r"\d\.\s*사\s*업\s*범\s*위", r"\d\.\s*과\s*업\s*내\s*용", r"\d\.\s*주\s*요\s*과\s*업"]:
            m = re.search(pat, text)
            if m:
                return text[m.start(): m.start() + 7000]
        for pat in [r"사\s*업\s*범\s*위", r"과\s*업\s*내\s*용"]:
            m = re.search(pat, text)
            if m:
                return text[m.start(): m.start() + 7000]
        return text[:8000]

    def _is_noise(self, text: str) -> bool:
        for pat in self.noise_regexes:
            if re.search(pat, text):
                return True
        return any(kw in text for kw in self.noise_keywords)

    def _clean(self, text: str) -> str:
        text = re.sub(r"^[•\-\d\.\s①-⑩※]+", "", text).strip()
        text = re.sub(r"\s+", " ", text)
        if len(text) > 95:
            text = text[:92].rstrip() + "..."
        return text if len(text) >= 15 else ""

    def _is_similar_to_any(self, line: str, candidates: List[str]) -> bool:
        return any(self._similarity(line, c) >= 0.75 for c in candidates)

    def _similarity(self, a: str, b: str) -> float:
        ta = set(re.findall(r"[가-힣A-Za-z0-9]+", a))
        tb = set(re.findall(r"[가-힣A-Za-z0-9]+", b))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)
