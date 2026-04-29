# BizDocParser

이메일 인박스에서 비즈니스 문서(RFP, 구매 발주서 등)를 자동으로 수집, 파싱, 그리고 분석하는 시스템입니다.

## 주요 기능

- **메일 자동 수집**: IMAP을 연계하여 특정 키워드(예: [발주서])가 포함된 메일의 첨부파일(PDF)을 자동 다운로드합니다.
- **문서 파싱 및 전환**: `pdfplumber`를 활용하여 PDF 내의 구조화된 데이터를 추출하고 CSV 리포트로 전환합니다.
- **텍스트 마이닝**: 수집된 문서의 키워드 빈도를 분석하고 워드클라우드를 생성합니다.
- **RFP 참여 검토 보고서**: 공공기관 IT 사업 RFP 문서에서 핵심 정보를 추출하여 임직원용 요약 보고서를 생성합니다.

## RFP 참여 검토 보고서 기능

이 프로젝트는 공공기관 IT 사업 RFP 문서에서 사업 참여 검토에 필요한 핵심 정보를 추출하고, 임직원용 요약 보고서와 CSV/JSON 구조화 결과를 생성합니다.

### 현재 범위

- 텍스트 선택 가능한 PDF만 처리
- Python 텍스트마이닝 기반 정보 추출
- LLM API 호출 없음
- 회사 내부 정보 기반 판단 없음
- OCR 없음

### 향후 확장

생성된 `llm_ready_rfp_context.json`에 회사 내부 정보, 기술스택, 가용 인력, 유사 사업 수행 이력을 결합하여 LLM API 또는 사내 sLM 기반 사업 참여 검토 보조 서비스로 확장할 수 있습니다.

### 실행 환경

Python 3.13.13과 `.venv`를 사용합니다.

```bash
# 환경 설정
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 분석 실행 (CLI)
python main.py --analyze rfp_dummy_pdf/rfp_genai_civil_service_chatbot.pdf

# 웹 서버 실행
python src/mail_ui_server.py
```

---
*본 프로젝트는 효율적인 비즈니스 문서 관리를 위해 설계되었습니다.*
