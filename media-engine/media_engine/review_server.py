#!/usr/bin/env python3
"""Small local review server for the V1 UI shell."""

from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .db import DEFAULT_DB, ROOT, connect, fetch_all


class ReviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/review":
            conn = connect(DEFAULT_DB)
            rows = fetch_all(
                conn,
                """
                SELECT c.*, r.output_path
                FROM clip_candidates c
                LEFT JOIN render_jobs r ON r.candidate_id = c.id
                ORDER BY c.created_at DESC
                """,
            )
            payload = json.dumps(rows, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        return super().do_GET()


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), ReviewHandler)
    print("review UI: http://127.0.0.1:8765/review.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
