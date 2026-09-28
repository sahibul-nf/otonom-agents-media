"""SQLite persistence for local-first autonomous media workflows."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from .duration_presets import resolve_duration_preset
from .hyperframes_templates import normalize_hyperframes_template

ROOT = Path(__file__).resolve().parents[1]
_db_override = (os.environ.get("MEDIA_ENGINE_DB") or "").strip()
DEFAULT_DB = Path(_db_override).expanduser() if _db_override else ROOT / "data" / "media_engine.sqlite"
_artifacts_override = (os.environ.get("MEDIA_ENGINE_ARTIFACTS") or "").strip()
ARTIFACTS_DIR = Path(_artifacts_override).expanduser() if _artifacts_override else ROOT / "artifacts"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS media_profiles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  niche TEXT NOT NULL,
  languages_json TEXT NOT NULL,
  default_render_preset TEXT NOT NULL,
  cta_text TEXT NOT NULL,
  watermark_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS source_manifests (
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  source_url TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  permission_status TEXT NOT NULL,
  permission_evidence TEXT NOT NULL DEFAULT '',
  allowed_use_json TEXT NOT NULL,
  monetization_allowed INTEGER NOT NULL DEFAULT 0,
  attribution_rule TEXT NOT NULL DEFAULT '',
  publish_restrictions_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_targets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  platform TEXT NOT NULL,
  account_label TEXT NOT NULL,
  mode TEXT NOT NULL,
  require_approval INTEGER NOT NULL DEFAULT 1,
  ai_disclosure_required INTEGER NOT NULL DEFAULT 0,
  daily_cap INTEGER NOT NULL DEFAULT 10,
  enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE(profile_id, platform)
);

CREATE TABLE IF NOT EXISTS clip_candidates (
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  source_id TEXT NOT NULL REFERENCES source_manifests(id),
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  title_hook TEXT NOT NULL,
  hook_subtitle TEXT NOT NULL DEFAULT '',
  viral_reason TEXT NOT NULL,
  transcript_span TEXT NOT NULL,
  risk_flags_json TEXT NOT NULL,
  score_json TEXT NOT NULL DEFAULT '{}',
  curation_metadata_json TEXT NOT NULL DEFAULT '{}',
  caption_source TEXT NOT NULL DEFAULT 'youtube',
  asr_metadata_json TEXT NOT NULL DEFAULT '{}',
  render_quality_json TEXT NOT NULL DEFAULT '{}',
  cost_json TEXT NOT NULL DEFAULT '{}',
  quality_gate_json TEXT NOT NULL DEFAULT '{}',
  caption_corrections_json TEXT NOT NULL DEFAULT '{}',
  dedupe_key TEXT NOT NULL DEFAULT '',
  review_deadline_at TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS render_jobs (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES clip_candidates(id),
  preset TEXT NOT NULL,
  crop_strategy TEXT NOT NULL,
  caption_style TEXT NOT NULL,
  status TEXT NOT NULL,
  output_path TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rerender_jobs (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES clip_candidates(id),
  renderer TEXT NOT NULL,
  quality TEXT NOT NULL,
  style_path TEXT NOT NULL DEFAULT '',
  hyperframes_template TEXT NOT NULL DEFAULT '',
  brand_system_template_id TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL DEFAULT '',
  result_json TEXT NOT NULL DEFAULT '{}',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publish_attempts (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL REFERENCES clip_candidates(id),
  platform TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_jobs (
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  source_id TEXT NOT NULL,
  source_url TEXT NOT NULL,
  count INTEGER NOT NULL,
  clip_length_preset TEXT NOT NULL DEFAULT 'auto',
  clip_min_seconds INTEGER NOT NULL DEFAULT 20,
  clip_max_seconds INTEGER NOT NULL DEFAULT 180,
  genres_json TEXT NOT NULL DEFAULT '[]',
  brand_template TEXT NOT NULL,
  hyperframes_template TEXT NOT NULL DEFAULT 'auto',
  brand_system_template_id TEXT NOT NULL DEFAULT '',
  hyperframes_format TEXT NOT NULL DEFAULT 'auto',
  renderer TEXT NOT NULL,
  quality TEXT NOT NULL,
  caption_source TEXT NOT NULL,
  asr_model TEXT NOT NULL,
  speech_language TEXT NOT NULL DEFAULT 'id',
  transcript_languages TEXT NOT NULL DEFAULT 'id,en',
  llm_provider TEXT NOT NULL,
  status TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  command TEXT NOT NULL DEFAULT '',
  log_text TEXT NOT NULL DEFAULT '',
  result_json TEXT NOT NULL DEFAULT '{}',
  error TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_posts (
  id TEXT PRIMARY KEY,
  candidate_id TEXT NOT NULL UNIQUE REFERENCES clip_candidates(id),
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  scheduled_at TEXT NOT NULL,
  status TEXT NOT NULL,
  publish_mode TEXT NOT NULL DEFAULT 'queue_only',
  platforms_json TEXT NOT NULL DEFAULT '[]',
  platform_results_json TEXT NOT NULL DEFAULT '{}',
  published_at TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS autonomy_settings (
  profile_id TEXT PRIMARY KEY REFERENCES media_profiles(id),
  autonomy_mode TEXT NOT NULL DEFAULT 'assisted',
  review_grace_hours INTEGER NOT NULL DEFAULT 12,
  auto_schedule_enabled INTEGER NOT NULL DEFAULT 1,
  overall_threshold INTEGER NOT NULL DEFAULT 82,
  hook_threshold INTEGER NOT NULL DEFAULT 80,
  caption_threshold INTEGER NOT NULL DEFAULT 90,
  boundary_threshold INTEGER NOT NULL DEFAULT 80,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watch_channels (
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  channel_url TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  permission_status TEXT NOT NULL DEFAULT 'user_attested',
  enabled INTEGER NOT NULL DEFAULT 1,
  poll_interval_minutes INTEGER NOT NULL DEFAULT 30,
  last_polled_at TEXT NOT NULL DEFAULT '',
  last_seen_video_id TEXT NOT NULL DEFAULT '',
  last_new_video_id TEXT NOT NULL DEFAULT '',
  last_new_video_at TEXT NOT NULL DEFAULT '',
  last_clip_job_id TEXT NOT NULL DEFAULT '',
  last_error TEXT NOT NULL DEFAULT '',
  generation_defaults_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(profile_id, channel_url)
);
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.Error:
        pass
    return conn


SCHEMA_UPGRADES = {
    "clip_candidates": {
        "hook_subtitle": "TEXT NOT NULL DEFAULT ''",
        "score_json": "TEXT NOT NULL DEFAULT '{}'",
        "curation_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "caption_source": "TEXT NOT NULL DEFAULT 'youtube'",
        "asr_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "render_quality_json": "TEXT NOT NULL DEFAULT '{}'",
        "cost_json": "TEXT NOT NULL DEFAULT '{}'",
        "quality_gate_json": "TEXT NOT NULL DEFAULT '{}'",
        "caption_corrections_json": "TEXT NOT NULL DEFAULT '{}'",
        "dedupe_key": "TEXT NOT NULL DEFAULT ''",
        "review_deadline_at": "TEXT NOT NULL DEFAULT ''",
    },
    "generation_jobs": {
        "clip_length_preset": "TEXT NOT NULL DEFAULT 'auto'",
        "clip_min_seconds": "INTEGER NOT NULL DEFAULT 20",
        "clip_max_seconds": "INTEGER NOT NULL DEFAULT 180",
        "genres_json": "TEXT NOT NULL DEFAULT '[]'",
        "hyperframes_template": "TEXT NOT NULL DEFAULT 'auto'",
        "brand_system_template_id": "TEXT NOT NULL DEFAULT ''",
        "hyperframes_format": "TEXT NOT NULL DEFAULT 'auto'",
        "command": "TEXT NOT NULL DEFAULT ''",
        "speech_language": "TEXT NOT NULL DEFAULT 'id'",
        "transcript_languages": "TEXT NOT NULL DEFAULT 'id,en'",
        "log_text": "TEXT NOT NULL DEFAULT ''",
        "result_json": "TEXT NOT NULL DEFAULT '{}'",
        "error": "TEXT NOT NULL DEFAULT ''",
        "curation_source": "TEXT NOT NULL DEFAULT 'auto'",
        "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "scheduled_posts": {
        "publish_mode": "TEXT NOT NULL DEFAULT 'queue_only'",
        "platforms_json": "TEXT NOT NULL DEFAULT '[]'",
        "platform_results_json": "TEXT NOT NULL DEFAULT '{}'",
        "published_at": "TEXT NOT NULL DEFAULT ''",
        "last_error": "TEXT NOT NULL DEFAULT ''",
        "note": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "rerender_jobs": {
        "style_path": "TEXT NOT NULL DEFAULT ''",
        "hyperframes_template": "TEXT NOT NULL DEFAULT ''",
        "brand_system_template_id": "TEXT NOT NULL DEFAULT ''",
        "force_source_refresh": "INTEGER NOT NULL DEFAULT 0",
        "regenerate_captions": "INTEGER NOT NULL DEFAULT 0",
        "status": "TEXT NOT NULL DEFAULT 'queued'",
        "progress": "INTEGER NOT NULL DEFAULT 0",
        "message": "TEXT NOT NULL DEFAULT ''",
        "result_json": "TEXT NOT NULL DEFAULT '{}'",
        "error": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
    },
    "publish_targets": {
        "enabled": "INTEGER NOT NULL DEFAULT 1",
    },
}


def ensure_schema_upgrades(conn: sqlite3.Connection) -> None:
    for table, columns in SCHEMA_UPGRADES.items():
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not table_exists:
            continue
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()


def normalize_schema_values(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'generation_jobs'"
    ).fetchone()
    if not table_exists:
        return
    for row in conn.execute("SELECT id, clip_length_preset, hyperframes_template FROM generation_jobs"):
        canonical = resolve_duration_preset(row["clip_length_preset"]).id
        if row["clip_length_preset"] != canonical:
            conn.execute(
                "UPDATE generation_jobs SET clip_length_preset = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (canonical, row["id"]),
            )
        template = normalize_hyperframes_template(row["hyperframes_template"])
        if row["hyperframes_template"] != template:
            conn.execute(
                "UPDATE generation_jobs SET hyperframes_template = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (template, row["id"]),
            )
    conn.commit()


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_schema_upgrades(conn)
    normalize_schema_values(conn)
    conn.commit()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_profile(conn: sqlite3.Connection, profile: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO media_profiles
          (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            profile["id"],
            profile["name"],
            profile["niche"],
            json.dumps(profile["languages"], ensure_ascii=False),
            profile["default_render_preset"],
            profile["cta_text"],
            profile["watermark_text"],
        ),
    )

    for target in profile["publish_targets"]:
        conn.execute(
            """
            INSERT OR REPLACE INTO publish_targets
              (profile_id, platform, account_label, mode, require_approval,
               ai_disclosure_required, daily_cap, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile["id"],
                target["platform"],
                target["account_label"],
                target["mode"],
                int(target.get("require_approval", True)),
                int(target.get("ai_disclosure_required", False)),
                int(target.get("daily_cap", 10)),
                int(target.get("enabled", True)),
            ),
        )
    conn.commit()


