#!/usr/bin/env python3
"""Small local review server for the V1 UI shell."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .autonomy import get_autonomy_settings, update_autonomy_settings
from .caption_edits import merge_caption_corrections
from .db import ARTIFACTS_DIR, DEFAULT_DB, ROOT, connect, fetch_all, initialize
from .credentials import credential_status
from .duration_presets import duration_preset_options
from .env_loader import load_env_file
from .generation_jobs import create_generation_job, list_brand_templates, list_generation_jobs
from .genres import genre_options
from .live_publishers import LivePublishError, publish_telegram_video
from .models import PUBLISH_MODES
from .post_copy import build_post_caption
from .publishers import build_payload, create_dry_run_attempt
from .rerender import create_rerender_job, list_rerender_jobs
from .scheduler import list_scheduled_posts, process_due_auto_schedule, schedule_candidate_next, unschedule_candidate, update_schedule
from .styles import load_style, save_style_template


def _artifact_path(value: str) -> Path | None:
    if not value:
        return None
    requested = Path(value).resolve()
    root = ARTIFACTS_DIR.resolve()
    if requested == root or root not in requested.parents:
        return None
    return requested


def _delete_candidate_artifacts(paths: list[str]) -> list[str]:
    removed: set[str] = set()
    for value in paths:
        artifact = _artifact_path(value)
        if not artifact:
            continue
        root = ARTIFACTS_DIR.resolve()
        try:
            relative = artifact.relative_to(root)
        except ValueError:
            continue
        target = root / relative.parts[0] / relative.parts[1] if len(relative.parts) >= 3 else artifact
        if not target.exists() or str(target) in removed:
            continue
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        removed.add(str(target))
    return sorted(removed)


def _loads(value: str | None, fallback):
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def _parse_range_header(value: str, size: int) -> tuple[int, int] | None:
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or size <= 0:
        return None
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else size - 1
    else:
        suffix = int(end_text)
        if suffix <= 0:
            return None
        start = max(size - suffix, 0)
        end = size - 1
    if start >= size:
        return None
    end = min(end, size - 1)
    if start > end:
        return None
    return start, end


class ReviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/review":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            process_due_auto_schedule(conn)
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
                WHERE c.status != 'archived'
                ORDER BY c.created_at DESC
                """,
            )
            for row in rows:
                row["score"] = _loads(row.get("score_json"), {})
                row["curation_metadata"] = _loads(row.get("curation_metadata_json"), {})
                row["asr_metadata"] = _loads(row.get("asr_metadata_json"), {})
                row["render_quality"] = _loads(row.get("render_quality_json"), {})
                row["cost"] = _loads(row.get("cost_json"), {})
                row["quality_gate"] = _loads(row.get("quality_gate_json"), {})
                row["caption_corrections"] = _loads(row.get("caption_corrections_json"), {})
                row["render_metadata"] = _loads(row.get("render_metadata_json"), {})
                row["captions"] = row["caption_corrections"].get("edited_captions") or row["render_metadata"].get("captions") or []
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
            query = parse_qs(parsed.query)
            try:
                self._send_json(load_style(query.get("path", [""])[0] or None))
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        if parsed.path == "/api/brand-templates":
            self._send_json(list_brand_templates())
            return
        if parsed.path == "/api/genres":
            self._send_json(genre_options())
            return
        if parsed.path == "/api/duration-presets":
            self._send_json(duration_preset_options())
            return
        if parsed.path == "/api/generation-jobs":
            self._send_json(list_generation_jobs())
            return
        if parsed.path == "/api/rerender-jobs":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["40"])[0] or 40)
            except ValueError:
                limit = 40
            self._send_json(
                list_rerender_jobs(
                    limit=max(1, min(100, limit)),
                    candidate_id=(query.get("candidate_id", [""])[0] or "").strip() or None,
                )
            )
            return
        if parsed.path == "/api/autonomy-settings":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            self._send_json(get_autonomy_settings(conn))
            return
        if parsed.path == "/api/schedule":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            process_due_auto_schedule(conn)
            self._send_json(list_scheduled_posts(conn))
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
            content_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
            file_size = requested.stat().st_size
            range_header = self.headers.get("Range", "").strip()
            byte_range = _parse_range_header(range_header, file_size) if range_header else None
            status = 206 if byte_range else 200
            start = byte_range[0] if byte_range else 0
            end = byte_range[1] if byte_range else file_size - 1
            length = max(0, end - start + 1)
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Content-Disposition", f'inline; filename="{requested.name}"')
            if byte_range:
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.end_headers()
            with requested.open("rb") as handle:
                handle.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = handle.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
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
            result = conn.execute("UPDATE clip_candidates SET status = 'approved', review_deadline_at = '' WHERE id = ?", (candidate_id,))
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            self._send_json({"candidate_id": candidate_id, "status": "approved"})
            return

        if parsed.path == "/api/hold":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            result = conn.execute("UPDATE clip_candidates SET status = 'held', review_deadline_at = '' WHERE id = ?", (candidate_id,))
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            self._send_json({"candidate_id": candidate_id, "status": "held"})
            return

        if parsed.path == "/api/reject":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            result = conn.execute("UPDATE clip_candidates SET status = 'rejected', review_deadline_at = '' WHERE id = ?", (candidate_id,))
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            self._send_json({"candidate_id": candidate_id, "status": "rejected"})
            return

        if parsed.path == "/api/autonomy-settings":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                settings = update_autonomy_settings(conn, str(payload.get("profile_id") or "nourbit"), payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(settings)
            return

        if parsed.path == "/api/generation-jobs":
            try:
                job = create_generation_job(payload, start=True)
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(job, status=202)
            return

        if parsed.path == "/api/brand-template":
            label = str(payload.get("label") or "").strip()
            style = payload.get("style")
            if not isinstance(style, dict):
                self._send_json({"error": "style is required"}, status=400)
                return
            try:
                template = save_style_template(label, style, str(payload.get("base_template") or "") or None)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(template, status=201)
            return

        if parsed.path == "/api/caption-corrections":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            captions = payload.get("captions")
            if not candidate_id or not isinstance(captions, list):
                self._send_json({"error": "candidate_id and captions are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            candidate = conn.execute(
                "SELECT status, caption_corrections_json FROM clip_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            try:
                corrections = merge_caption_corrections(
                    _loads(candidate["caption_corrections_json"], {}),
                    captions,
                )
            except (TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            next_status = candidate["status"]
            if next_status not in {"approved", "scheduled", "ready_to_publish", "published"}:
                next_status = "held"
            conn.execute(
                """
                UPDATE clip_candidates
                SET caption_corrections_json = ?, caption_source = 'manual_edit',
                    status = ?, review_deadline_at = ''
                WHERE id = ?
                """,
                (json.dumps(corrections, ensure_ascii=False), next_status, candidate_id),
            )
            conn.commit()
            self._send_json({"candidate_id": candidate_id, "status": next_status, "caption_corrections": corrections})
            return

        if parsed.path == "/api/rerender":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            try:
                result = create_rerender_job(
                    candidate_id,
                    renderer=str(payload.get("renderer") or "remotion"),
                    quality=str(payload.get("quality") or "production"),
                    style_path=str(payload.get("style") or "") or None,
                )
            except (RuntimeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result, status=202)
            return

        if parsed.path == "/api/schedule-next":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = schedule_candidate_next(conn, candidate_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/schedule-update":
            schedule_id = str(payload.get("schedule_id", "")).strip()
            scheduled_at = str(payload.get("scheduled_at", "")).strip()
            if not schedule_id or not scheduled_at:
                self._send_json({"error": "schedule_id and scheduled_at are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = update_schedule(conn, schedule_id, scheduled_at)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/unschedule":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = unschedule_candidate(conn, candidate_id)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/archive":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            result = conn.execute("UPDATE clip_candidates SET status = 'archived' WHERE id = ?", (candidate_id,))
            conn.commit()
            if result.rowcount == 0:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            self._send_json({"candidate_id": candidate_id, "status": "archived"})
            return

        if parsed.path == "/api/delete-candidate":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            delete_artifacts = bool(payload.get("delete_artifacts", True))
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            candidate = conn.execute("SELECT id FROM clip_candidates WHERE id = ?", (candidate_id,)).fetchone()
            if not candidate:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            paths = [
                row["output_path"]
                for row in conn.execute("SELECT output_path FROM render_jobs WHERE candidate_id = ?", (candidate_id,))
                if row["output_path"]
            ]
            conn.execute("DELETE FROM publish_attempts WHERE candidate_id = ?", (candidate_id,))
            conn.execute("DELETE FROM render_jobs WHERE candidate_id = ?", (candidate_id,))
            conn.execute("DELETE FROM clip_candidates WHERE id = ?", (candidate_id,))
            conn.commit()
            removed = _delete_candidate_artifacts(paths) if delete_artifacts else []
            self._send_json({"candidate_id": candidate_id, "deleted": True, "artifacts_removed": removed})
            return

        if parsed.path == "/api/clear-review":
            confirm = str(payload.get("confirm", "")).strip()
            delete_artifacts = bool(payload.get("delete_artifacts", True))
            if confirm != "DELETE":
                self._send_json({"error": "confirm must be DELETE"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            paths = [
                row["output_path"]
                for row in conn.execute("SELECT output_path FROM render_jobs WHERE output_path != ''")
                if row["output_path"]
            ]
            counts = {
                "clip_candidates": conn.execute("SELECT count(*) FROM clip_candidates").fetchone()[0],
                "render_jobs": conn.execute("SELECT count(*) FROM render_jobs").fetchone()[0],
                "publish_attempts": conn.execute("SELECT count(*) FROM publish_attempts").fetchone()[0],
            }
            conn.execute("DELETE FROM publish_attempts")
            conn.execute("DELETE FROM render_jobs")
            conn.execute("DELETE FROM clip_candidates")
            conn.commit()
            removed = _delete_candidate_artifacts(paths) if delete_artifacts else []
            self._send_json({"deleted": counts, "artifacts_removed": removed})
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
    port = int(os.environ.get("MEDIA_ENGINE_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    print(f"review UI: http://127.0.0.1:{port}/review.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
