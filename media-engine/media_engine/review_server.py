#!/usr/bin/env python3
"""Small local review server for the V1 UI shell."""

from __future__ import annotations

import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_all
from .models import PUBLISH_MODES
from .styles import load_style


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
        if parsed.path == "/api/targets":
            conn = connect(DEFAULT_DB)
            rows = fetch_all(conn, "SELECT * FROM publish_targets ORDER BY platform")
            self._send_json(rows)
            return
        if parsed.path == "/api/style":
            self._send_json(load_style())
            return
        if parsed.path == "/api/artifact":
            query = parse_qs(parsed.query)
            requested = Path(query.get("path", [""])[0]).resolve()
            root = ARTIFACTS_DIR.resolve()
            if not requested.exists() or root not in requested.parents:
                self._send_json({"error": "artifact not found"}, status=404)
                return
            content = requested.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(str(requested))[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Content-Disposition", f'inline; filename="{requested.name}"')
            self.end_headers()
            self.wfile.write(content)
            return
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, status=400)
            return

        if parsed.path == "/api/approve":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            result = conn.execute("UPDATE clip_candidates SET status = 'approved' WHERE id = ?", (candidate_id,))
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            self._send_json({"candidate_id": candidate_id, "status": "approved"})
            return

        if parsed.path == "/api/set-target-mode":
            profile = str(payload.get("profile", "nourbit")).strip()
            platform = str(payload.get("platform", "")).strip()
            mode = str(payload.get("mode", "")).strip()
            if mode not in PUBLISH_MODES:
                self._send_json({"error": "unsupported mode"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            result = conn.execute(
                "UPDATE publish_targets SET mode = ? WHERE profile_id = ? AND platform = ?",
                (mode, profile, platform),
            )
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "target not found"}, status=404)
                return
            self._send_json({"profile": profile, "platform": platform, "mode": mode})
            return

        self._send_json({"error": "not found"}, status=404)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def _send_json(self, value, status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), ReviewHandler)
    print("review UI: http://127.0.0.1:8765/review.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
