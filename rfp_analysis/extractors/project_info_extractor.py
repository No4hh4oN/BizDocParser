"""
사업 개요 추출기 (Project Info Extractor)

이 모듈은 RFP 텍스트에서 사업의 가장 기본적인 정보(명칭, 기간, 예산 등)를 정규표현식과
키워드 매칭을 통해 추출합니다. 

프로세스:
1. '사업개요', '공고' 섹션을 우선적으로 탐색합니다.
2. 특정 키워드(예: '사업예산', '사업기간') 뒤에 오는 텍스트를 추출합니다.
3. 화폐 단위(원)나 날짜 형식(년, 월, 일)을 정규식으로 파싱하여 정제합니다.
"""

import re
from typing import Any, Dict

class ProjectInfoExtractor:
    """
    RFP 텍스트에서 프로젝트 메타데이터를 추출하는 클래스입니다.
    학습용 주석: 복잡한 문장 속에서 원하는 값만 골라내기 위해 '패턴 정의 -> 매칭 -> 정제' 과정을 거칩니다.
    """

    def __init__(self):
        # 추출할 필드와 해당 필드를 찾기 위한 정규표현식 패턴들 정의
        # 학습용 주석: 공공기관마다 표현이 조금씩 다르므로(예: 예산 vs 사업비), 다양한 패턴을 등록합니다.
        self.patterns = {
            "project_name": [
                r"사\s*업\s*명\s*[:：]\s*(.+)",
                r"용\s*역\s*명\s*[:：]\s*(.+)",
                r"\[\s*사\s*업\s*명\s*\]\s*(.+)"
            ],
            "agency": [
                r"발\s*주\s*기\s*관\s*[:：]\s*(.+)",
                r"수\s*요\s*기\s*관\s*[:：]\s*(.+)",
                r"부\s*서\s*명\s*[:：]\s*(.+)"
            ],
            "notice_no": [
                r"공\s*고\s*번\s*호\s*[:：]\s*(.+)",
                r"입\s*찰\s*번\s*호\s*[:：]\s*(.+)"
            ],
            "project_period": [
                r"사\s*업\s*기\s*간\s*[:：]\s*(.+)",
                r"용\s*역\s*기\s*간\s*[:：]\s*(.+)",
                r"기\s*간\s*[:：]\s*계\s*약\s*일\s*로\s*부\s*터\s*(.+)"
            ],
            "budget": [
                r"사\s*업\s*예\s*산\s*[:：]\s*(.+)",
                r"사\s*업\s*비\s*[:：]\s*(.+)",
                r"추\s*정\s*금\s*액\s*[:：]\s*(.+)",
                r"금\s*액\s*[:：]\s*(.+)"
            ],
            "contract_method": [
                r"계\s*약\s*방\s*식\s*[:：]\s*(.+)",
                r"입\s*찰\s*방\s*식\s*[:：]\s*(.+)"
            ],
            "business_type": [
                r"사\s*업\s*유\s*형\s*[:：]\s*(.+)"
            ],
            "submission_deadline": [
                r"제\s*출\s*마\s*감\s*일\s*[:：]\s*(.+)",
                r"입\s*찰\s*마\s*감\s*[:：]\s*(.+)",
                r"제\s*출\s*기\s*한\s*[:：]\s*(.+)"
            ],
            "evaluation_ratio": [
                r"평\s*가\s*비\s*율\s*[:：]\s*(.+)",
                r"평\s*가\s*방\s*법\s*[:：]\s*(.+)",
                r"기\s*술\s*능\s*력\s*평\s*가\s*(.+)"
            ]
        }

    def extract(self, text: str, tables: list = None) -> Dict[str, Any]:
        """
        텍스트와 표 데이터를 활용하여 최적의 정보를 추출합니다.
        """
        results = {}
        # 1. 표 데이터 분석 (우선순위 부여)
        table_results = self._extract_from_tables(tables) if tables else {}
        
        for field, patterns in self.patterns.items():
            value = "not_found"
            source_section = "not_found"
            
            # (A) 표 결과 우선 적용
            if table_results.get(field):
                value = table_results[field]
                source_section = "표(Table)"
            
            # (B) 정규식 보완
            if value == "not_found":
                for pattern in patterns:
                    match = re.search(pattern, text)
                    if match:
                        value = match.group(1).strip().split('\n')[0].strip()
                        source_section = "본문"
                        break
            
            # (C) 사업명 특수 규칙 (표지 제목)
            if field == "project_name" and value == "not_found":
                # 가장 긴 줄을 사업명으로 추정하되, 불용어 제외
                lines = [l.strip() for l in text.split('\n')[:15] if len(l.strip()) > 10]
                lines = [l for l in lines if "주의" not in l and "샘플" not in l]
                if lines:
                    value = lines[0]
                    source_section = "표지"

            results[field] = {
                "value": self._clean_value(field, value),
                "source_section": source_section,
                "extract_method": "hybrid_search",
                "confidence": 1.0 if value != "not_found" else 0.0
            }
        
        return results

    def _extract_from_tables(self, tables: list) -> Dict[str, str]:
        extracted = {}
        # 필드별 매칭 키워드 및 제외 키워드
        config = {
            "project_name": (["사업명", "용역명", "과업명"], ["내역", "안내"]),
            "agency": (["발주기관", "수요기관", "소속기관"], ["제출", "담당"]),
            "budget": (["사업예산", "사업비", "추정금액", "금액"], ["점", "배점", "평가"]),
            "project_period": (["사업기간", "용역기간", "수행기간"], []),
            "contract_method": (["계약방법", "계약방식", "입찰방식"], []),
            "submission_deadline": (["제출마감", "접수마감", "입찰마감"], []),
            "evaluation_ratio": (["평가비율", "평가방법", "평가배점"], [])
        }

        for table in tables:
            for row in table:
                row_cells = [str(c).replace('\n', ' ').strip() for c in row if c]
                row_str = " ".join(row_cells)
                
                for field, (keywords, negatives) in config.items():
                    if any(kw in row_str for kw in keywords):
                        # 제외 키워드가 있으면 스킵
                        if any(neg in row_str for neg in negatives):
                            continue
                            
                        # 키워드 다음 칸의 값을 추출
                        for i, cell in enumerate(row_cells):
                            if any(kw in cell for kw in keywords):
                                # 키워드 셀 자체가 값을 포함하는 경우 (예: "사업명: OOO")
                                if len(cell) > 10:
                                    extracted[field] = cell
                                    break
                                # 다음 셀이 값인 경우
                                if i + 1 < len(row_cells):
                                    extracted[field] = row_cells[i+1]
                                    break
        return extracted

    def _clean_value(self, field: str, value: str) -> str:
        if value == "not_found":
            return value
            
        value = value.strip(" :：[]()\"' ")
        
        if field == "budget":
            # 숫자와 '원'만 남기기 (예: "480,000,000원")
            match = re.search(r"([\d,]+원)", value)
            if match:
                return match.group(1)
        
        if field == "evaluation_ratio":
            # 배점 정보만 추출 (예: "기술 90 : 가격 10")
            match = re.search(r"(기\s*술.+?[\d]+.+?가\s*격.+?[\d]+)", value)
            if match:
                return match.group(1).replace('  ', ' ')
                
        return value
