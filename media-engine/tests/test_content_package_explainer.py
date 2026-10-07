"""Explainer job completion sync for short/long content packages."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from media_engine.content_package import ContentPackage, PackageArtifacts, apply_qa_status
from media_engine.content_package_explainer import (
    notify_explainer_render_complete,
    refresh_package_explainer_artifacts,
)
from media_engine.content_package_store import get_package, save_package
from media_engine.explainer_stitch import explainer_artifact_dir


class ContentPackageExplainerSyncTests(unittest.TestCase):
    def test_notify_render_complete_updates_video_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            profile_id = "test"
            job_id = "job_sync_1"
            root = explainer_artifact_dir(profile_id, job_id)
            root.mkdir(parents=True, exist_ok=True)
            final = root / "final.mp4"
            final.write_bytes(b"\x00\x00\x01\x00" * 200)

            (root / "status.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "profile_id": profile_id,
                        "status": "planned",
                        "content_package_id": "pkg_expl_1",
                    }
                ),
                encoding="utf-8",
            )

            pkg = ContentPackage(
                id="pkg_expl_1",
                profile_id=profile_id,
                format="short",
                job="inform",
                source_kind="topic",
                source_ref="sync test",
                caption="Caption for short.",
                video_engine="av_explainer",
                artifacts=PackageArtifacts(
                    video_path=str(root / "pending_explainer.mp4"),
                    package_meta={"explainer_job_id": job_id, "explainer_status": "planned"},
                ),
            )
            (root / "pending_explainer.mp4").write_bytes(b"")
            save_package(apply_qa_status(pkg), db_path=db)

            updated = notify_explainer_render_complete(
                job_id=job_id,
                profile_id=profile_id,
                output_path=final,
                duration_seconds=12.5,
                db_path=db,
            )
            self.assertEqual(updated, ["pkg_expl_1"])

            loaded = get_package("pkg_expl_1", db_path=db)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.artifacts.video_path, str(final))
            self.assertEqual(loaded.artifacts.package_meta.get("explainer_status"), "rendered")
            self.assertTrue(loaded.qa.passed)
            self.assertEqual(loaded.status, "ready_for_review")

    def test_refresh_polls_explainer_status_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            profile_id = "test"
            job_id = "job_poll_1"
            root = explainer_artifact_dir(profile_id, job_id)
            root.mkdir(parents=True, exist_ok=True)
            final = root / "final.mp4"
            final.write_bytes(b"\x00\x00\x01\x00" * 100)
            (root / "status.json").write_text(
                json.dumps(
                    {
                        "job_id": job_id,
                        "profile_id": profile_id,
                        "status": "rendered",
                        "output_path": str(final),
                        "content_package_id": "pkg_poll",
                    }
                ),
                encoding="utf-8",
            )

            pkg = ContentPackage(
                id="pkg_poll",
                profile_id=profile_id,
                format="long_form",
                job="teach",
                source_kind="topic",
                source_ref="poll",
                caption="Long caption.",
                title="Long title",
                video_engine="av_explainer",
                artifacts=PackageArtifacts(
                    video_path=str(root / "pending.mp4"),
                    package_meta={"explainer_job_id": job_id, "explainer_status": "rendering"},
                ),
            )
            (root / "pending.mp4").write_bytes(b"")
            save_package(apply_qa_status(pkg), db_path=db)

            refreshed = refresh_package_explainer_artifacts(pkg, db_path=db)
            self.assertEqual(refreshed.artifacts.video_path, str(final))
            self.assertEqual(refreshed.artifacts.package_meta.get("explainer_status"), "rendered")


if __name__ == "__main__":
    unittest.main()
