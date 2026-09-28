import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from media_engine import db as db_mod
from media_engine import explainer_pipeline as pipeline
from media_engine import explainer_stitch as stitch
from media_engine import review_server


class SceneEditorBackendTests(unittest.TestCase):
    def _patched(self, db_path: Path, artifacts: Path) -> ExitStack:
        stack = ExitStack()
        stack.enter_context(patch.object(db_mod, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(db_mod, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(pipeline, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(pipeline, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(stitch, "ARTIFACTS_DIR", artifacts))
        stack.enter_context(patch.object(review_server, "DEFAULT_DB", db_path))
        stack.enter_context(patch.object(review_server, "ARTIFACTS_DIR", artifacts))
        return stack

    def _create_candidate(self, db_path: Path) -> tuple[dict, str]:
        created = pipeline.create_explainer_job(
            topic="Scene editor",
            hyperframes_template="techtalk_explainer",
            db_path=db_path,
        )
        plan = json.loads(Path(created["plan_path"]).read_text(encoding="utf-8"))
        output = Path(created["plan_path"]).parent / "final.mp4"
        conn = db_mod.connect(db_path)
        candidate_id = pipeline.register_explainer_in_review(
            conn,
            job_id=created["job_id"],
            profile_id=created["profile_id"],
            plan=plan,
            output_path=output,
            duration_seconds=30,
        )
        return created, candidate_id

    def test_context_resolves_trusted_explainer_job_and_other_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.sqlite"
            artifacts = root / "artifacts"
            with self._patched(db_path, artifacts):
                _created, candidate_id = self._create_candidate(db_path)
                context = review_server.get_editor_context(candidate_id, db_path=db_path)
                self.assertEqual(context["capability"], "scene")
                self.assertTrue(context["can_edit_scenes"])
                self.assertFalse(context["can_trim"])
                self.assertEqual(context["job"]["status"], "planned")
                self.assertIn("plan", context)

                conn = db_mod.connect(db_path)
                conn.execute(
                    """
                    UPDATE clip_candidates
                    SET curation_metadata_json = ?, caption_source = ?
                    WHERE id = ?
                    """,
                    (json.dumps({"kind": "longform_ingest"}), "ingest_longform", candidate_id),
                )
                conn.commit()
                imported = review_server.get_editor_context(candidate_id, db_path=db_path)
                self.assertEqual(imported["capability"], "imported_longform")
                self.assertNotIn("plan", imported)

                conn.execute(
                    "UPDATE clip_candidates SET curation_metadata_json = '{}', caption_source = 'youtube' WHERE id = ?",
                    (candidate_id,),
                )
                conn.commit()
                short = review_server.get_editor_context(candidate_id, db_path=db_path)
                self.assertEqual(short["capability"], "short")
                self.assertTrue(short["can_trim"])
                self.assertNotIn("plan", short)

    def test_short_editor_context_includes_look_from_latest_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.sqlite"
            artifacts = root / "artifacts"
            with self._patched(db_path, artifacts):
                _created, candidate_id = self._create_candidate(db_path)
                conn = db_mod.connect(db_path)
                contract = {
                    "hyperframesTemplate": "spiritual_reflective",
                    "brandSystemTemplateId": "",
                    "hyperframesFormat": "short_9_16",
                }
                conn.execute(
                    "UPDATE clip_candidates SET curation_metadata_json = '{}', caption_source = 'youtube' WHERE id = ?",
                    (candidate_id,),
                )
                conn.execute(
                    """
                    INSERT INTO render_jobs
                      (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "render_short_1",
                        candidate_id,
                        "premium",
                        "center",
                        "caption",
                        "rendered",
                        str(artifacts / "out.mp4"),
                        json.dumps(contract),
                    ),
                )
                conn.commit()
                conn.close()
                context = review_server.get_editor_context(candidate_id, db_path=db_path)
                self.assertEqual(context["capability"], "short")
                self.assertIn("look", context)
                self.assertEqual(context["look"]["hyperframes_template"], "spiritual_reflective")

    def test_save_normalizes_reorder_add_delete_and_preserves_hidden_media(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.sqlite"
            artifacts = root / "artifacts"
            with self._patched(db_path, artifacts):
                created, candidate_id = self._create_candidate(db_path)
                plan_path = Path(created["plan_path"])
                original = json.loads(plan_path.read_text(encoding="utf-8"))
                original["scenes"][0]["audio_file"] = "scene_01.m4a"
                plan_path.write_text(json.dumps(original), encoding="utf-8")

                saved = pipeline.save_explainer_scene_plan(
                    candidate_id,
                    title=" Edited title ",
                    scenes=[
                        {
                            "id": "s02",
                            "type": "text",
                            "headline": "Moved first",
                            "duration_target": 99,
                        },
                        {
                            "id": "s01",
                            "type": "avatar",
                            "script": "Updated script",
                            "duration_target": 1,
                        },
                        {
                            "id": "new",
                            "type": "broll",
                            "headline": "New scene",
                            "duration_target": 8,
                        },
                    ],
                    db_path=db_path,
                )

                persisted = json.loads(plan_path.read_text(encoding="utf-8"))
                self.assertEqual([scene["id"] for scene in persisted["scenes"]], ["s02", "s01", "new"])
                self.assertEqual(persisted["title"], "Edited title")
                self.assertEqual(persisted["scenes"][0]["duration_target"], 30.0)
                self.assertEqual(persisted["scenes"][1]["duration_target"], 3.0)
                self.assertEqual(persisted["scenes"][1]["clip_file"], "scene_01.mp4")
                self.assertEqual(persisted["scenes"][1]["audio_file"], "scene_01.m4a")
                self.assertEqual(persisted["scenes"][2]["template"], "techtalk_intel_brief")
                self.assertEqual(persisted["hyperframes_template"], "techtalk_intel_brief")
                self.assertEqual(saved["status"]["status"], "planned")
                self.assertEqual(saved["status"]["scene_count"], 3)

    def test_rejects_untrusted_job_non_explainer_and_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.sqlite"
            artifacts = root / "artifacts"
            with self._patched(db_path, artifacts):
                created, candidate_id = self._create_candidate(db_path)
                conn = db_mod.connect(db_path)
                conn.execute(
                    "UPDATE clip_candidates SET curation_metadata_json = ? WHERE id = ?",
                    (json.dumps({"kind": "explainer", "job_id": "../../outside"}), candidate_id),
                )
                conn.commit()
                with self.assertRaisesRegex(ValueError, "invalid explainer job_id"):
                    pipeline.resolve_explainer_review_candidate(candidate_id, db_path=db_path)

                conn.execute(
                    "UPDATE clip_candidates SET curation_metadata_json = ? WHERE id = ?",
                    (json.dumps({"kind": "short"}), candidate_id),
                )
                conn.commit()
                with self.assertRaisesRegex(ValueError, "not an explainer"):
                    pipeline.save_explainer_scene_plan(
                        candidate_id,
                        title="No",
                        scenes=[{"id": "x", "type": "text", "headline": "No"}],
                        db_path=db_path,
                    )

                conn.execute(
                    "UPDATE clip_candidates SET curation_metadata_json = ?, status = 'published' WHERE id = ?",
                    (json.dumps({"kind": "explainer", "job_id": created["job_id"]}), candidate_id),
                )
                conn.commit()
                with self.assertRaisesRegex(ValueError, "published"):
                    pipeline.save_explainer_scene_plan(
                        candidate_id,
                        title="Locked",
                        scenes=[{"id": "x", "type": "text", "headline": "Locked"}],
                        db_path=db_path,
                    )

    def test_save_hands_off_async_full_rerender(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / "test.sqlite"
            artifacts = root / "artifacts"
            with self._patched(db_path, artifacts):
                created, candidate_id = self._create_candidate(db_path)
                plan = json.loads(Path(created["plan_path"]).read_text(encoding="utf-8"))
                rendering = {"status": "rendering", "job_id": created["job_id"]}
                with patch.object(pipeline, "start_explainer_run", return_value=rendering) as start:
                    saved = pipeline.save_explainer_scene_plan(
                        candidate_id,
                        title=plan["title"],
                        scenes=plan["scenes"],
                        rerender_after=True,
                        prefer_hyperframes=True,
                        db_path=db_path,
                    )
                self.assertTrue(saved["rerender_started"])
                self.assertEqual(saved["status"], rendering)
                start.assert_called_once_with(
                    job_id=created["job_id"],
                    profile_id=created["profile_id"],
                    prefer_hyperframes=True,
                    db_path=db_path,
                )


if __name__ == "__main__":
    unittest.main()
