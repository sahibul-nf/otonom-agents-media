import sqlite3
import unittest

from media_engine.db import initialize
from media_engine.publishers import build_payload, create_dry_run_attempt


class PublisherTests(unittest.TestCase):
    def test_build_tiktok_payload_defaults_private(self):
        candidate = {"id": "clip1", "title_hook": "Hook"}
        render_job = {"output_path": "/tmp/clip.mp4"}
        payload = build_payload("tiktok", candidate, render_job)
        self.assertEqual(payload["visibility"], "private")
        self.assertTrue(payload["dry_run"])

    def test_blocked_attempt_is_recorded(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        initialize(conn)
        conn.execute("INSERT INTO media_profiles VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("nourbit", "Nourbit", "niche", "[]", "lecture_clean", "cta", "wm"))
        conn.execute("INSERT INTO source_manifests VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("src", "nourbit", "url", "community", "public_third_party", "", "[]", 0, "", "[]"))
        conn.execute("INSERT INTO clip_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", ("clip", "nourbit", "src", 0, 1000, "Hook", "Reason", "Text", "[]", "approved"))
        source = {"permission_status": "public_third_party", "permission_evidence": ""}
        target = {"platform": "facebook_reels", "mode": "auto_publish", "require_approval": 1}
        candidate = {"id": "clip", "title_hook": "Hook", "status": "approved"}
        attempt = create_dry_run_attempt(conn, source, target, candidate, {"output_path": "/tmp/clip.mp4"})
        self.assertEqual(attempt["status"], "blocked")
        self.assertIn("public third-party", attempt["error"])


if __name__ == "__main__":
    unittest.main()
