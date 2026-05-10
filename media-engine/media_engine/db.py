"""SQLite persistence for local-first autonomous media workflows."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "media_engine.sqlite"
ARTIFACTS_DIR = ROOT / "artifacts"


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
  UNIQUE(profile_id, platform)
);

CREATE TABLE IF NOT EXISTS clip_candidates (
  id TEXT PRIMARY KEY,
  profile_id TEXT NOT NULL REFERENCES media_profiles(id),
  source_id TEXT NOT NULL REFERENCES source_manifests(id),
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  title_hook TEXT NOT NULL,
  viral_reason TEXT NOT NULL,
  transcript_span TEXT NOT NULL,
  risk_flags_json TEXT NOT NULL,
  score_json TEXT NOT NULL DEFAULT '{}',
  curation_metadata_json TEXT NOT NULL DEFAULT '{}',
  caption_source TEXT NOT NULL DEFAULT 'youtube',
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
"""


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA_UPGRADES = {
    "clip_candidates": {
        "score_json": "TEXT NOT NULL DEFAULT '{}'",
        "curation_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "caption_source": "TEXT NOT NULL DEFAULT 'youtube'",
    }
}


def ensure_schema_upgrades(conn: sqlite3.Connection) -> None:
    for table, columns in SCHEMA_UPGRADES.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, definition in columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    ensure_schema_upgrades(conn)
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
               ai_disclosure_required, daily_cap)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile["id"],
                target["platform"],
                target["account_label"],
                target["mode"],
                int(target.get("require_approval", True)),
                int(target.get("ai_disclosure_required", False)),
                int(target.get("daily_cap", 10)),
            ),
        )
    conn.commit()


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
