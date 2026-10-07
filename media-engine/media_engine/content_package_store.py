"""SQLite persistence for content packages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .content_package import ContentPackage, apply_qa_status
from .db import connect, fetch_all, fetch_one, initialize


def ensure_content_packages_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_packages (
          id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          format TEXT NOT NULL,
          job TEXT NOT NULL,
          source_json TEXT NOT NULL,
          caption TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL DEFAULT '',
          description TEXT NOT NULL DEFAULT '',
          video_engine TEXT,
          parent_package_id TEXT NOT NULL DEFAULT '',
          brand_preset TEXT NOT NULL DEFAULT 'blank',
          artifacts_json TEXT NOT NULL DEFAULT '{}',
          qa_json TEXT NOT NULL DEFAULT '{}',
          status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()


def save_package(pkg: ContentPackage, *, db_path: str | Path) -> ContentPackage:
    conn = connect(db_path)
    initialize(conn)
    ensure_content_packages_table(conn)
    pkg = apply_qa_status(pkg)
    conn.execute(
        """
        INSERT OR REPLACE INTO content_packages (
          id, profile_id, format, job, source_json, caption, title, description,
          video_engine, parent_package_id, brand_preset, artifacts_json, qa_json, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pkg.id,
            pkg.profile_id,
            pkg.format,
            pkg.job,
            json.dumps({"kind": pkg.source_kind, "ref": pkg.source_ref}),
            pkg.caption,
            pkg.title,
            pkg.description,
            pkg.video_engine,
            pkg.parent_package_id,
            pkg.brand_preset,
            json.dumps(pkg.artifacts.to_dict()),
            json.dumps(pkg.qa.to_dict()),
            pkg.status,
            pkg.created_at or None,
        ),
    )
    conn.commit()
    return pkg


def get_package(package_id: str, *, db_path: str | Path) -> ContentPackage | None:
    conn = connect(db_path)
    initialize(conn)
    ensure_content_packages_table(conn)
    row = fetch_one(conn, "SELECT * FROM content_packages WHERE id = ?", (package_id,))
    if not row:
        return None
    return ContentPackage.from_row(dict(row))


def list_packages(
    *,
    db_path: str | Path,
    profile_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conn = connect(db_path)
    initialize(conn)
    ensure_content_packages_table(conn)
    clauses = ["1=1"]
    params: list[Any] = []
    if profile_id:
        clauses.append("profile_id = ?")
        params.append(profile_id)
    if status:
        clauses.append("status = ?")
        params.append(status)
    params.append(limit)
    rows = fetch_all(
        conn,
        f"""
        SELECT * FROM content_packages
        WHERE {' AND '.join(clauses)}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        tuple(params),
    )
    return [ContentPackage.from_row(dict(r)).to_dict() for r in rows]


def approve_package(package_id: str, *, db_path: str | Path) -> ContentPackage:
    conn = connect(db_path)
    initialize(conn)
    ensure_content_packages_table(conn)
    row = fetch_one(conn, "SELECT * FROM content_packages WHERE id = ?", (package_id,))
    if not row:
        raise ValueError(f"package not found: {package_id}")
    pkg = ContentPackage.from_row(dict(row))
    if pkg.status not in ("ready_for_review", "draft"):
        pass
    pkg.status = "approved"
    save_package(pkg, db_path=db_path)
    return pkg
