"""
수행 리스크 추출기 (Risk Extractor)

이 모듈은 RFP 내의 문구에서 사업 수행 시 주의가 필요한 잠재적 리스크 요소를 식별합니다.

프로세스:
1. rfp_analysis.resources.risk_keywords에 정의된 키워드 사전을 로드합니다.
2. 텍스트 전체를 문장 단위로 나누어 키워드가 포함된 문장을 찾습니다.
3. 키워드가 발견된 경우, 해당 문장과 근거 요구사항 ID(있을 경우)를 묶어 리스크 후보로 등록합니다.
"""

import re
from typing import Any, Dict, List
from rfp_analysis.resources.risk_keywords import RISK_KEYWORDS

class RiskExtractor:
    """
    키워드 매칭 기반의 리스크 탐지 엔진입니다.
    학습용 주석: 리스크 탐지는 '무엇이 문제인가(Type)'와 '어떤 문구 때문인가(Evidence)'를 연결하는 것이 핵심입니다.
    """

    def __init__(self):
        # 리스크 키워드 사전 로드
        self.risk_map = RISK_KEYWORDS

    def extract(self, text: str, requirements: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        텍스트에서 리스크 키워드를 탐색하고 근거 문장을 수집합니다.
        """
        risk_candidates = []
        
        # 텍스트를 문장 단위로 분할 (마침표 기준)
        sentences = [s.strip() for s in re.split(r"[\.\?\!\n]", text) if len(s.strip()) > 5]

        # 각 리스크 유형별로 키워드 매칭
        for risk_type, keywords in self.risk_map.items():
            for keyword in keywords:
                # 해당 키워드가 포함된 문장 탐색
                for sentence in sentences:
                    if keyword in sentence:
                        # 이미 등록된 문장인지 확인 (중복 방지)
                        if any(r["evidence_text"] == sentence for r in risk_candidates):
                            continue
                        
                        # 연관된 요구사항 ID 찾기 (문장에 ID 패턴이 있는지 확인)
                        related_id = "N/A"
                        id_match = re.search(r"([A-Z]{3})[-_\s]*(\d{3})", sentence)
                        if id_match:
                            related_id = f"{id_match.group(1)}-{id_match.group(2)}"

                        risk_candidates.append({
                            "risk_type": risk_type,
                            "risk_keyword": keyword,
                            "requirement_id": related_id,
                            "evidence_text": sentence,
                            "check_point": f"{keyword} 관련 요구사항 준수 여부 및 기술적 난이도 검토",
                            "severity": "중간 (검토 필요)" # 키워드 기반이므로 기본값 설정
                        })
        
        # 리스크 탐지 결과가 너무 많을 경우를 대비해 상위 건수만 제한하거나
        # 중복된 키워드/유형 조합을 정제할 수 있습니다.
        return risk_candidates[:50] # 최대 50건으로 제한
