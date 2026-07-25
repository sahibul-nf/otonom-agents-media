"""Tests for Path A Cursor trigger → poll → URL extract helpers."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from media_engine.cursor_cloud import (
    CursorCloudConfig,
    build_path_a_prompt,
    create_agent,
    extract_video_url,
    parse_agent_run_ids,
)
from media_engine.path_a_jobs import read_path_a_status, start_path_a_generate


class CursorCloudHelpersTests(unittest.TestCase):
    def test_extract_video_url_prefers_marker(self):
        text = "done\nVIDEO_URL: https://files2.heygen.ai/foo/bar.mp4?x=1\nTITLE: Hi"
        self.assertEqual(extract_video_url(text), "https://files2.heygen.ai/foo/bar.mp4?x=1")

    def test_extract_heygen_fallback(self):
        text = "Ready at https://files2.heygen.ai/path/video.mp4 thanks"
        url = extract_video_url(text)
        assert url is not None
        self.assertTrue(url.startswith("https://files2.heygen.ai/"))

    def test_parse_agent_run_ids_from_create_response(self):
        agent_id, run_id = parse_agent_run_ids(
            {
                "agent": {"id": "bc-11111111-1111-1111-1111-111111111111", "latestRunId": "run-aaa"},
                "run": {"id": "run-bbb", "agentId": "bc-11111111-1111-1111-1111-111111111111"},
            }
        )
        self.assertEqual(agent_id, "bc-11111111-1111-1111-1111-111111111111")
        self.assertEqual(run_id, "run-bbb")

    def test_build_prompt_includes_marker_instruction(self):
        prompt = build_path_a_prompt(topic="Bitcoin ETF", title="ETF 101", job_id="patha_abc")
        self.assertIn("VIDEO_URL:", prompt)
        self.assertIn("OTONOM_JOB_ID: patha_abc", prompt)
        self.assertIn("Bitcoin ETF", prompt)

    def test_dry_run_create_agent(self):
        cfg = CursorCloudConfig(
            api_key="",
            dry_run=True,
            dry_run_video_url="https://example.com/v.mp4",
        )
        payload = create_agent("hello", config=cfg, name="test")
        self.assertTrue(payload.get("dry_run"))
        self.assertEqual(payload["run"]["status"], "FINISHED")
        self.assertIn("VIDEO_URL:", payload["run"]["result"])


class PathAJobPipelineTests(unittest.TestCase):
    def test_dry_run_pipeline_notifies_after_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            jobs_root = Path(tmp) / "path_a_jobs"

            def fake_job_dir(job_id: str, profile_id: str = "nourbit") -> Path:
                path = jobs_root / job_id
                path.mkdir(parents=True, exist_ok=True)
                return path

            def fake_jobs_root(profile_id: str = "nourbit") -> Path:
                jobs_root.mkdir(parents=True, exist_ok=True)
                return jobs_root

            cfg = CursorCloudConfig(
                api_key="unused",
                dry_run=True,
                dry_run_video_url="https://files2.heygen.ai/dry/video.mp4",
                timeout_seconds=30,
                poll_interval_seconds=0.05,
            )

            with mock.patch("media_engine.path_a_jobs.path_a_job_dir", fake_job_dir):
                with mock.patch("media_engine.path_a_jobs.path_a_jobs_root", fake_jobs_root):
                    with mock.patch(
                        "media_engine.path_a_jobs.ingest_longform",
                        return_value={"ok": True, "job_id": "ingest_test", "candidate_ids": ["cand_1"]},
                    ) as ingest:
                        with mock.patch(
                            "media_engine.path_a_jobs.send_status_telegram",
                            return_value={"ok": True},
                        ) as notify:
                            job = start_path_a_generate(
                                topic="Dry Path A",
                                title="Dry Path A",
                                config=cfg,
                            )
                            job_id = job["job_id"]
                            deadline = time.time() + 15
                            final = None
                            while time.time() < deadline:
                                final = read_path_a_status(job_id)
                                if final.get("status") in {"ready", "failed"}:
                                    break
                                time.sleep(0.05)

            self.assertIsNotNone(final)
            assert final is not None
            self.assertEqual(final["status"], "ready", final.get("error"))
            self.assertEqual(final["candidate_ids"], ["cand_1"])
            self.assertTrue(final.get("telegram_notified"))
            ingest.assert_called_once()
            self.assertEqual(
                ingest.call_args.kwargs.get("source") or ingest.call_args[1].get("source"),
                "https://files2.heygen.ai/dry/video.mp4",
            )
            notify.assert_called()
            self.assertIn("Review", notify.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
