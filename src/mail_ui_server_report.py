from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app_config import BASE_DIR, bootstrap_env, load_mail_settings
from csv_converter import convert_pdfs_to_csv
from inbox_query import list_inbox_mails
from pdf_downloader import download_pdf_attachments
from staff_eval_converter import evaluate_staff_participation_for_files
from word_analyzer import analyze_word_counts
from word_cloud import build_word_cloud, build_word_cloud_image

import sys

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from rfp_analysis.pipeline import RfpAnalysisPipeline

    RFP_PIPELINE_AVAILABLE = True
except ImportError:
    RFP_PIPELINE_AVAILABLE = False


HOST = "127.0.0.1"
PORT = 8001
WEB_DIR = BASE_DIR / "web"
STATIC_FILES = {
    "/": WEB_DIR / "flow-ui-report.html",
    "/flow-ui-report.html": WEB_DIR / "flow-ui-report.html",
    "/flow-ui-report.css": WEB_DIR / "flow-ui-report.css",
    "/flow-ui-report.js": WEB_DIR / "flow-ui-report.js",
}

DEFAULT_STAFF_MODELS = [
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "o1",
    "o3",
    "o4-mini",
]

SNAPSHOT_SUFFIX_PATTERN = re.compile(r"-\d{4}-\d{2}-\d{2}$")


def _is_supported_text_generation_model(model_id: str) -> bool:
    """
    Step6에 노출할 텍스트 생성 모델만 선별한다.
    - 포함: gpt-*, o1/o3/o4 계열(텍스트 생성 추론 모델)
    - 제외: 이미지/오디오/임베딩/모더레이션/실시간/스냅샷 등
    """
    if not model_id:
        return False

    lowered = model_id.lower()
    if SNAPSHOT_SUFFIX_PATTERN.search(lowered):
        return False

    excluded_fragments = (
        "audio",
        "realtime",
        "transcribe",
        "tts",
        "dall-e",
        "image",
        "embedding",
        "moderation",
        "search",
        "computer-use",
        "omni-moderation",
    )
    if any(fragment in lowered for fragment in excluded_fragments):
        return False

    if lowered.startswith("gpt-"):
        return True

    # reasoning text-generation families
    if lowered in {"o1", "o3", "o4-mini"}:
        return True
    if lowered.startswith("o1-") or lowered.startswith("o3-") or lowered.startswith("o4-"):
        return True

    return False


def _filter_text_generation_models(model_ids: list[str]) -> list[str]:
    filtered = [model_id for model_id in model_ids if _is_supported_text_generation_model(model_id)]
    return sorted(set(filtered))


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def static_response(handler: BaseHTTPRequestHandler, file_path: Path) -> None:
    if not file_path.exists():
        handler.send_error(404)
        return

    body = file_path.read_bytes()
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    if file_path.suffix in {".html", ".css", ".js"}:
        content_type = f"{content_type}; charset=utf-8"

    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw_body = handler.rfile.read(length)
    return json.loads(raw_body.decode("utf-8"))


class MailUiReportHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print(f"[mail-ui-report] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in STATIC_FILES:
            static_response(self, STATIC_FILES[parsed.path])
            return

        if parsed.path == "/api/config":
            self.handle_config()
            return

        if parsed.path == "/api/mail":
            self.handle_mail_query(parsed.query)
            return

        if parsed.path == "/api/download-file":
            self.handle_download_file(parsed.query)
            return

        if parsed.path == "/api/openai-models":
            self.handle_openai_models()
            return

        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/download":
            self.handle_download()
            return

        if parsed.path == "/api/convert":
            self.handle_convert()
            return

        if parsed.path == "/api/analyze":
            self.handle_analyze()
            return

        if parsed.path == "/api/staff-evaluate":
            self.handle_staff_evaluate()
            return

        if parsed.path == "/api/rfp-analyze":
            self.handle_rfp_analyze()
            return

        self.send_error(404)

    def handle_config(self) -> None:
        try:
            settings = load_mail_settings()
            json_response(
                self,
                200,
                {
                    "emailAddress": settings.email_address,
                    "imapServer": settings.imap_server,
                },
            )
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_mail_query(self, query_string: str) -> None:
        try:
            params = parse_qs(query_string)
            search_text = params.get("query", [""])[0]
            period = params.get("period", ["7"])[0]
            mails = list_inbox_mails(search_text=search_text, period=period)
            json_response(self, 200, {"mails": mails})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_download_file(self, query_string: str) -> None:
        try:
            params = parse_qs(query_string)
            relative_path = params.get("path", [""])[0].strip()
            if not relative_path:
                self.send_error(400, "path query is required")
                return

            base_resolved = BASE_DIR.resolve()
            target_path = (BASE_DIR / relative_path).resolve()
            if not target_path.is_relative_to(base_resolved):
                self.send_error(403, "invalid path")
                return
            if not target_path.exists() or not target_path.is_file():
                self.send_error(404, "file not found")
                return

            body = target_path.read_bytes()
            content_type = mimetypes.guess_type(target_path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{target_path.name}"')
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_download(self) -> None:
        try:
            payload = read_json_body(self)
            mail_ids = [str(mail_id) for mail_id in payload.get("mailIds", [])]
            files = download_pdf_attachments(mail_ids)
            json_response(self, 200, {"files": files})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_convert(self) -> None:
        try:
            payload = read_json_body(self)
            files = [str(file_path) for file_path in payload.get("files", [])]
            result = convert_pdfs_to_csv(files)
            json_response(self, 200, result)
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_analyze(self) -> None:
        try:
            payload = read_json_body(self)
            files = [str(file_path) for file_path in payload.get("files", [])]
            analysis = analyze_word_counts(files)
            analysis["wordCloud"] = build_word_cloud(analysis["topWords"])
            analysis["wordCloudImage"] = build_word_cloud_image(analysis["topWords"])
            for item in analysis.get("perFile", []):
                top_words = item.get("topWords", [])
                item["wordCloud"] = build_word_cloud(top_words)
                item["wordCloudImage"] = build_word_cloud_image(top_words)
            json_response(self, 200, {"analysis": analysis})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_staff_evaluate(self) -> None:
        try:
            payload = read_json_body(self)
            files = [str(file_path) for file_path in payload.get("files", [])]
            model = payload.get("model")
            result = evaluate_staff_participation_for_files(files=files, model=model)
            json_response(self, 200, result)
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_openai_models(self) -> None:
        """
        현재 API 키/권한으로 호출 가능한 모델 ID 목록을 조회해 반환한다.
        조회 실패 시 기본 모델 목록으로 폴백한다.
        """
        try:
            bootstrap_env()
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not api_key:
                json_response(self, 200, {"models": DEFAULT_STAFF_MODELS, "source": "fallback"})
                return

            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            page = client.models.list()
            model_ids_set: set[str] = set()
            while True:
                model_ids_set.update(item.id for item in page.data if getattr(item, "id", None))
                if not getattr(page, "has_next_page", lambda: False)():
                    break
                page = page.get_next_page()

            model_ids = _filter_text_generation_models(list(model_ids_set))
            if not model_ids:
                json_response(self, 200, {"models": DEFAULT_STAFF_MODELS, "source": "fallback"})
                return

            json_response(self, 200, {"models": model_ids, "source": "api"})
        except Exception:
            json_response(self, 200, {"models": DEFAULT_STAFF_MODELS, "source": "fallback"})

    def handle_rfp_analyze(self) -> None:
        if not RFP_PIPELINE_AVAILABLE:
            json_response(self, 500, {"error": "RFP 분석 모듈(rfp_analysis)을 로드할 수 없습니다."})
            return

        try:
            payload = read_json_body(self)
            files = [str(file_path) for file_path in payload.get("files", [])]
            if not files:
                json_response(self, 400, {"error": "분석할 파일을 선택하세요."})
                return

            pipeline = RfpAnalysisPipeline()
            results = []
            for file_path in files:
                from csv_converter import resolve_downloaded_pdf

                full_path = resolve_downloaded_pdf(file_path)
                result = pipeline.run(full_path)
                results.append(result)

            json_response(self, 200, {"rfp_results": results})
        except Exception as exc:
            json_response(self, 500, {"error": f"RFP 분석 중 오류 발생: {str(exc)}"})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MailUiReportHandler)
    print(f"mail ui report server: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