DEFAULT_WORKSPACE_PROFILE_ID = "workspace"
DEFAULT_WORKSPACE_SOURCE_ID = "workspace_source"


def workspace_profile() -> dict[str, Any]:
    path = ROOT / "profiles" / "workspace.json"
    if path.exists():
        return load_json(path)
    return {
        "id": DEFAULT_WORKSPACE_PROFILE_ID,
        "name": "Workspace",
        "niche": "General short-form clips",
        "languages": ["id", "en"],
        "default_render_preset": "short_clean",
        "cta_text": "",
        "watermark_text": "",
        "publish_targets": [],
    }


def ensure_media_profile(conn: sqlite3.Connection, profile_id: str) -> None:
    if conn.execute("SELECT 1 FROM media_profiles WHERE id = ?", (profile_id,)).fetchone():
        return
    if profile_id == DEFAULT_WORKSPACE_PROFILE_ID:
        seed_profile(conn, workspace_profile())
        return
    nourbit_path = ROOT / "profiles" / "nourbit.json"
    if profile_id == "nourbit" and nourbit_path.exists():
        seed_profile(conn, load_json(nourbit_path))
        return
    raise ValueError(f"Unknown profile_id '{profile_id}'. Seed a profile before starting generation.")


def ensure_source_manifest(
    conn: sqlite3.Connection,
    *,
    profile_id: str,
    source_id: str,
    source_url: str,
) -> None:
    existing = conn.execute("SELECT 1 FROM source_manifests WHERE id = ?", (source_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE source_manifests SET profile_id = ?, source_url = ? WHERE id = ?",
            (profile_id, source_url, source_id),
        )
        conn.commit()
        return
    seed_source(
        conn,
        {
            "id": source_id,
            "profile_id": profile_id,
            "source_url": source_url,
            "owner_type": "user_submitted",
            "permission_status": "user_attested",
            "permission_evidence": "Submitted via dashboard generate flow.",
            "allowed_use": ["draft_clip_generation", "manual_review"],
            "monetization_allowed": False,
            "attribution_rule": "Credit the original YouTube source when publishing.",
            "publish_restrictions": ["manual_review_required"],
        },
    )


def seed_source(conn: sqlite3.Connection, manifest: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO source_manifests
          (id, profile_id, source_url, owner_type, permission_status,
           permission_evidence, allowed_use_json, monetization_allowed,
           attribution_rule, publish_restrictions_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            manifest["id"],
            manifest["profile_id"],
            manifest["source_url"],
            manifest["owner_type"],
            manifest["permission_status"],
            manifest.get("permission_evidence", ""),
            json.dumps(manifest.get("allowed_use", []), ensure_ascii=False),
            int(manifest.get("monetization_allowed", False)),
            manifest.get("attribution_rule", ""),
            json.dumps(manifest.get("publish_restrictions", []), ensure_ascii=False),
        ),
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def fetch_one(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
    return row_to_dict(conn.execute(query, params).fetchone())


def fetch_all(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, params).fetchall()]
