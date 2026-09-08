import sqlite3
import unittest

from media_engine.db import initialize
from media_engine.review_server import APPROVABLE_STATUSES, _approve_candidate_record, batch_approve_candidates


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    initialize(conn)
    conn.execute(
        "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
    )
    conn.execute(
        "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
        ("src", "nourbit", "https://youtube.com/watch?v=test", "community", "public_third_party", "", "[]", 1, "", "[]"),
    )
    return conn


def insert_candidate(conn: sqlite3.Connection, candidate_id: str, status: str = "rendered") -> None:
    conn.execute(
        """
        INSERT INTO clip_candidates
          (id, profile_id, source_id, start_ms, end_ms, title_hook, hook_subtitle,
           viral_reason, transcript_span, risk_flags_json, score_json,
           curation_metadata_json, caption_corrections_json, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            "nourbit",
            "src",
            0,
            30_000,
            f"Hook {candidate_id}",
            "Subtitle",
            "Reason",
            "Transcript",
            "[]",
            "{}",
            "{}",
            "{}",
            status,
        ),
    )
    conn.commit()


class ReviewBatchApproveTests(unittest.TestCase):
    def test_approvable_statuses(self):
        self.assertEqual(APPROVABLE_STATUSES, {"rendered", "pending_auto_schedule"})

    def test_approve_rendered_candidate(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a")
        ok, error = _approve_candidate_record(conn, "clip-a")
        conn.commit()
        self.assertTrue(ok)
        self.assertIsNone(error)
        status = conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip-a'").fetchone()["status"]
        self.assertEqual(status, "approved")
        conn.close()

    def test_approve_skips_already_approved(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a", status="approved")
        ok, error = _approve_candidate_record(conn, "clip-a")
        self.assertFalse(ok)
        self.assertEqual(error, "already approved")
        conn.close()

    def test_approve_skips_held_by_default(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a", status="held")
        ok, error = _approve_candidate_record(conn, "clip-a")
        self.assertFalse(ok)
        self.assertIn("cannot be approved", error or "")
        conn.close()

    def test_approve_blocks_active_rerender(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a")
        conn.execute(
            """
            INSERT INTO rerender_jobs (id, candidate_id, status, renderer, quality, style_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("rerender-1", "clip-a", "running", "hyperframes", "production", "auto"),
        )
        conn.commit()
        ok, error = _approve_candidate_record(conn, "clip-a")
        self.assertFalse(ok)
        self.assertEqual(error, "re-render in progress")
        conn.close()

    def test_batch_approve_mixed_eligibility(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a")
        insert_candidate(conn, "clip-b", status="approved")
        insert_candidate(conn, "clip-c", status="held")

        result = batch_approve_candidates(conn, ["clip-a", "clip-b", "clip-c", "missing"])

        self.assertEqual(result["approved_ids"], ["clip-a"])
        self.assertEqual(len(result["skipped"]), 2)
        self.assertEqual(result["failed"], [{"id": "missing", "error": "candidate not found"}])
        status = conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip-a'").fetchone()["status"]
        self.assertEqual(status, "approved")
        conn.close()


if __name__ == "__main__":
    unittest.main()
