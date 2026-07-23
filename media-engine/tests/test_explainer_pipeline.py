import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from media_engine import db as db_mod
from media_engine import explainer_pipeline as pipeline
from media_engine import explainer_stitch as stitch
from media_engine.explainer_stitch import render_title_card, stitch_segments


class ExplainerPipelineTests(unittest.TestCase):
    def test_title_card_and_stitch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = root / "a.mp4"
            b = root / "b.mp4"
            render_title_card(output_path=a, headline="Hello", narration="World", duration=2)
            render_title_card(output_path=b, headline="Next", duration=2)
            out = root / "final.mp4"
            stitch_segments([a, b], out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 1000)

    def _patched(self, db_path: Path, artifacts: Path) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch.object(db_mod, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(db_mod, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(pipeline, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(pipeline, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(stitch, "ARTIFACTS_DIR", artifacts))
        return stack

    def test_create_and_run_without_avatar_fails_clearly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "test.sqlite"
            artifacts = tmp_path / "artifacts"
            with self._patched(db_path, artifacts):
                created = pipeline.create_explainer_job(topic="Bitcoin", db_path=db_path)
                job_id = created["job_id"]
                with self.assertRaises(FileNotFoundError):
                    pipeline.run_explainer(job_id=job_id, prefer_hyperframes=False, db_path=db_path)

    def test_run_with_placeholder_avatar_clips_registers_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "test.sqlite"
            artifacts = tmp_path / "artifacts"
            with self._patched(db_path, artifacts):
                created = pipeline.create_explainer_job(topic="Bitcoin", db_path=db_path)
                job_id = created["job_id"]
                fixtures = Path(created["fixtures_dir"])
                plan = json.loads((artifacts / "workspace" / "explainers" / job_id / "scenes.json").read_text(encoding="utf-8"))
                for scene in plan["scenes"]:
                    if scene["type"] != "avatar":
                        continue
                    name = scene.get("clip_file") or f"{scene['id']}.mp4"
                    render_title_card(
                        output_path=fixtures / name,
                        headline="Avatar stand-in",
                        narration=scene.get("script", ""),
                        duration=min(4.0, float(scene.get("duration_target") or 4)),
                        label="AVATAR",
                    )
                result = pipeline.run_explainer(job_id=job_id, prefer_hyperframes=False, db_path=db_path)
                self.assertEqual(result["status"], "rendered")
                self.assertTrue(Path(result["output_path"]).exists())
                self.assertTrue(result["candidate_id"])
                queue = pipeline.list_review_queue(db_path=db_path)
                self.assertTrue(any(item["id"] == result["candidate_id"] for item in queue))


if __name__ == "__main__":
    unittest.main()
