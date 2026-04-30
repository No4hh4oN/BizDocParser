"""
요구사항 코드 매핑 사전

공공기관 IT 사업에서 사용하는 표준 요구사항 분류 코드(Prefix)를 사람이 읽기 쉬운 명칭으로 매핑합니다.
이 정보는 통계 보고서 및 대시보드 생성 시 가독성을 높이는 데 사용됩니다.
"""

# 요구사항 유형 코드와 한글 명칭 매핑
# 학습용 주석: 공공 SW 사업 제안요청서 작성 가이드의 표준 분류 체계를 따릅니다.
REQUIREMENT_CODE_MAP = {
    "SFR": "시스템 기능 요구사항 (System Function Requirement)",
    "DAR": "데이터 요구사항 (Data Requirement)",
    "SER": "보안 요구사항 (Security Requirement)",
    "QUR": "품질 요구사항 (Quality Requirement)",
    "PMR": "프로젝트 관리 요구사항 (Project Management Requirement)",
    "PSR": "프로젝트 지원 요구사항 (Project Support Requirement)",
    "INR": "인터페이스 요구사항 (Interface Requirement)",
    "TER": "테스트 요구사항 (Test Requirement)",
    "ORR": "운영 요구사항 (Operation Requirement)",
    "COR": "제약사항 (Constraint Requirement)"
}

def get_category_name(code: str) -> str:
    """
    코드를 기반으로 카테고리 명칭을 반환합니다.
    학습용 주석: 매핑되지 않은 새로운 코드가 나타날 경우를 대비하여 '기타' 처리를 포함합니다.
    """
    # 대문자로 변환하여 검색 (예: sfr -> SFR)
    clean_code = code.upper().strip()
    return REQUIREMENT_CODE_MAP.get(clean_code, f"기타 요구사항 ({clean_code})")
