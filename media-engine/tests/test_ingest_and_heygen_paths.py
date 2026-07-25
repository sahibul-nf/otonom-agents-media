import tempfile
import unittest
from pathlib import Path
from unittest import mock

from media_engine.heygen_client import HeyGenApiError, HeyGenConfig, create_video_agent_session, require_api_key
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


if __name__ == "__main__":
    unittest.main()
