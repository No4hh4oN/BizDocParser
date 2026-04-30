# BizDocParser Report UI Guide

`README.md`는 원본 문서로 유지하고, 이 문서는 개선된 Report UI/UX 전용 가이드입니다.

## 개요

Report UI는 메일 조회부터 PDF 다운로드, 임원 보고서 생성, 워드클라우드 분석, 직원 참여 가능 판단(LLM)까지 문서별로 처리할 수 있는 웹 UI입니다.

- 서버: `src/mail_ui_server_report.py`
- 화면: `web/flow-ui-report.html`, `web/flow-ui-report.css`, `web/flow-ui-report.js`
- 기본 주소: `http://127.0.0.1:8001`

## 실행 방법

```bash
# 가상환경 활성화 후
pip install -r requirements.txt
python src/mail_ui_server_report.py
```

브라우저에서 `http://127.0.0.1:8001` 접속

## 환경 변수

`.env`에 아래 정보가 필요합니다.

- 메일 조회/다운로드
  - `IMAP_SERVER`
  - `IMAP_EMAIL`
  - `IMAP_PASSWORD`
- LLM 참여판단
  - `OPENAI_API_KEY`

## 화면 흐름

1. Step 1 메일 조회
2. Step 2 메일 선택 및 PDF 다운로드
3. Step 3 다운로드된 PDF 확인
4. Step 4 문서별 임원 보고서 생성/다운로드
5. Step 5 문서별 단어 분석 및 워드클라우드 결과 보기(모달)
6. Step 6 문서별 LLM 참여판단, 결과 보기/다운로드

## Step 4 동작

- `보고서 생성`은 미생성 문서에만 표시됩니다.
- 생성 완료 문서는 `보고서 다운로드`만 표시됩니다.
- 결과 경로는 문서 카드 내에서 줄바꿈되어 표시됩니다.

## Step 5 동작

- 문서별 `단어 분석` 버튼으로 개별 분석 수행
- 분석 성공 후 `단어 분석` 버튼은 숨김
- `워드클라우드 결과 보기`로 모달 표시
- 모달에서 아래 다운로드 지원
  - 워드클라우드 이미지 다운로드
  - 단어 빈도 CSV 다운로드

## Step 6 동작

- 문서마다 별도 모델 드롭다운 제공
- 모델 드롭다운은 텍스트 생성용 모델만 표시
- `작업 가능 인원 분석`은 문서별 독립 실행
- 재분석 시 확인창 표시
  - 기존 결과 다운로드 확인 후 재분석 진행 여부 선택
- `결과 보기`는 해당 문서 카드 바로 아래에서 토글(펼침/접기)
- `결과 다운로드`로 최신 XLSX 파일 다운로드

## 모델 목록 조회

Step 6 드롭다운 모델은 `/api/openai-models`로 조회합니다.

- 소스: OpenAI `models.list`
- 필터: 텍스트 생성 모델만 노출
- 제외: 이미지/오디오/임베딩/모더레이션/실시간/스냅샷 모델
- API 조회 실패 시 기본 텍스트 모델 목록으로 폴백

## 주요 API

- `GET /api/config`
- `GET /api/mail`
- `POST /api/download`
- `POST /api/convert`
- `POST /api/analyze`
- `POST /api/staff-evaluate`
- `GET /api/openai-models`
- `GET /api/download-file`

## 출력 경로

- 임원 보고서: `outputs/executive_reports/<timestamp>/<pdf_stem>/executive_summary.xlsx`
- 참여판단 결과: `outputs/staff_evaluations/<timestamp>/<pdf_stem>/staff_participation_<model>_<timestamp>.xlsx`
- 보조 산출물(JSON/MD/CSV)도 동일 루트 하위에 저장

