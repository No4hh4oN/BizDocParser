"""
RFP 분석 파이프라인 (RFP Analysis Pipeline)

이 모듈은 개별 추출기(Extractor)와 빌더(Builder)를 연결하여 
하나의 완성된 분석 프로세스를 제공합니다.

프로세스:
1. PDF 파일 경로를 입력받아 텍스트 및 표 데이터를 추출합니다.
2. 각 Extractor(개요, 범위, 요구사항, 리스크)를 순차적으로 실행합니다.
3. 추출된 데이터를 통합하여 최종 결과 객체를 생성합니다.
4. Builder를 통해 마크다운 보고서와 JSON 컨텍스트를 생성합니다.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# 기존 프로젝트의 라이브러리 활용 (학습용 주석: 기존 인프라를 재사용하여 효율성을 높입니다)
from src.send_purchase_orders import extract_pdf_assets

# 신규 구현 모듈 임포트
from rfp_analysis.extractors.project_info_extractor import ProjectInfoExtractor
from rfp_analysis.extractors.scope_extractor import ScopeExtractor
from rfp_analysis.extractors.requirement_extractor import RequirementExtractor
from rfp_analysis.extractors.risk_extractor import RiskExtractor
from rfp_analysis.builders.executive_summary_builder import ExecutiveSummaryBuilder
from rfp_analysis.builders.llm_context_builder import LlmContextBuilder

class RfpAnalysisPipeline:
    """
    RFP 분석의 전 과정을 관리하는 중앙 파이프라인 클래스입니다.
    학습용 주석: 파이프라인 패턴을 사용하여 각 단계를 독립적으로 관리하고 확장할 수 있게 합니다.
    """

    def __init__(self):
        # 각 구성 요소 초기화
        self.info_extractor = ProjectInfoExtractor()
        self.scope_extractor = ScopeExtractor()
        self.req_extractor = RequirementExtractor()
        self.risk_extractor = RiskExtractor()
        self.summary_builder = ExecutiveSummaryBuilder()
        self.llm_builder = LlmContextBuilder()

    def run(self, pdf_path: str) -> Dict[str, Any]:
        """
        주어진 PDF 파일에 대해 전체 분석을 수행합니다.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")

        print(f"[Pipeline] 분석 시작: {path.name}")
        
        # 1. 원천 데이터 추출 (기존 모듈 활용)
        # 학습용 주석: pdfplumber를 사용하여 텍스트와 표를 가져옵니다.
        assets = extract_pdf_assets(path)
        full_text = assets.get("text", "")

        # 2. 개별 추출기 실행
        # 학습용 주석: 각 추출기는 고유의 책임을 가지며 독립적으로 작동합니다.
        project_info = self.info_extractor.extract(full_text, assets.get("tables", []))
        scope = self.scope_extractor.extract(full_text)
        requirements = self.req_extractor.extract_from_assets(assets)
        # risks = self.risk_extractor.extract(full_text, requirements.get("details", []))
        risks = [] # 리스크 추출 기능 일시 중지 (학습용 주석: 추후 구현을 위해 보류)

        # 3. 데이터 통합
        analysis_data = {
            "document_name": path.name,
            "analysis_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_info": project_info,
            "scope": scope,
            "requirements": requirements,
            "risks": risks
        }

        # 4. 리포트 및 결과물 생성 (Excel 보고서는 main.py에서 별도로 처리)
        llm_context = self.llm_builder.build(analysis_data)

        # 결과 객체 구성
        return {
            "data": analysis_data,
            "reports": {
                "llm_ready_rfp_context": llm_context
            }
        }
