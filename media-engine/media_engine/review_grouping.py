"""Review queue helpers: attach source cosmetics for batch grouping (#58)."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

GENERIC_SOURCE_ID_RE = re.compile(r"(^workspace_source$|_source$)")


def is_generic_source_id(source_id: str | None) -> bool:
    """True when source_id cannot safely group siblings (legacy Create default)."""
    value = str(source_id or "").strip()
    if not value:
        return True
    return bool(GENERIC_SOURCE_ID_RE.search(value))


def _loads(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError, ValueError):
        return fallback


def _title_from_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.netloc or "").replace("www.", "")
    path = (parsed.path or "").strip("/")
    if host and path:
        return f"{host}/{path.split('/')[-1]}"
    return host or path or raw


def source_payload_from_job_result(
    *,
    source_id: str,
    source_url: str = "",
    result_json: Any = None,
) -> dict[str, Any]:
    result = _loads(result_json, {})
    if not isinstance(result, dict):
        result = {}
    meta = result.get("source_metadata")
    if not isinstance(meta, dict):
        meta = {}
    title = str(meta.get("title") or "").strip()
    channel = str(meta.get("channel") or "").strip()
    thumbnail = str(meta.get("thumbnail_url") or "").strip()
    canonical = str(meta.get("canonical_url") or meta.get("source_url") or source_url or "").strip()
    if not title:
        title = _title_from_url(canonical) or "Clip batch"
    return {
        "id": source_id,
        "url": canonical,
        "title": title,
        "channel": channel,
        "thumbnail_url": thumbnail if thumbnail not in {"", "NA", "None"} else "",
        "groupable": not is_generic_source_id(source_id),
    }


def enrich_review_rows_with_source(conn: Any, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach `source` cosmetics from manifests + latest generation job per source_id."""
    source_ids = sorted({str(row.get("source_id") or "").strip() for row in rows if row.get("source_id")})
    manifests: dict[str, str] = {}
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        for row in conn.execute(
            f"SELECT id, source_url FROM source_manifests WHERE id IN ({placeholders})",
            source_ids,
        ):
            manifests[str(row["id"])] = str(row["source_url"] or "")

    job_results: dict[str, Any] = {}
    if source_ids:
        placeholders = ",".join("?" for _ in source_ids)
        for row in conn.execute(
            f"""
            SELECT g.source_id, g.result_json
            FROM generation_jobs g
            INNER JOIN (
              SELECT source_id, MAX(created_at) AS max_created
              FROM generation_jobs
              WHERE source_id IN ({placeholders})
              GROUP BY source_id
            ) latest ON latest.source_id = g.source_id AND latest.max_created = g.created_at
            """,
            source_ids,
        ):
            job_results[str(row["source_id"])] = row["result_json"]

    for row in rows:
        source_id = str(row.get("source_id") or "").strip()
        source_url = manifests.get(source_id, "")
        # Prefer manifest URL when job metadata omitted it.
        payload = source_payload_from_job_result(
            source_id=source_id or f"clip:{row.get('id') or 'unknown'}",
            source_url=source_url,
            result_json=job_results.get(source_id),
        )
        if not payload["url"] and source_url:
            payload["url"] = source_url
            if payload["title"] == "Clip batch":
                payload["title"] = _title_from_url(source_url) or "Clip batch"
        row["source"] = payload
    return rows
