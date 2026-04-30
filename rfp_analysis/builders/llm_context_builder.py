"""
LLM 입력용 컨텍스트 빌더 (LLM Context Builder)

이 모듈은 향후 LLM(대규모 언어 모델)이나 sLM이 사업 참여 여부를 판단할 때 
참고할 수 있도록, 정제된 데이터를 표준화된 JSON 형식으로 변환합니다.

프로세스:
1. 추출된 모든 도메인 데이터(개요, 범위, 요구사항, 리스크)를 수집합니다.
2. JSON 스키마에 맞게 구조화합니다.
3. LLM이 수행해야 할 태스크(Future Tasks)를 포함하여 결과물을 생성합니다.
"""

import json
from datetime import datetime
from typing import Any, Dict

class LlmContextBuilder:
    """
    RFP 분석 데이터를 AI 모델이 이해하기 쉬운 구조의 JSON으로 변환합니다.
    학습용 주석: JSON 구조는 LLM의 추론 능력을 극대화하기 위해 계층적으로 설계되었습니다.
    """

    def build(self, data: Dict[str, Any]) -> str:
        """
        데이터를 JSON 문자열로 변환합니다.
        """
        info = data.get("project_info", {})
        scope = data.get("scope", {})
        reqs = data.get("requirements", {})
        risks = data.get("risks", [])

        # 표준화된 JSON 구조 정의 (골든 샘플 규격 반영)
        context = {
            "document_meta": {
                "document_name": info.get("project_name", {}).get("value", ""),
                "source_file": data.get("document_name", "")
            },
            "project_summary": {
                "project_name": info.get("project_name", {}).get("value", ""),
                "agency": info.get("agency", {}).get("value", ""),
                "budget": info.get("budget", {}).get("value", ""),
                "project_period": info.get("project_period", {}).get("value", ""),
                "contract_method": info.get("contract_method", {}).get("value", ""),
                "submission_deadline": info.get("submission_deadline", {}).get("value", ""),
                "evaluation_ratio": info.get("evaluation_ratio", {}).get("value", "")
            },
            "scope_summary": {
                "main_scope": scope.get("included_scope", [])
            },
            "requirements": {
                "statistics": reqs.get("statistics", []),
                "details": reqs.get("details", [])[:100]
            },
            "risk_candidates": [] # 리스크 분석 기능 보류 중
        }

        # 가독성을 위해 들여쓰기(indent)를 포함하여 직렬화
        return json.dumps(context, ensure_ascii=False, indent=2)
