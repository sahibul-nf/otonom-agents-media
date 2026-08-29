import sqlite3
import unittest

from media_engine.db import initialize
from media_engine.review_server import _delete_candidate_record


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


def insert_candidate(conn: sqlite3.Connection, candidate_id: str) -> None:
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
            "rendered",
        ),
    )
    conn.execute(
        """
        INSERT INTO render_jobs (id, candidate_id, preset, crop_strategy, caption_style, status, output_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (f"render-{candidate_id}", candidate_id, "premium", "center", "caption", "completed", f"/tmp/artifacts/nourbit/{candidate_id}/final.mp4"),
    )
    conn.commit()


class ReviewDeleteCandidatesTests(unittest.TestCase):
    def test_delete_single_candidate_record(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a")
        ok, error, paths = _delete_candidate_record(conn, "clip-a")
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertEqual(paths, [f"/tmp/artifacts/nourbit/clip-a/final.mp4"])
        remaining = conn.execute("SELECT id FROM clip_candidates").fetchall()
        self.assertEqual(remaining, [])
        conn.close()

    def test_bulk_delete_skips_unknown_ids(self):
        conn = make_conn()
        insert_candidate(conn, "clip-a")
        insert_candidate(conn, "clip-b")

        deleted_ids: list[str] = []
        failed: list[dict[str, str]] = []
        for candidate_id in ["clip-a", "missing", "clip-b"]:
            ok, error, _paths = _delete_candidate_record(conn, candidate_id)
            if ok:
                deleted_ids.append(candidate_id)
            else:
                failed.append({"id": candidate_id, "error": error or "unknown error"})

        self.assertEqual(deleted_ids, ["clip-a", "clip-b"])
        self.assertEqual(failed, [{"id": "missing", "error": "candidate not found"}])
        self.assertEqual(conn.execute("SELECT count(*) FROM clip_candidates").fetchone()[0], 0)
        conn.close()

    def test_delete_unknown_candidate_returns_not_found(self):
        conn = make_conn()
        ok, error, paths = _delete_candidate_record(conn, "missing")
        self.assertFalse(ok)
        self.assertEqual(error, "candidate not found")
        self.assertEqual(paths, [])
        conn.close()


if __name__ == "__main__":
    unittest.main()
