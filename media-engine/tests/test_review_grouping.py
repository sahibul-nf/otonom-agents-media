"""Tests for Review source grouping helpers (#58)."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from media_engine.review_grouping import (
    enrich_review_rows_with_source,
    is_generic_source_id,
    source_payload_from_job_result,
)


class ReviewGroupingTests(unittest.TestCase):
    def test_generic_source_ids(self):
        self.assertTrue(is_generic_source_id("workspace_source"))
        self.assertTrue(is_generic_source_id("nourbit_source"))
        self.assertTrue(is_generic_source_id(""))
        self.assertFalse(is_generic_source_id("workspace_Ow5mweU_fx0"))
        self.assertFalse(is_generic_source_id("ingest_abc123"))

    def test_source_payload_prefers_metadata_title(self):
        payload = source_payload_from_job_result(
            source_id="workspace_Ow5mweU_fx0",
            source_url="https://www.youtube.com/watch?v=Ow5mweU_fx0",
            result_json={
                "source_metadata": {
                    "title": "Hello World",
                    "channel": "TechTalk",
                    "thumbnail_url": "https://i.ytimg.com/vi/Ow5mweU_fx0/hqdefault.jpg",
                }
            },
        )
        self.assertEqual(payload["title"], "Hello World")
        self.assertEqual(payload["channel"], "TechTalk")
        self.assertTrue(payload["groupable"])
        self.assertTrue(payload["thumbnail_url"])

    def test_enrich_attaches_source_from_generation_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.executescript(
                """
                CREATE TABLE source_manifests (
                  id TEXT PRIMARY KEY,
                  source_url TEXT NOT NULL
                );
                CREATE TABLE generation_jobs (
                  id TEXT PRIMARY KEY,
                  source_id TEXT NOT NULL,
                  result_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                "INSERT INTO source_manifests (id, source_url) VALUES (?, ?)",
                ("workspace_Ow5mweU_fx0", "https://www.youtube.com/watch?v=Ow5mweU_fx0"),
            )
            conn.execute(
                "INSERT INTO generation_jobs (id, source_id, result_json, created_at) VALUES (?, ?, ?, ?)",
                (
                    "job1",
                    "workspace_Ow5mweU_fx0",
                    json.dumps(
                        {
                            "source_metadata": {
                                "title": "Batch Source",
                                "channel": "Channel",
                                "thumbnail_url": "https://example.com/thumb.jpg",
                            }
                        }
                    ),
                    "2026-08-01T00:00:00",
                ),
            )
            conn.commit()
            rows = [{"id": "clip1", "source_id": "workspace_Ow5mweU_fx0"}]
            enrich_review_rows_with_source(conn, rows)
            self.assertEqual(rows[0]["source"]["title"], "Batch Source")
            self.assertEqual(rows[0]["source"]["channel"], "Channel")
            self.assertTrue(rows[0]["source"]["groupable"])
            conn.close()


if __name__ == "__main__":
    unittest.main()
