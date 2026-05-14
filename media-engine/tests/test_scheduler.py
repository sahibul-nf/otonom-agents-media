import sqlite3
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from media_engine.db import initialize
from media_engine.scheduler import list_scheduled_posts, schedule_candidate_next, unschedule_candidate


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        initialize(self.conn)
        self.conn.execute(
            "INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"),
        )
        self.conn.execute(
            "INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            ("src", "nourbit", "url", "community", "authorized_community", "ok", "[]", 1, "", "[]"),
        )

    def tearDown(self):
        self.conn.close()

    def add_clip(self, candidate_id="clip", status="approved"):
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (candidate_id, "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", status),
        )
        self.conn.commit()

    def test_schedule_next_uses_two_daily_slots(self):
        tz = ZoneInfo("Asia/Jakarta")
        self.add_clip("clip1")
        self.add_clip("clip2")
        self.add_clip("clip3")
        now = datetime(2026, 5, 15, 8, 0, tzinfo=tz)

        first = schedule_candidate_next(self.conn, "clip1", now=now)
        second = schedule_candidate_next(self.conn, "clip2", now=now)
        third = schedule_candidate_next(self.conn, "clip3", now=now)

        self.assertIn("2026-05-15T09:00", first["scheduled_at"])
        self.assertIn("2026-05-15T19:30", second["scheduled_at"])
        self.assertIn("2026-05-16T09:00", third["scheduled_at"])

    def test_only_approved_clips_can_be_scheduled(self):
        self.add_clip(status="rendered")
        with self.assertRaises(ValueError):
            schedule_candidate_next(self.conn, "clip")

    def test_unschedule_returns_candidate_to_approved(self):
        self.add_clip()
        schedule_candidate_next(self.conn, "clip", now=datetime(2026, 5, 15, 8, 0, tzinfo=ZoneInfo("Asia/Jakarta")))
        unschedule_candidate(self.conn, "clip")

        row = self.conn.execute("SELECT status FROM clip_candidates WHERE id = 'clip'").fetchone()
        self.assertEqual(row["status"], "approved")
        self.assertEqual(list_scheduled_posts(self.conn), [])


if __name__ == "__main__":
    unittest.main()
