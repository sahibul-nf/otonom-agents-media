import tempfile
import unittest
from pathlib import Path
from unittest import mock

from media_engine.heygen_client import (
    HeyGenApiError,
    HeyGenConfig,
    create_avatar_video,
    create_video_agent_session,
    estimate_cost_usd,
    estimate_script_seconds,
    generate_avatar_clips_for_scenes,
    require_api_key,
)
from media_engine.ingest_longform import ingest_longform, materialize_longform_source
from media_engine.explainer_stitch import render_title_card


class IngestLongformTests(unittest.TestCase):
    def test_materialize_local_and_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "sample.mp4"
            render_title_card(
                output_path=src,
                headline="Ingest sample",
                narration="Path A delivery test.",
                duration=2.0,
                scene_type="text",
            )
            db = root / "test.sqlite"
            # Patch ARTIFACTS_DIR via materialize under tmp by copying through ingest with db only —
            # ingest writes under real ARTIFACTS_DIR; use review_only against local file.
            result = ingest_longform(
                source=str(src),
                mode="review_only",
                title="Sample long-form",
                db_path=db,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["mode"], "review_only")
            self.assertEqual(len(result["candidate_ids"]), 1)
            self.assertTrue(Path(result["local_path"]).exists())


class HeyGenClientScaffoldTests(unittest.TestCase):
    def test_require_api_key_fails_without_env(self):
        with mock.patch.dict("os.environ", {"HEYGEN_API_KEY": "", "HEYGEN_API_DRY_RUN": ""}, clear=False):
            with self.assertRaises(HeyGenApiError):
                require_api_key(HeyGenConfig(api_key="", dry_run=False))

    def test_dry_run_create_session(self):
        cfg = HeyGenConfig(api_key="", dry_run=True)
        payload = create_video_agent_session(
            prompt="Test Path B dry run",
            config=cfg,
        )
        self.assertTrue(payload.get("dry_run"))
        self.assertEqual(payload.get("path"), "/v3/video-agents")

    def test_dry_run_create_avatar_video(self):
        cfg = HeyGenConfig(api_key="", dry_run=True)
        payload = create_avatar_video(script="Halo TechTalk.", title="clip", config=cfg)
        self.assertTrue(payload.get("dry_run"))
        self.assertEqual(payload.get("path"), "/v3/videos")
        self.assertEqual(payload["body"]["engine"]["type"], "avatar_iii")
        self.assertEqual(payload["body"]["avatar_id"], "0f4dca86e0bd42d8a8afdae9948338ce")

    def test_cost_guard_blocks_oversized_batch(self):
        scenes = [
            {"type": "avatar", "id": f"a{i}", "script": "kata " * 40, "duration_target": 20}
            for i in range(8)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(HeyGenApiError) as ctx:
                generate_avatar_clips_for_scenes(
                    scenes,
                    Path(tmp),
                    config=HeyGenConfig(api_key="", dry_run=True),
                    max_seconds=30,
                )
            self.assertIn("cost guard", str(ctx.exception).lower())

    def test_dry_run_batch_estimates_without_files(self):
        scenes = [
            {"type": "avatar", "id": "hook", "script": "Satu dua tiga empat lima."},
            {"type": "text", "id": "card", "headline": "Ignore"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            result = generate_avatar_clips_for_scenes(
                scenes,
                Path(tmp),
                config=HeyGenConfig(api_key="x", dry_run=True),
                max_seconds=90,
            )
            self.assertTrue(result["dry_run"])
            self.assertEqual(len(result["clips"]), 1)
            self.assertGreater(result["estimated_usd"], 0)
            self.assertFalse(list(Path(tmp).glob("*.mp4")))

    def test_estimate_helpers(self):
        self.assertGreaterEqual(estimate_script_seconds("satu dua tiga"), 5.0)
        self.assertEqual(estimate_cost_usd(10, usd_per_second=0.05), 0.5)


if __name__ == "__main__":
    unittest.main()
