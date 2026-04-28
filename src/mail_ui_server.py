from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from app_config import BASE_DIR, load_mail_settings
from csv_converter import convert_pdfs_to_csv
from inbox_query import list_inbox_mails
from pdf_downloader import download_pdf_attachments
from word_analyzer import analyze_word_counts
from word_cloud import build_word_cloud


HOST = "127.0.0.1"
PORT = 8000
WEB_DIR = BASE_DIR / "web"
STATIC_FILES = {
    "/": WEB_DIR / "flow-ui.html",
    "/flow-ui.html": WEB_DIR / "flow-ui.html",
    "/flow-ui.css": WEB_DIR / "flow-ui.css",
    "/flow-ui.js": WEB_DIR / "flow-ui.js",
}


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
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw_body = handler.rfile.read(length)
    return json.loads(raw_body.decode("utf-8"))


class MailUiHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        print(f"[mail-ui] {self.address_string()} - {format % args}")

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
            json_response(self, 200, {"analysis": analysis})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), MailUiHandler)
    print(f"mail ui server: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
