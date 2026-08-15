#!/usr/bin/env python3
"""Small local review server for the V1 UI shell."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
import sqlite3
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .autonomy import MANUAL_HOLD_REASON, get_autonomy_settings, reconcile_caption_holds, update_autonomy_settings
from .caption_edits import merge_caption_corrections
from .clip_boundaries import update_clip_boundary
from .db import ARTIFACTS_DIR, DEFAULT_DB, DEFAULT_WORKSPACE_PROFILE_ID, ROOT, connect, fetch_all, fetch_one, initialize
from .silence_trim import captions_duration_ms, remove_pause_from_captions, remove_pauses_batch_from_captions, word_pause_gaps
from .credentials import credential_status
from .credential_vault import ensure_default_migration, set_profile_secrets, unset_profile_secrets
from .duration_presets import duration_preset_options
from .env_loader import load_env_file
from .explainer_pipeline import (
    create_explainer_job,
    list_explainer_jobs,
    read_explainer_status,
    resolve_explainer_review_candidate,
    save_explainer_scene_plan,
    start_explainer_run,
)
from .ingest_longform import ingest_longform
from .path_a_jobs import list_path_a_jobs, read_path_a_status, start_path_a_generate
from .cursor_cloud import CursorCloudError
from .generation_jobs import create_generation_job, list_brand_templates, list_generation_jobs
from .genres import genre_catalog
from .source_resolve import resolve_youtube_source
from .review_grouping import enrich_review_rows_with_source
from .hyperframes_catalog import list_hyperframes_catalog
from .hyperframes_previews import ensure_hyperframes_template_preview, list_hyperframes_preview_status, prewarm_hyperframes_template_previews
from .hyperframes_renderer import check_hyperframes_runtime
from .hyperframes_templates import list_hyperframes_templates
from .live_publishers import (
    LivePublishError,
    publish_live_payload,
    validate_platform_connection,
)
from .llm import LLMError
from .models import PUBLISH_MODES
from .metadata_refresh import refresh_candidate_metadata
from .oauth_flow import OAuthFlowError, complete_oauth, start_oauth
from .post_copy import build_post_caption, generate_post_caption, sanitize_post_caption
from .publishers import build_payload, create_dry_run_attempt
from .rerender import create_rerender_job, list_rerender_jobs
from .schedule_publisher import archive_legacy_permission_attempts, process_due_publishes
from .channel_watcher import (
    add_watch_channel,
    delete_watch_channel,
    list_media_profiles,
    list_publish_targets,
    list_watch_channels,
    poll_due_watch_channels,
    poll_watch_channel,
    update_publish_target,
    update_watch_channel,
    upsert_publish_target,
)
from .workspace_profiles import (
    WorkspaceProfileError,
    create_profile,
    delete_profile,
    profile_usage,
    update_profile,
)
from .scheduler import (
    list_scheduled_posts,
    process_due_auto_schedule,
    process_due_auto_schedule_all,
    schedule_candidate_next,
    unschedule_candidate,
    update_schedule,
    update_schedule_platforms,
)
from .styles import load_style, save_brand_system_template, save_style_template


ENV_FILE = ROOT.parent / ".env.local"
PLATFORM_DISCONNECT_KEYS: dict[str, list[str]] = {
    "telegram_channel": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID", "TELEGRAM_CHAT_ID"],
    "youtube_shorts": ["YOUTUBE_REFRESH_TOKEN"],
    "facebook_reels": ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID", "NOURBIT_FACEBOOK_PAGE_TOKEN", "NOURBIT_FACEBOOK_PAGE_ID"],
    "tiktok": ["TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "TIKTOK_OPEN_ID"],
}


def _safe_load_env() -> None:
    if ENV_FILE.exists():
        load_env_file(ENV_FILE)
    ensure_default_migration(ENV_FILE if ENV_FILE.exists() else None)


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


def _active_clip_duration_ms(
    *,
    captions: list,
    candidate_row,
    render_meta: dict,
) -> int:
    """Timeline used for Remove Pause planning: current media, not original YouTube span.

    After auto-trim / prior Remove Pause, captions and the working source are shorter than
    ``end_ms - start_ms``. Using max(original_span, …) made keep plans extend past the
    source so forced A/V cuts were skipped (``changed=False``).
    """
    caption_ms = captions_duration_ms(captions) if isinstance(captions, list) else 0
    rq = _loads(candidate_row["render_quality_json"], {})
    if not isinstance(rq, dict):
        rq = {}
    trim = rq.get("silence_trim") if isinstance(rq.get("silence_trim"), dict) else {}
    trim_ms = int(trim.get("duration_after_ms") or 0)
    rq_ms = int(rq.get("duration_ms") or 0)
    source_ms = 0
    source_path = str(render_meta.get("sourceVideoPath") or "").strip()
    if source_path and Path(source_path).exists():
        try:
            from .silence_trim import probe_duration_ms

            source_ms = probe_duration_ms(source_path)
        except Exception:  # noqa: BLE001 - fall back to caption/trim estimates
            source_ms = 0
    positives = [ms for ms in (caption_ms, trim_ms, source_ms, rq_ms) if ms > 0]
    if positives:
        return int(min(positives))
    return max(0, int(candidate_row["end_ms"] or 0) - int(candidate_row["start_ms"] or 0))


def _normalize_clip_status(row: dict) -> dict:
    status = str(row.get("status") or "")
    if status == "needs_caption_fix":
        row["status"] = "held"
        metadata = _loads(row.get("curation_metadata_json"), {})
        metadata["hold_reason"] = metadata.get("hold_reason") or "caption_fix_required"
        row["curation_metadata_json"] = json.dumps(metadata, ensure_ascii=False)
    return row


def get_editor_context(candidate_id: str, *, db_path: str | Path = DEFAULT_DB) -> dict:
    candidate_id = str(candidate_id or "").strip()
    if not candidate_id:
        raise ValueError("candidate_id is required")
    conn = connect(db_path)
    initialize(conn)
    row = conn.execute(
        """
        SELECT c.id, c.profile_id, c.status, c.caption_source, c.curation_metadata_json,
               r.status AS render_status, r.metadata_json AS render_metadata_json
        FROM clip_candidates c
        LEFT JOIN render_jobs r ON r.id = (
          SELECT r2.id FROM render_jobs r2
          WHERE r2.candidate_id = c.id
          ORDER BY r2.created_at DESC, r2.id DESC
          LIMIT 1
        )
        WHERE c.id = ?
        """,
        (candidate_id,),
    ).fetchone()
    if not row:
        raise FileNotFoundError("candidate not found")
    candidate = dict(row)
    metadata = _loads(candidate.get("curation_metadata_json"), {})
    if not isinstance(metadata, dict):
        metadata = {}
    render_metadata = _loads(candidate.get("render_metadata_json"), {})
    if not isinstance(render_metadata, dict):
        render_metadata = {}
    kind = str(metadata.get("kind") or "")
    published = candidate["status"] == "published"
    context = {
        "candidate_id": candidate_id,
        "profile_id": candidate["profile_id"],
        "capability": "short",
        "can_edit_scenes": False,
        "can_trim": not published,
        "can_rerender": not published,
        "render": {
            "status": candidate.get("render_status") or candidate["status"],
            "error": str(render_metadata.get("error") or ""),
        },
    }
    if kind == "explainer":
        resolved = resolve_explainer_review_candidate(candidate_id, db_path=db_path)
        status = _loads(resolved["status_path"].read_text(encoding="utf-8"), {})
        if not isinstance(status, dict):
            status = {}
        context.update(
            {
                "capability": "scene",
                "can_edit_scenes": not published,
                "can_trim": False,
                "plan": resolved["plan"],
                "job": {
                    "job_id": resolved["job_id"],
                    "status": str(status.get("status") or "planned"),
                    "error": str(status.get("error") or ""),
                    "hyperframes_template": str(
                        status.get("hyperframes_template")
                        or resolved["plan"].get("hyperframes_template")
                        or ""
                    ),
                },
                "render": {
                    "status": str(status.get("status") or "planned"),
                    "error": str(status.get("error") or ""),
                },
            }
        )
    elif kind == "longform_ingest" or candidate["caption_source"] == "ingest_longform":
        context.update(
            {
                "capability": "imported_longform",
                "can_trim": False,
                "can_rerender": False,
            }
        )
    else:
        # Short-form: surface active/latest async re-render so the editor can poll.
        rerender = conn.execute(
            """
            SELECT id, status, error, progress, message
            FROM rerender_jobs
            WHERE candidate_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        if rerender:
            context["job"] = {
                "job_id": rerender["id"],
                "status": str(rerender["status"] or ""),
                "error": str(rerender["error"] or ""),
                "progress": int(rerender["progress"] or 0),
                "message": str(rerender["message"] or ""),
            }
            if str(rerender["status"] or "") in {"queued", "running"}:
                context["render"] = {
                    "status": str(rerender["status"]),
                    "error": str(rerender["error"] or ""),
                }
    return context


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
        if parsed.path.startswith("/api/oauth/callback/"):
            platform = parsed.path.rsplit("/", 1)[-1].strip()
            query = {key: values[0] for key, values in parse_qs(parsed.query).items() if values}
            host, port = self.server.server_address  # type: ignore[attr-defined]
            server_base = f"http://{host}:{port}"
            try:
                result = complete_oauth(platform, query, server_base, ENV_FILE)
            except OAuthFlowError as exc:
                self._send_html(
                    f"<h2>Connect failed</h2><p>{escape(str(exc))}</p><p>You can close this tab and retry from Channels.</p>",
                    status=400,
                )
                return
            except Exception as exc:  # noqa: BLE001
                self._send_html(
                    f"<h2>Connect failed</h2><p>{escape(str(exc))}</p><p>You can close this tab and retry from Channels.</p>",
                    status=500,
                )
                return
            self._send_html(
                f"<h2>Connected</h2><p>{escape(platform)} account is connected.</p>"
                "<script>setTimeout(()=>window.close(), 1200);</script>",
            )
            return
        if parsed.path == "/api/review":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            reconcile_caption_holds(conn)
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
                _normalize_clip_status(row)
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
            enrich_review_rows_with_source(conn, rows)
            rows.sort(key=lambda row: row.get("score", {}).get("overall_score", 0), reverse=True)
            payload = json.dumps(rows, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path == "/api/editor-context":
            candidate_id = (parse_qs(parsed.query).get("candidate_id", [""])[0] or "").strip()
            try:
                self._send_json(get_editor_context(candidate_id, db_path=DEFAULT_DB))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        if parsed.path == "/api/targets":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", [""])[0] or "").strip() or None
            self._send_json(list_publish_targets(conn, profile_id=profile_id))
            return
        if parsed.path == "/api/profiles":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            self._send_json({"profiles": list_media_profiles(conn)})
            return
        if parsed.path == "/api/watch-channels":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", [""])[0] or "").strip() or None
            self._send_json({"channels": list_watch_channels(conn, profile_id=profile_id)})
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
        if parsed.path == "/api/hyperframes-templates":
            self._send_json(list_hyperframes_templates())
            return
        if parsed.path == "/api/hyperframes-catalog":
            self._send_json(list_hyperframes_catalog())
            return
        if parsed.path == "/api/hyperframes-template-preview":
            query = parse_qs(parsed.query)
            template_id = (query.get("template", ["auto"])[0] or "auto").strip()
            hyperframes_format = (query.get("format", ["short_9_16"])[0] or "short_9_16").strip()
            try:
                preview = ensure_hyperframes_template_preview(template_id, hyperframes_format)
            except (RuntimeError, ValueError, OSError) as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_media_file(preview)
            return
        if parsed.path == "/api/hyperframes-template-preview-status":
            query = parse_qs(parsed.query)
            include_brand = (query.get("include_brand", ["1"])[0] or "1") not in {"0", "false", "False"}
            self._send_json(list_hyperframes_preview_status(include_brand=include_brand))
            return
        if parsed.path == "/api/genres":
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", [DEFAULT_WORKSPACE_PROFILE_ID])[0] or DEFAULT_WORKSPACE_PROFILE_ID).strip()
            conn = connect(DEFAULT_DB)
            initialize(conn)
            row = fetch_one(conn, "SELECT niche FROM media_profiles WHERE id = ?", (profile_id,))
            niche = str((row or {}).get("niche") or "")
            self._send_json(genre_catalog(profile_id=profile_id, niche=niche))
            return
        if parsed.path == "/api/duration-presets":
            self._send_json(duration_preset_options())
            return
        if parsed.path == "/api/engine-health":
            load_env_file(ENV_FILE)
            self._send_json({"hyperframes": check_hyperframes_runtime(run_doctor=False)})
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
        if parsed.path == "/api/explainers":
            query = parse_qs(parsed.query)
            profile_id = query.get("profile_id", [DEFAULT_WORKSPACE_PROFILE_ID])[0] or DEFAULT_WORKSPACE_PROFILE_ID
            try:
                limit = int(query.get("limit", ["20"])[0] or 20)
            except ValueError:
                limit = 20
            self._send_json({"jobs": list_explainer_jobs(profile_id=profile_id, limit=max(1, min(limit, 100)))})
            return
        if parsed.path == "/api/path-a-jobs":
            query = parse_qs(parsed.query)
            profile_id = query.get("profile_id", [DEFAULT_WORKSPACE_PROFILE_ID])[0] or DEFAULT_WORKSPACE_PROFILE_ID
            try:
                limit = int(query.get("limit", ["20"])[0] or 20)
            except ValueError:
                limit = 20
            self._send_json({"jobs": list_path_a_jobs(profile_id=profile_id, limit=max(1, min(limit, 100)))})
            return
        if parsed.path == "/api/path-a-status":
            query = parse_qs(parsed.query)
            job_id = (query.get("job_id", [""])[0] or "").strip()
            profile_id = query.get("profile_id", [DEFAULT_WORKSPACE_PROFILE_ID])[0] or DEFAULT_WORKSPACE_PROFILE_ID
            if not job_id:
                self._send_json({"error": "job_id is required"}, status=400)
                return
            try:
                self._send_json(read_path_a_status(job_id, profile_id=profile_id))
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        if parsed.path == "/api/explainer-status":
            query = parse_qs(parsed.query)
            job_id = (query.get("job_id", [""])[0] or "").strip()
            profile_id = query.get("profile_id", [DEFAULT_WORKSPACE_PROFILE_ID])[0] or DEFAULT_WORKSPACE_PROFILE_ID
            if not job_id:
                self._send_json({"error": "job_id is required"}, status=400)
                return
            try:
                self._send_json(read_explainer_status(job_id, profile_id=profile_id))
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return
        if parsed.path == "/api/autonomy-settings":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", ["nourbit"])[0] or "nourbit").strip() or "nourbit"
            self._send_json(get_autonomy_settings(conn, profile_id))
            return
        if parsed.path == "/api/schedule":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", [""])[0] or "").strip()
            if profile_id:
                process_due_auto_schedule(conn, profile_id=profile_id)
                self._send_json(list_scheduled_posts(conn, profile_id=profile_id))
            else:
                process_due_auto_schedule_all(conn)
                # Default list still uses nourbit for backward compatibility when no profile filter.
                self._send_json(list_scheduled_posts(conn))
            return
        if parsed.path == "/api/watch-poll":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", [""])[0] or "").strip() or None
            force = (query.get("force", ["0"])[0] or "0") in {"1", "true", "True"}
            try:
                results = poll_due_watch_channels(conn, profile_id=profile_id, force=force)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=500)
                return
            self._send_json({"results": results})
            return
        if parsed.path == "/api/resolve-source":
            query = parse_qs(parsed.query)
            raw_url = (query.get("url", [""])[0] or "").strip()
            if not raw_url:
                self._send_json({"error": "url is required", "ok": False}, status=400)
                return
            try:
                self._send_json(resolve_youtube_source(raw_url))
            except ValueError as exc:
                self._send_json({"error": str(exc), "ok": False}, status=400)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc), "ok": False}, status=502)
            return
        if parsed.path == "/api/publish-attempts":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            archive_legacy_permission_attempts(conn)
            rows = fetch_all(
                conn,
                """
                SELECT * FROM publish_attempts
                WHERE status != 'legacy_blocked'
                ORDER BY created_at DESC
                LIMIT 80
                """,
            )
            for row in rows:
                row["payload"] = _loads(row.get("payload_json"), {})
            self._send_json(rows)
            return
        if parsed.path == "/api/credentials":
            _safe_load_env()
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", ["nourbit"])[0] or "nourbit").strip() or "nourbit"
            self._send_json(credential_status(profile_id))
            return
        if parsed.path == "/api/connections":
            _safe_load_env()
            query = parse_qs(parsed.query)
            profile_id = (query.get("profile_id", ["nourbit"])[0] or "nourbit").strip() or "nourbit"
            credentials = credential_status(profile_id)
            conn = connect(DEFAULT_DB)
            initialize(conn)
            profile_targets = list_publish_targets(conn, profile_id=profile_id)
            self._send_json({
                "profile_id": profile_id,
                "platforms": credentials["platforms"],
                "targets": profile_targets,
                "auth": {
                    "telegram_channel": {"mode": "bot_token", "action": "configure_token", "disconnect_supported": True},
                    "youtube_shorts": {"mode": "oauth", "action": "connect", "disconnect_supported": True},
                    "facebook_reels": {"mode": "oauth", "action": "connect", "disconnect_supported": True},
                    "tiktok": {"mode": "oauth", "action": "connect", "disconnect_supported": True},
                },
            })
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
            row = conn.execute(
                "SELECT curation_metadata_json FROM clip_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if not row:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            metadata = _loads(row["curation_metadata_json"], {})
            metadata["hold_reason"] = MANUAL_HOLD_REASON
            conn.execute(
                """
                UPDATE clip_candidates
                SET status = 'held', review_deadline_at = '', curation_metadata_json = ?
                WHERE id = ?
                """,
                (json.dumps(metadata, ensure_ascii=False), candidate_id),
            )
            conn.commit()
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

        if parsed.path == "/api/profiles":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                profile = create_profile(conn, payload)
            except WorkspaceProfileError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json({"profile": profile, "profiles": list_media_profiles(conn)}, status=201)
            return

        if parsed.path == "/api/profile-update":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                profile = update_profile(conn, payload)
            except WorkspaceProfileError as exc:
                message = str(exc)
                status = 404 if "not found" in message.lower() else 400
                self._send_json({"error": message}, status=status)
                return
            self._send_json({"profile": profile, "profiles": list_media_profiles(conn)})
            return

        if parsed.path == "/api/profile-delete":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            profile_id = str(payload.get("id") or payload.get("profile_id") or "").strip()
            usage = profile_usage(conn, profile_id) if profile_id else {}
            try:
                result = delete_profile(conn, payload)
            except WorkspaceProfileError as exc:
                message = str(exc)
                status = 404 if "not found" in message.lower() else 400
                if "force=true" in message.lower() or "still has" in message.lower():
                    status = 409
                self._send_json({"error": message, "usage": usage}, status=status)
                return
            self._send_json({**result, "profiles": list_media_profiles(conn)})
            return

        if parsed.path == "/api/generation-jobs":
            load_env_file(ENV_FILE)
            try:
                job = create_generation_job(payload, start=True)
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            except sqlite3.Error as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_json(job, status=202)
            return

        if parsed.path == "/api/explainers":
            topic = str(payload.get("topic") or "").strip()
            if not topic:
                self._send_json({"error": "topic is required"}, status=400)
                return
            sources_raw = payload.get("sources") or []
            if isinstance(sources_raw, str):
                sources = [line.strip() for line in sources_raw.splitlines() if line.strip()]
            elif isinstance(sources_raw, list):
                sources = [str(item).strip() for item in sources_raw if str(item).strip()]
            else:
                sources = []
            profile_id = str(payload.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID).strip() or DEFAULT_WORKSPACE_PROFILE_ID
            try:
                created = create_explainer_job(
                    topic=topic,
                    sources=sources or None,
                    profile_id=profile_id,
                    llm_provider=str(payload.get("llm_provider") or "none"),
                    language=str(payload.get("language") or "id"),
                    hyperframes_template=str(payload.get("hyperframes_template") or "techtalk_explainer"),
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(created, status=201)
            return

        if parsed.path == "/api/explainer-run":
            job_id = str(payload.get("job_id") or "").strip()
            if not job_id:
                self._send_json({"error": "job_id is required"}, status=400)
                return
            profile_id = str(payload.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID).strip() or DEFAULT_WORKSPACE_PROFILE_ID
            prefer_hyperframes = not bool(payload.get("ffmpeg_only", True))
            if "prefer_hyperframes" in payload:
                prefer_hyperframes = bool(payload.get("prefer_hyperframes"))
            try:
                status = start_explainer_run(
                    job_id=job_id,
                    profile_id=profile_id,
                    prefer_hyperframes=prefer_hyperframes,
                )
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except (OSError, ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(status, status=202)
            return

        if parsed.path == "/api/explainer-scene-plan":
            candidate_id = str(payload.get("candidate_id") or "").strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            if "title" not in payload or "scenes" not in payload:
                self._send_json({"error": "title and scenes are required"}, status=400)
                return
            try:
                saved = save_explainer_scene_plan(
                    candidate_id,
                    title=payload.get("title"),
                    scenes=payload.get("scenes"),
                    rerender_after=bool(payload.get("rerender_after", False)),
                    prefer_hyperframes=bool(payload.get("prefer_hyperframes", False)),
                    db_path=DEFAULT_DB,
                )
                context = get_editor_context(candidate_id, db_path=DEFAULT_DB)
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except (OSError, TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            context["rerender_started"] = saved["rerender_started"]
            self._send_json(context, status=202 if saved["rerender_started"] else 200)
            return

        if parsed.path == "/api/ingest-longform":
            source = str(payload.get("source") or "").strip()
            if not source:
                self._send_json({"error": "source is required"}, status=400)
                return
            mode = str(payload.get("mode") or "review_only").strip() or "review_only"
            profile_id = str(payload.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID).strip() or DEFAULT_WORKSPACE_PROFILE_ID
            try:
                result = ingest_longform(
                    source=source,
                    mode=mode,  # type: ignore[arg-type]
                    title=str(payload.get("title") or "").strip(),
                    profile_id=profile_id,
                    count=int(payload.get("count") or 5),
                    language=str(payload.get("language") or "id"),
                )
            except FileNotFoundError as exc:
                self._send_json({"error": str(exc)}, status=404)
                return
            except (OSError, ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result, status=201)
            return

        if parsed.path == "/api/path-a-generate":
            topic = str(payload.get("topic") or "").strip()
            if not topic:
                self._send_json({"error": "topic is required"}, status=400)
                return
            profile_id = str(payload.get("profile_id") or DEFAULT_WORKSPACE_PROFILE_ID).strip() or DEFAULT_WORKSPACE_PROFILE_ID
            load_env_file(ENV_FILE)
            try:
                created = start_path_a_generate(
                    topic=topic,
                    title=str(payload.get("title") or "").strip(),
                    script=str(payload.get("script") or "").strip(),
                    profile_id=profile_id,
                )
            except (CursorCloudError, ValueError, OSError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(created, status=202)
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

        if parsed.path == "/api/brand-system-templates":
            label = str(payload.get("label") or "").strip()
            style = payload.get("style")
            brand_system = payload.get("brand_system")
            if not isinstance(style, dict):
                self._send_json({"error": "style is required"}, status=400)
                return
            if not isinstance(brand_system, dict):
                self._send_json({"error": "brand_system is required"}, status=400)
                return
            try:
                template = save_brand_system_template(
                    label,
                    style,
                    brand_system,
                    str(payload.get("base_template") or "") or None,
                    target_path=str(payload.get("path") or payload.get("target_path") or "") or None,
                )
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(template, status=201)
            return

        if parsed.path == "/api/hyperframes-template-preview-prewarm":
            include_brand = bool(payload.get("include_brand", False))
            try:
                result = prewarm_hyperframes_template_previews(include_brand=include_brand)
            except RuntimeError as exc:
                self._send_json({"error": str(exc)}, status=503)
                return
            self._send_json(result)
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

        if parsed.path == "/api/remove-pause":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            pause_at_ms = int(payload.get("pause_at_ms") or 0)
            gap_ms = int(payload.get("gap_ms") or 0)
            rerender_after = bool(payload.get("rerender_after", True))
            if not candidate_id or gap_ms < 40:
                self._send_json({"error": "candidate_id and gap_ms (>=40) are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            row = conn.execute(
                """
                SELECT c.*, r.metadata_json AS render_metadata_json
                FROM clip_candidates c
                LEFT JOIN render_jobs r ON r.id = (
                  SELECT r2.id FROM render_jobs r2
                  WHERE r2.candidate_id = c.id
                  ORDER BY r2.created_at DESC, r2.id DESC LIMIT 1
                )
                WHERE c.id = ?
                """,
                (candidate_id,),
            ).fetchone()
            if not row:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            if row["status"] == "published":
                self._send_json({"error": "published clip is locked"}, status=400)
                return

            corrections = _loads(row["caption_corrections_json"], {})
            render_meta = _loads(row["render_metadata_json"], {})
            captions = corrections.get("edited_captions") or render_meta.get("captions") or []
            if not isinstance(captions, list) or not captions:
                self._send_json({"error": "no captions available to retiming"}, status=400)
                return

            duration_ms = _active_clip_duration_ms(
                captions=captions,
                candidate_row=row,
                render_meta=render_meta,
            )
            try:
                keep_segments, remapped = remove_pause_from_captions(captions, duration_ms, pause_at_ms, gap_ms)
            except (TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            if keep_segments == [(0, duration_ms)] or not remapped:
                self._send_json({"error": "pause window did not change the timeline"}, status=400)
                return

            try:
                next_corrections = merge_caption_corrections(corrections, remapped)
            except (TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            curation = _loads(row["curation_metadata_json"], {})
            cuts = list(curation.get("manual_silence_cuts") or [])
            cuts.append({"pause_at_ms": pause_at_ms, "gap_ms": gap_ms, "end_ms": pause_at_ms + gap_ms})
            curation["manual_silence_cuts"] = cuts
            curation["manual_silence_keep_segments"] = keep_segments

            next_status = row["status"]
            if next_status not in {"approved", "scheduled", "ready_to_publish", "published"}:
                next_status = "held"
            conn.execute(
                """
                UPDATE clip_candidates
                SET caption_corrections_json = ?, caption_source = 'manual_edit',
                    curation_metadata_json = ?, status = ?, review_deadline_at = ''
                WHERE id = ?
                """,
                (
                    json.dumps(next_corrections, ensure_ascii=False),
                    json.dumps(curation, ensure_ascii=False),
                    next_status,
                    candidate_id,
                ),
            )
            conn.commit()

            result = {
                "candidate_id": candidate_id,
                "status": next_status,
                "captions": remapped,
                "caption_corrections": next_corrections,
                "keep_segments": keep_segments,
                "removed_ms": max(0, gap_ms - 140),
                "curation_metadata": curation,
            }
            if rerender_after:
                load_env_file(ENV_FILE)
                try:
                    result["rerender_job"] = create_rerender_job(
                        candidate_id,
                        renderer=str(payload.get("renderer") or "hyperframes"),
                        quality=str(payload.get("quality") or "production"),
                        style_path=str(payload.get("style") or "") or None,
                        force_source_refresh=False,
                        regenerate_captions=False,
                    )
                except (RuntimeError, ValueError) as exc:
                    result["rerender_error"] = str(exc)
            self._send_json(result)
            return

        if parsed.path == "/api/remove-pauses-batch":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            min_gap_ms = int(payload.get("min_gap_ms") or 0)
            dry_run = bool(payload.get("dry_run", False))
            rerender_after = bool(payload.get("rerender_after", True))
            if not candidate_id or min_gap_ms < 40:
                self._send_json({"error": "candidate_id and min_gap_ms (>=40) are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            row = conn.execute(
                """
                SELECT c.*, r.metadata_json AS render_metadata_json
                FROM clip_candidates c
                LEFT JOIN render_jobs r ON r.id = (
                  SELECT r2.id FROM render_jobs r2
                  WHERE r2.candidate_id = c.id
                  ORDER BY r2.created_at DESC, r2.id DESC LIMIT 1
                )
                WHERE c.id = ?
                """,
                (candidate_id,),
            ).fetchone()
            if not row:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            if row["status"] == "published":
                self._send_json({"error": "published clip is locked"}, status=400)
                return

            corrections = _loads(row["caption_corrections_json"], {})
            render_meta = _loads(row["render_metadata_json"], {})
            captions = corrections.get("edited_captions") or render_meta.get("captions") or []
            if not isinstance(captions, list) or not captions:
                self._send_json({"error": "no captions available to retiming"}, status=400)
                return

            duration_ms = _active_clip_duration_ms(
                captions=captions,
                candidate_row=row,
                render_meta=render_meta,
            )
            gaps = word_pause_gaps(captions, min_gap_ms)
            preview = {
                "candidate_id": candidate_id,
                "min_gap_ms": min_gap_ms,
                "duration_ms": duration_ms,
                "match_count": len(gaps),
                "matches": gaps,
                "removable_ms": sum(max(0, int(gap["gap_ms"]) - 140) for gap in gaps),
            }
            if dry_run:
                self._send_json(preview)
                return
            if not gaps:
                self._send_json({"error": "no pauses at or above that threshold"}, status=400)
                return

            try:
                keep_segments, remapped, _gaps = remove_pauses_batch_from_captions(
                    captions, duration_ms, min_gap_ms
                )
            except (TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            if keep_segments == [(0, duration_ms)] or not remapped:
                self._send_json({"error": "pause windows did not change the timeline"}, status=400)
                return

            try:
                next_corrections = merge_caption_corrections(corrections, remapped)
            except (TypeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return

            curation = _loads(row["curation_metadata_json"], {})
            cuts = list(curation.get("manual_silence_cuts") or [])
            cuts.extend(gaps)
            curation["manual_silence_cuts"] = cuts
            curation["manual_silence_keep_segments"] = keep_segments
            curation["manual_silence_batch"] = {
                "min_gap_ms": min_gap_ms,
                "match_count": len(gaps),
            }

            next_status = row["status"]
            if next_status not in {"approved", "scheduled", "ready_to_publish", "published"}:
                next_status = "held"
            conn.execute(
                """
                UPDATE clip_candidates
                SET caption_corrections_json = ?, caption_source = 'manual_edit',
                    curation_metadata_json = ?, status = ?, review_deadline_at = ''
                WHERE id = ?
                """,
                (
                    json.dumps(next_corrections, ensure_ascii=False),
                    json.dumps(curation, ensure_ascii=False),
                    next_status,
                    candidate_id,
                ),
            )
            conn.commit()

            kept_ms = sum(end - start for start, end in keep_segments)
            result = {
                **preview,
                "status": next_status,
                "captions": remapped,
                "caption_corrections": next_corrections,
                "keep_segments": keep_segments,
                "removed_ms": max(0, duration_ms - kept_ms),
                "curation_metadata": curation,
            }
            if rerender_after:
                load_env_file(ENV_FILE)
                try:
                    result["rerender_job"] = create_rerender_job(
                        candidate_id,
                        renderer=str(payload.get("renderer") or "hyperframes"),
                        quality=str(payload.get("quality") or "production"),
                        style_path=str(payload.get("style") or "") or None,
                        force_source_refresh=False,
                        regenerate_captions=False,
                    )
                except (RuntimeError, ValueError) as exc:
                    result["rerender_error"] = str(exc)
            self._send_json(result)
            return

        if parsed.path == "/api/post-copy":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            post_caption = str(payload.get("post_caption", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            if not post_caption:
                self._send_json({"error": "post_caption is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            candidate = conn.execute(
                "SELECT status, curation_metadata_json FROM clip_candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if not candidate:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            if candidate["status"] == "published":
                self._send_json({"error": "published clip post copy is locked"}, status=400)
                return
            metadata = _loads(candidate["curation_metadata_json"], {})
            sanitized = sanitize_post_caption(post_caption)
            metadata["post_caption_override"] = sanitized
            metadata["post_caption_source"] = "manual_edit"
            conn.execute(
                """
                UPDATE clip_candidates
                SET curation_metadata_json = ?
                WHERE id = ?
                """,
                (json.dumps(metadata, ensure_ascii=False), candidate_id),
            )
            conn.commit()
            self._send_json({
                "candidate_id": candidate_id,
                "post_caption": sanitized,
                "char_count": len(sanitized),
            })
            return

        if parsed.path == "/api/post-copy-generate":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            preferred_provider = str(payload.get("llm_provider") or "").strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            load_env_file(ENV_FILE)
            conn = connect(DEFAULT_DB)
            initialize(conn)
            row = conn.execute(
                """
                SELECT cc.*, rj.metadata_json AS render_metadata_json
                FROM clip_candidates cc
                LEFT JOIN render_jobs rj ON rj.candidate_id = cc.id
                WHERE cc.id = ?
                ORDER BY rj.created_at DESC
                LIMIT 1
                """,
                (candidate_id,),
            ).fetchone()
            if not row:
                self._send_json({"error": "candidate not found"}, status=404)
                return
            if row["status"] == "published":
                self._send_json({"error": "published clip post copy is locked"}, status=400)
                return
            candidate = dict(row)
            metadata = _loads(candidate.get("curation_metadata_json"), {})
            try:
                generated = generate_post_caption(
                    candidate,
                    {"metadata_json": candidate.get("render_metadata_json") or "{}"},
                    preferred_provider=preferred_provider,
                )
            except LLMError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            metadata["post_caption_override"] = generated["post_caption"]
            metadata["post_caption_source"] = generated["source"]
            conn.execute(
                """
                UPDATE clip_candidates
                SET curation_metadata_json = ?
                WHERE id = ?
                """,
                (json.dumps(metadata, ensure_ascii=False), candidate_id),
            )
            conn.commit()
            self._send_json({
                "candidate_id": candidate_id,
                **generated,
            })
            return

        if parsed.path == "/api/rerender":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            load_env_file(ENV_FILE)
            try:
                result = create_rerender_job(
                    candidate_id,
                    renderer=str(payload.get("renderer") or "hyperframes"),
                    quality=str(payload.get("quality") or "production"),
                    style_path=str(payload.get("style") or "") or None,
                    force_source_refresh=bool(payload.get("force_source_refresh", False)),
                    regenerate_captions=bool(payload.get("regenerate_captions", False)),
                )
            except (RuntimeError, ValueError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result, status=202)
            return

        if parsed.path == "/api/metadata-refresh":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            mode = str(payload.get("mode") or "smart").strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            load_env_file(ENV_FILE)
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = refresh_candidate_metadata(conn, candidate_id, mode=mode)
                if bool(payload.get("rerender_after", False)):
                    result["rerender_job"] = create_rerender_job(
                        candidate_id,
                        renderer=str(payload.get("renderer") or "hyperframes"),
                        quality=str(payload.get("quality") or "production"),
                        style_path=str(payload.get("style") or "") or None,
                    )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/clip-boundary":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            try:
                start_ms = int(payload.get("start_ms"))
                end_ms = int(payload.get("end_ms"))
            except (TypeError, ValueError):
                self._send_json({"error": "start_ms and end_ms are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = update_clip_boundary(conn, candidate_id, start_ms, end_ms)
                if bool(payload.get("rerender_after", False)):
                    result["rerender_job"] = create_rerender_job(
                        candidate_id,
                        renderer=str(payload.get("renderer") or "hyperframes"),
                        quality=str(payload.get("quality") or "production"),
                        style_path=str(payload.get("style") or "") or None,
                        force_source_refresh=True,
                        regenerate_captions=True,
                    )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(result)
            return

        if parsed.path == "/api/schedule-next":
            candidate_id = str(payload.get("candidate_id", "")).strip()
            platforms = payload.get("platforms")
            if not candidate_id:
                self._send_json({"error": "candidate_id is required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = schedule_candidate_next(
                    conn,
                    candidate_id,
                    platforms=platforms if isinstance(platforms, list) else None,
                )
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

        if parsed.path == "/api/schedule-platforms":
            schedule_id = str(payload.get("schedule_id", "")).strip()
            platforms = payload.get("platforms")
            if not schedule_id or not isinstance(platforms, list):
                self._send_json({"error": "schedule_id and platforms are required"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                result = update_schedule_platforms(conn, schedule_id, [str(platform) for platform in platforms])
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
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

        if parsed.path == "/api/publish-due":
            load_env_file(ENV_FILE)
            try:
                limit = int(payload.get("limit") or 5)
            except (TypeError, ValueError):
                limit = 5
            result = process_due_publishes(
                db_path=DEFAULT_DB,
                env_file=ENV_FILE if ENV_FILE.exists() else None,
                profile_id=str(payload.get("profile_id") or "nourbit").strip() or "nourbit",
                limit=max(1, min(20, limit)),
                dry_run=bool(payload.get("dry_run", False)),
                notify=True,
            )
            self._send_json(result)
            return

        if parsed.path == "/api/oauth-start":
            _safe_load_env()
            platform = str(payload.get("platform", "")).strip()
            profile_id = str(payload.get("profile_id") or "nourbit").strip() or "nourbit"
            host, port = self.server.server_address  # type: ignore[attr-defined]
            server_base = f"http://{host}:{port}"
            try:
                result = start_oauth(platform, server_base, ENV_FILE, profile_id=profile_id)
            except OAuthFlowError as exc:
                self._send_json({"platform": platform, "error": str(exc)}, status=400)
                return
            self._send_json(
                {
                    "platform": result.platform,
                    "profile_id": result.profile_id,
                    "auth_url": result.auth_url,
                    "state": result.state,
                    "expires_in": result.expires_in,
                }
            )
            return

        if parsed.path == "/api/connection-disconnect":
            platform = str(payload.get("platform", "")).strip()
            profile_id = str(payload.get("profile_id") or "nourbit").strip() or "nourbit"
            keys = PLATFORM_DISCONNECT_KEYS.get(platform)
            if not keys:
                self._send_json({"error": "unsupported platform"}, status=400)
                return
            unset_profile_secrets(profile_id, keys)
            self._send_json({"platform": platform, "profile_id": profile_id, "status": "disconnected"})
            return

        if parsed.path == "/api/connection-credentials":
            _safe_load_env()
            profile_id = str(payload.get("profile_id") or "nourbit").strip() or "nourbit"
            platform = str(payload.get("platform") or "").strip()
            values = payload.get("values") if isinstance(payload.get("values"), dict) else {}
            allowed = set(PLATFORM_DISCONNECT_KEYS.get(platform) or [])
            if not allowed:
                self._send_json({"error": "unsupported platform"}, status=400)
                return
            updates = {str(k): str(v) for k, v in values.items() if str(k) in allowed and str(v).strip()}
            if not updates:
                self._send_json({"error": "no credential values provided"}, status=400)
                return
            set_profile_secrets(profile_id, updates)
            self._send_json({"platform": platform, "profile_id": profile_id, "status": "saved", "keys": sorted(updates.keys())})
            return

        if parsed.path == "/api/connection-test":
            platform = str(payload.get("platform", "")).strip()
            profile_id = str(payload.get("profile_id") or "nourbit").strip() or "nourbit"
            _safe_load_env()
            status = credential_status(profile_id).get("platforms", {}).get(platform)
            if not status:
                self._send_json({"error": "unsupported platform"}, status=400)
                return
            if not status.get("ready"):
                self._send_json(
                    {
                        "platform": platform,
                        "profile_id": profile_id,
                        "status": "needs_setup",
                        "missing_keys": status.get("missing_keys", []),
                        "message": "Credentials are missing for this workspace. Connect the account, then refresh.",
                        "error": "Credentials are missing for this workspace. Connect the account, then refresh.",
                    },
                    status=409,
                )
                return
            try:
                result = validate_platform_connection(platform, profile_id=profile_id)
            except LivePublishError as exc:
                self._send_json(
                    {
                        "platform": platform,
                        "profile_id": profile_id,
                        "status": "unauthorized",
                        "message": str(exc),
                        "error": str(exc),
                    },
                    status=401,
                )
                return
            self._send_json({"platform": platform, "profile_id": profile_id, "status": "authorized", "message": "Account authorization verified", "result": result})
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
            try:
                conn.execute("DELETE FROM scheduled_posts WHERE candidate_id = ?", (candidate_id,))
                conn.execute("DELETE FROM rerender_jobs WHERE candidate_id = ?", (candidate_id,))
                conn.execute("DELETE FROM publish_attempts WHERE candidate_id = ?", (candidate_id,))
                conn.execute("DELETE FROM render_jobs WHERE candidate_id = ?", (candidate_id,))
                conn.execute("DELETE FROM clip_candidates WHERE id = ?", (candidate_id,))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                self._send_json({"error": f"failed to delete candidate: {exc}"}, status=409)
                return
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
            active_generation = conn.execute(
                "SELECT count(*) FROM generation_jobs WHERE status IN ('queued','running')"
            ).fetchone()[0]
            active_rerender = conn.execute(
                "SELECT count(*) FROM rerender_jobs WHERE status IN ('queued','running')"
            ).fetchone()[0]
            if active_generation or active_rerender:
                self._send_json(
                    {
                        "error": "cannot clear while jobs are running",
                        "active_generation_jobs": active_generation,
                        "active_rerender_jobs": active_rerender,
                    },
                    status=409,
                )
                return
            paths = [
                row["output_path"]
                for row in conn.execute("SELECT output_path FROM render_jobs WHERE output_path != ''")
                if row["output_path"]
            ]
            counts = {
                "clip_candidates": conn.execute("SELECT count(*) FROM clip_candidates").fetchone()[0],
                "render_jobs": conn.execute("SELECT count(*) FROM render_jobs").fetchone()[0],
                "rerender_jobs": conn.execute("SELECT count(*) FROM rerender_jobs").fetchone()[0],
                "publish_attempts": conn.execute("SELECT count(*) FROM publish_attempts").fetchone()[0],
                "scheduled_posts": conn.execute("SELECT count(*) FROM scheduled_posts").fetchone()[0],
            }
            try:
                conn.execute("BEGIN")
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("DELETE FROM scheduled_posts")
                conn.execute("DELETE FROM rerender_jobs")
                conn.execute("DELETE FROM publish_attempts")
                conn.execute("DELETE FROM render_jobs")
                conn.execute("DELETE FROM clip_candidates")
                conn.execute("PRAGMA foreign_keys = ON")
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                conn.execute("PRAGMA foreign_keys = ON")
                self._send_json({"error": f"failed to clear review data: {exc}"}, status=409)
                return
            removed = _delete_candidate_artifacts(paths) if delete_artifacts else []
            self._send_json({"deleted": counts, "artifacts_removed": removed})
            return

        if parsed.path == "/api/watch-channels":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            channel_url = str(payload.get("channel_url") or payload.get("url") or "").strip()
            if not channel_url:
                self._send_json({"error": "channel_url is required"}, status=400)
                return
            try:
                channel = add_watch_channel(
                    conn,
                    channel_url=channel_url,
                    profile_id=str(payload.get("profile_id") or "nourbit").strip() or "nourbit",
                    label=str(payload.get("label") or "").strip(),
                    permission_status=str(payload.get("permission_status") or "user_attested").strip(),
                    poll_interval_minutes=int(payload.get("poll_interval_minutes") or 30),
                    generation_defaults=payload.get("generation_defaults") if isinstance(payload.get("generation_defaults"), dict) else None,
                    bootstrap_seen=bool(payload.get("bootstrap_seen", True)),
                )
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(channel, status=201)
            return

        if parsed.path == "/api/watch-channel-update":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            channel_id = str(payload.get("id") or payload.get("channel_id") or "").strip()
            if not channel_id:
                self._send_json({"error": "id is required"}, status=400)
                return
            try:
                channel = update_watch_channel(conn, channel_id, payload)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(channel)
            return

        if parsed.path == "/api/watch-channel-delete":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            channel_id = str(payload.get("id") or payload.get("channel_id") or "").strip()
            if not channel_id:
                self._send_json({"error": "id is required"}, status=400)
                return
            try:
                self._send_json(delete_watch_channel(conn, channel_id))
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=404)
            return

        if parsed.path == "/api/watch-poll":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            channel_id = str(payload.get("id") or payload.get("channel_id") or "").strip()
            force = bool(payload.get("force", True))
            try:
                if channel_id:
                    result = poll_watch_channel(conn, channel_id, enqueue=True, force=force)
                    self._send_json(result)
                else:
                    profile_id = str(payload.get("profile_id") or "").strip() or None
                    self._send_json({"results": poll_due_watch_channels(conn, profile_id=profile_id, force=force)})
            except (ValueError, RuntimeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/publish-target":
            conn = connect(DEFAULT_DB)
            initialize(conn)
            try:
                if payload.get("id") is not None:
                    target = update_publish_target(conn, payload)
                else:
                    target = upsert_publish_target(conn, payload)
            except (ValueError, TypeError) as exc:
                self._send_json({"error": str(exc)}, status=400)
                return
            self._send_json(target)
            return

        if parsed.path == "/api/set-target-mode":
            profile = str(payload.get("profile", "nourbit")).strip()
            platform = str(payload.get("platform", "")).strip()
            mode = str(payload.get("mode", "")).strip()
            if mode not in PUBLISH_MODES:
                self._send_json({"error": "unsupported mode"}, status=400)
                return
            conn = connect(DEFAULT_DB)
            initialize(conn)
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
            _safe_load_env()
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
            built_payload["dry_run"] = dry_run
            built_payload["profile_id"] = candidate.get("profile_id")
            if dry_run:
                self._send_json({"status": "dry_run", "attempt": attempt, "payload": built_payload})
                return
            try:
                result = publish_live_payload(platform, built_payload, profile_id=str(candidate.get("profile_id") or "nourbit"))
            except LivePublishError as exc:
                conn.execute(
                    "UPDATE publish_attempts SET status = ?, error = ? WHERE id = ?",
                    ("failed", str(exc), attempt["id"]),
                )
                conn.commit()
                attempt["status"] = "failed"
                attempt["error"] = str(exc)
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

    def _send_media_file(self, path: Path) -> None:
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        file_size = path.stat().st_size
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
        self.send_header("Content-Disposition", f'inline; filename="{path.name}"')
        if byte_range:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def _send_html(self, html: str, status: int = 200) -> None:
        payload = f"<!doctype html><html><body style='font-family:system-ui;background:#0b0d12;color:#e6e8ef;padding:24px'>{html}</body></html>".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    port = int(os.environ.get("MEDIA_ENGINE_PORT", "8765"))
    _safe_load_env()
    server = ThreadingHTTPServer(("127.0.0.1", port), ReviewHandler)
    print(f"review UI: http://127.0.0.1:{port}/review.html")
    server.serve_forever()


if __name__ == "__main__":
    main()
