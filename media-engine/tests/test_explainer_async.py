import json
import tempfile
import time
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from media_engine import db as db_mod
from media_engine import explainer_pipeline as pipeline
from media_engine import explainer_stitch as stitch
from media_engine.explainer_stitch import render_title_card


class ExplainerAsyncAndTemplateTests(unittest.TestCase):
    def _patched(self, db_path: Path, artifacts: Path) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch.object(db_mod, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(db_mod, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(pipeline, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(pipeline, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(stitch, "ARTIFACTS_DIR", artifacts))
        return stack

    def test_create_applies_techtalk_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "test.sqlite"
            artifacts = tmp_path / "artifacts"
            with self._patched(db_path, artifacts):
                created = pipeline.create_explainer_job(
                    topic="Bitcoin",
                    hyperframes_template="techtalk_explainer",
                    db_path=db_path,
                )
                plan = json.loads(Path(created["plan_path"]).read_text(encoding="utf-8"))
                self.assertEqual(plan["hyperframes_template"], "techtalk_intel_brief")
                text_scenes = [s for s in plan["scenes"] if s.get("type") in {"text", "broll"}]
                self.assertTrue(text_scenes)
                self.assertTrue(all(s.get("template") == "techtalk_intel_brief" for s in text_scenes))

    def test_start_explainer_run_async_registers_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            db_path = tmp_path / "test.sqlite"
            artifacts = tmp_path / "artifacts"
            with self._patched(db_path, artifacts):
                created = pipeline.create_explainer_job(topic="Bitcoin", db_path=db_path)
                job_id = created["job_id"]
                fixtures = Path(created["fixtures_dir"])
                plan = json.loads(Path(created["plan_path"]).read_text(encoding="utf-8"))
                for scene in plan["scenes"]:
                    if scene["type"] != "avatar":
                        continue
                    name = scene.get("clip_file") or f"{scene['id']}.mp4"
                    render_title_card(
                        output_path=fixtures / name,
                        headline="Avatar stand-in",
                        narration=scene.get("script", ""),
                        duration=min(3.0, float(scene.get("duration_target") or 3)),
                        label="AVATAR",
                    )
                started = pipeline.start_explainer_run(
                    job_id=job_id,
                    prefer_hyperframes=False,
                    db_path=db_path,
                )
                self.assertEqual(started["status"], "rendering")
                deadline = time.time() + 60
                status = started
                while time.time() < deadline:
                    status = pipeline.read_explainer_status(job_id)
                    if status.get("status") in {"rendered", "failed"}:
                        break
                    time.sleep(0.2)
                self.assertEqual(status["status"], "rendered", status.get("error"))
                self.assertTrue(status.get("candidate_id"))


if __name__ == "__main__":
    unittest.main()
