import tempfile
import unittest
from unittest.mock import patch

from media_engine.db import connect, initialize
from media_engine.rerender import _run_rerender_job, get_rerender_job


class RerenderJobTests(unittest.TestCase):
    def test_background_rerender_reports_progress_milestones(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/media_engine.sqlite"
            conn = connect(db_path)
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO source_manifests
                  (id, profile_id, source_url, owner_type, permission_status, allowed_use_json, publish_restrictions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("source_1", "nourbit", "https://youtube.com/watch?v=test", "third_party", "allowed", "[]", "[]"),
            )
            conn.execute(
                """
                INSERT INTO clip_candidates
                  (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason, transcript_span, risk_flags_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("clip_1", "nourbit", "source_1", 0, 60000, "Hook", "Reason", "span", "[]", "rendered"),
            )
            conn.execute(
                """
                INSERT INTO rerender_jobs
                  (id, candidate_id, renderer, quality, style_path, status, progress, message, result_json, error)
                VALUES (?, ?, ?, ?, ?, 'queued', 0, 'Queued', '{}', '')
                """,
                ("rerender_test", "clip_1", "remotion", "production", "profiles/nourbit_opus_style.json"),
            )
            conn.commit()
            conn.close()

            milestones = []

            def fake_rerender_candidate(*args, **kwargs):
                progress = kwargs["on_progress"]
                progress(12, "Loading clip data")
                progress(34, "Preparing render contract")
                progress(82, "Running render QA checks")
                milestones.extend([12, 34, 82])
                return {"candidate_id": "clip_1", "status": "rendered", "output_path": "/tmp/out.mp4"}

            with patch("media_engine.rerender.rerender_candidate", side_effect=fake_rerender_candidate):
                _run_rerender_job(
                    "rerender_test",
                    "clip_1",
                    "remotion",
                    "production",
                    "profiles/nourbit_opus_style.json",
                    None,
                    None,
                    db_path,
                )

            job = get_rerender_job("rerender_test", db_path)

        self.assertEqual(milestones, [12, 34, 82])
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress"], 100)
        self.assertEqual(job["message"], "Render updated")
        self.assertEqual(job["result"]["candidate_id"], "clip_1")


if __name__ == "__main__":
    unittest.main()
