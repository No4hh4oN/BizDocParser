"""
요구사항 상세 추출기 (Requirement Extractor)

이 모듈은 RFP의 핵심인 상세 요구사항(SFR, DAR, SER 등)을 추출하고 통계를 산출합니다.

프로세스:
1. 'SFR-001'과 같은 요구사항 식별자 패턴을 정규식으로 찾습니다.
2. 식별자 주변의 텍스트 또는 표(Table) 데이터를 분석하여 요구사항명, 상세 설명, 산출물을 추출합니다.
3. 추출된 데이터를 기반으로 코드별(유형별) 분포 통계를 계산합니다.
"""

import re
from typing import Any, Dict, List
from rfp_analysis.resources.requirement_code_map import get_category_name

class RequirementExtractor:
    """
    상세 요구사항 목록을 구조화된 데이터로 변환하고 분석합니다.
    학습용 주석: 공공기관 RFP의 요구사항은 보통 [ID / 요구사항명 / 상세설명 / 산출물] 구조를 가집니다.
    """

    def __init__(self):
        # 요구사항 ID 패턴 (예: SFR-001, SFR 001, [SFR-001])
        self.id_pattern = r"([A-Z]{3})[-_\s]*(\d{3})"

    def extract_from_assets(self, assets: Dict[str, Any]) -> Dict[str, Any]:
        """
        pdf_assets(텍스트 및 표)로부터 요구사항 정보를 추출합니다.
        """
        text = assets.get("text", "")
        tables = assets.get("tables", [])
        
        details = []
        # 1. 텍스트에서 ID 기반으로 매칭 시도 (단순화된 방식)
        # 학습용 주석: 실제 구현에서는 표(Table) 데이터를 순회하며 컬럼명을 기반으로 파싱하는 것이 더 정확합니다.
        # 여기서는 텍스트 기반의 범용적인 패턴 매칭 방식을 예시로 구현합니다.
        
        matches = list(re.finditer(self.id_pattern, text))
        
        for i, match in enumerate(matches):
            prefix = match.group(1)
            num = match.group(2)
            req_id = f"{prefix}-{num}"
            
            # 다음 매칭 지점까지의 텍스트를 컨텐츠로 간주
            start_pos = match.end()
            end_pos = matches[i+1].start() if i + 1 < len(matches) else len(text)
            content = text[start_pos:end_pos].strip()
            
            # 컨텐츠 내에서 줄바꿈 기준으로 명칭과 설명을 분리 시도
            content_lines = [line.strip() for line in content.split('\n') if line.strip()]
            req_name = content_lines[0] if content_lines else "명칭 미탐지"
            description = " ".join(content_lines[1:]) if len(content_lines) > 1 else "설명 미탐지"
            
            # '산출물' 키워드 근처 탐색
            deliverables = "내용 요약 참조"
            if "산출물" in content:
                # '산출물' 키워드 뒤의 텍스트를 일부 추출
                parts = content.split("산출물")
                if len(parts) > 1:
                    deliverables = parts[1].strip().split('\n')[0]

            details.append({
                "requirement_id": req_id,
                "category_code": prefix,
                "category_name": get_category_name(prefix),
                "requirement_name": req_name,
                "description": description,
                "deliverables": deliverables,
                "source_section": "요구사항 상세명세",
                "extract_method": "id_proximity_extraction"
            })

        # 2. 통계 계산
        stats = self._calculate_statistics(details)

        return {
            "details": details,
            "statistics": stats
        }

    def _calculate_statistics(self, details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        추출된 요구사항의 유형별 개수와 비율을 계산합니다.
        학습용 주석: 이 통계는 사업의 성격(개발 위주 vs 보안 위주 등)을 판단하는 근거가 됩니다.
        """
        if not details:
            return []

        counts = {}
        total = len(details)

        for item in details:
            code = item["category_code"]
            counts[code] = counts.get(code, 0) + 1

        stats = []
        for code, count in counts.items():
            ratio = (count / total) * 100
            stats.append({
                "category_code": code,
                "category_name": get_category_name(code),
                "count": count,
                "ratio": f"{ratio:.1f}%",
                "interpretation": self._interpret_stat(code, ratio)
            })
        
        # 개수 순으로 정렬
        stats.sort(key=lambda x: x["count"], reverse=True)
        return stats

    def _interpret_stat(self, code: str, ratio: float) -> str:
        """
        비율에 따른 간단한 분석 의견을 생성합니다.
        학습용 주석: 사용자에게 수치 이상의 의미를 전달하기 위한 보조 장치입니다.
        """
        if ratio > 40:
            return f"해당 사업은 {code} 비중이 매우 높음 (중점 관리 필요)"
        elif ratio > 20:
            return f"{code} 요구사항이 주요 과업에 포함됨"
        return "일반적인 수준의 요구사항"
