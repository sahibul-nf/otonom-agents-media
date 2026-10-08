"""Content package schema and validation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from media_engine.content_package import (
    ContentPackage,
    PackageArtifacts,
    apply_qa_status,
    stub_generate_package,
    validate_package,
)
from media_engine.content_package_service import (
    create_content_package,
    create_content_packages_batch,
    get_content_package,
    parse_create_formats,
)
from media_engine.content_package_store import approve_package, list_packages


class ContentPackageTests(unittest.TestCase):
    def test_carousel_rejects_two_slides(self):
        pkg = stub_generate_package(
            profile_id="test",
            format="carousel",
            source_ref="https://youtube.com/watch?v=abc12345678",
        )
        pkg.artifacts.slide_paths = ["a.png", "b.png"]
        qa = validate_package(pkg)
        self.assertFalse(qa.passed)
        self.assertTrue(any("3–5" in e for e in qa.errors))

    def test_clip_requires_parent(self):
        pkg = stub_generate_package(
            profile_id="test",
            format="clip",
            source_ref="x",
            parent_package_id="",
        )
        qa = validate_package(pkg)
        self.assertFalse(qa.passed)

    def test_short_requires_video(self):
        pkg = ContentPackage(
            id="p1",
            profile_id="test",
            format="short",
            job="inform",
            source_kind="youtube",
            source_ref="u",
            caption="cap",
            video_engine="av_explainer",
            artifacts=PackageArtifacts(),
        )
        qa = validate_package(pkg)
        self.assertFalse(qa.passed)

    def test_text_only_ready_for_review(self):
        pkg = stub_generate_package(
            profile_id="test",
            format="text_only",
            source_ref="https://youtu.be/abc12345678",
        )
        self.assertEqual(pkg.status, "ready_for_review")
        self.assertTrue(pkg.qa.passed)

    def test_create_and_get_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            created = create_content_package(
                format="text_only",
                source_ref="https://youtube.com/watch?v=dQw4w9WgXcQ",
                db_path=db,
            )
            loaded = get_content_package(created["id"], db_path=db)
            self.assertEqual(loaded["id"], created["id"])
            rows = list_packages(db_path=db)
            self.assertEqual(len(rows), 1)

    def test_parse_create_formats_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_create_formats()

    def test_parse_create_formats_clip_requires_parent(self):
        with self.assertRaises(ValueError):
            parse_create_formats(format="clip", parent_package_id="")

    def test_batch_create_multiple_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            batch = create_content_packages_batch(
                formats=["text_only", "still"],
                source_kind="topic",
                topic="AI regulation brief",
                llm_provider="none",
                db_path=db,
            )
            self.assertEqual(len(batch["packages"]), 2)
            self.assertTrue(batch["batch_id"])
            ids = {p["format"] for p in batch["packages"]}
            self.assertEqual(ids, {"text_only", "still"})
            for pkg in batch["packages"]:
                self.assertEqual(pkg["meta"]["batch_id"], batch["batch_id"])
                self.assertEqual(pkg["meta"]["batch_formats"], ["text_only", "still"])
            rows = list_packages(db_path=db)
            self.assertEqual(len(rows), 2)

    def test_approve_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            created = create_content_package(
                format="text_only",
                source_ref="https://youtube.com/watch?v=dQw4w9WgXcQ",
                db_path=db,
            )
            approved = approve_package(created["id"], db_path=db)
            self.assertEqual(approved.status, "approved")


if __name__ == "__main__":
    unittest.main()
