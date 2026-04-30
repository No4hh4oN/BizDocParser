"""
임직원용 요약 보고서 빌더 (Executive Summary Builder) - Claude Golden Sample 적용 버전

이 모듈은 골든 샘플의 마크다운 구조(개요, 범위, 분포)를 엑셀 시트 내에 재현합니다.
데이터는 생성된 CSV 데이터프레임을 활용하여 정합성을 유지합니다.
"""

import pandas as pd
from typing import Any, Dict

class ExecutiveSummaryBuilder:
    """
    RFP 분석 결과를 골든 샘플 양식의 엑셀 보고서로 변환하는 클래스입니다.
    """

    def build_xlsx(self, df_info: pd.DataFrame, df_stats: pd.DataFrame, included_scope: list, output_path: str):
        """
        골든 샘플의 3단계 구조를 엑셀 시트에 배치합니다.
        1. 사업 개요 (표)
        2. 주요 수행 범위 (리스트)
        3. 요구사항 분포 (표)
        """
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sheet_name = 'RFP 요약 보고서'
            final_scope = included_scope[:8] if included_scope else ["사업 범위를 충분히 추출하지 못했습니다. 상세 요구사항을 참조하세요."]
            
            # (1) 섹션 1: 사업 개요 (표)
            df_info.to_excel(writer, sheet_name=sheet_name, index=False, startrow=2)
            
            # (2) 섹션 2: 주요 수행 범위 (리스트 형식)
            # 학습용 주석: 골든 샘플의 2번 섹션을 재현하기 위해 리스트 데이터를 데이터프레임으로 변환하여 배치합니다.
            scope_rows = [{"주요 수행 범위": f"• {item}"} for item in final_scope]
            df_scope = pd.DataFrame(scope_rows)
            start_row_scope = len(df_info) + 5
            df_scope.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row_scope)
            
            # (3) 섹션 3: 요구사항 분포 (표)
            # 학습용 주석: 골든 샘플의 3번 섹션 표 형식을 그대로 유지합니다.
            start_row_stats = start_row_scope + len(df_scope) + 3
            df_stats.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row_stats)

            # 엑셀 서식 및 제목 삽입
            worksheet = writer.sheets[sheet_name]
            worksheet['A1'] = "RFP 요약 보고서 (Golden Sample 기준)"
            worksheet['A2'] = "## 1. 사업 개요"
            worksheet['A' + str(start_row_scope)] = "## 2. 주요 수행 범위"
            worksheet['A' + str(start_row_stats)] = "## 3. 요구사항 분포"
            
            # 컬럼 너비 조정
            worksheet.column_dimensions['A'].width = 25
            worksheet.column_dimensions['B'].width = 60
            worksheet.column_dimensions['C'].width = 15
            worksheet.column_dimensions['D'].width = 15
