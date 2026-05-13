#!/usr/bin/env python3
"""Small local review server for the V1 UI shell."""

from __future__ import annotations

import json
import mimetypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_all, initialize
from .credentials import credential_status
from .env_loader import load_env_file
from .live_publishers import LivePublishError, publish_telegram_video
from .models import PUBLISH_MODES
from .post_copy import build_post_caption
from .publishers import build_payload, create_dry_run_attempt
from .styles import load_style


class ReviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/review":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            rows = fetch_all(
                conn,
                """
                SELECT c.*, r.output_path, r.metadata_json AS render_metadata_json
                FROM clip_candidates c
                LEFT JOIN render_jobs r ON r.id = (
                  SELECT r2.id
                  FROM render_jobs r2
                  WHERE r2.candidate_id = c.id
                  ORDER BY r2.created_at DESC, r2.id DESC
                  LIMIT 1
                )
                ORDER BY c.created_at DESC
                """,
            )
            for row in rows:
                row["score"] = json.loads(row.get("score_json") or "{}")
                row["curation_metadata"] = json.loads(row.get("curation_metadata_json") or "{}")
                row["asr_metadata"] = json.loads(row.get("asr_metadata_json") or "{}")
                row["render_quality"] = json.loads(row.get("render_quality_json") or "{}")
                row["cost"] = json.loads(row.get("cost_json") or "{}")
                row["post_caption"] = build_post_caption(row, {"metadata_json": row.get("render_metadata_json") or "{}"})
            rows.sort(key=lambda row: row.get("score", {}).get("overall_score", 0), reverse=True)
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
        if parsed.path == "/api/credentials":
            load_env_file(ROOT.parent / ".env.local")
            self._send_json(credential_status())
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

        if parsed.path == "/api/publish-live":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            platform = str(payload.get("platform", "")).strip()
            dry_run = bool(payload.get("dry_run", True))
            if not candidate_id or not platform:
                self._send_json({"error": "candidate_id and platform are required"}, status=400)
                return
            load_env_file(ROOT.parent / ".env.local")
            conn = connect(DEFAULT_DB)
            initialize(conn)
            candidate = conn.execute("SELECT * FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
            if not candidate:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            candidate = dict(candidate)
            source = conn.execute("SELECT * FROM source_manifests WHERE id = ?", (candidate["source_id"],)).fetchone()
            target = conn.execute(
                "SELECT * FROM publish_targets WHERE profile_id = ? AND platform = ?",
                (candidate["profile_id"], platform),
            ).fetchone()
            render_job = conn.execute(
                "SELECT * FROM render_jobs WHERE candidate_id = ? ORDER BY created_at DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()
            if not source or not target:
                self._send_json({"error": "source or publish target not found"}, status=404)
                return
            attempt = create_dry_run_attempt(
                conn,
                dict(source),
                dict(target),
                candidate,
                dict(render_job) if render_job else None,
            )
            if attempt["status"] != "ready":
                self._send_json({"attempt": attempt, "error": attempt["error"]}, status=409)
                return
            built_payload = build_payload(platform, candidate, dict(render_job) if render_job else None)
            if dry_run:
                self._send_json({"status": "dry_run", "attempt": attempt, "payload": built_payload})
                return
            if platform != "telegram_channel":
                self._send_json({"error": "live publishing is currently enabled for telegram_channel only"}, status=400)
                return
            try:
                result = publish_telegram_video(built_payload)
            except LivePublishError as exc:
                self._send_json({"error": str(exc), "attempt": attempt}, status=502)
                return
            conn.execute(
                "UPDATE publish_attempts SET status = ?, payload_json = ? WHERE id = ?",
                ("published", json.dumps({**built_payload, "live_result": result}, ensure_ascii=False), attempt["id"]),
            )
            conn.execute("UPDATE clip_candidates SET status = 'published' WHERE id = ?", (candidate_id,))
            conn.commit()
            self._send_json(result)
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
