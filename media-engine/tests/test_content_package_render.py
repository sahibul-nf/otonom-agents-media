"""Still and carousel PNG rendering for content packages."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from media_engine.content_package import stub_generate_package, validate_package
from media_engine.content_package_render import attach_render_artifacts
from media_engine.db import ARTIFACTS_DIR


class ContentPackageRenderTests(unittest.TestCase):
    def test_still_png_meets_min_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = ARTIFACTS_DIR
            try:
                import media_engine.content_package_render as render_mod
                import media_engine.content_package_still_render as still_mod

                object.__setattr__(render_mod, "ARTIFACTS_DIR", Path(tmp))
                object.__setattr__(still_mod, "ARTIFACTS_DIR", Path(tmp))

                pkg = stub_generate_package(
                    profile_id="test",
                    format="still",
                    source_ref="topic brief",
                    brand_preset="techtalk",
                )
                pkg.title = "Bitcoin issuance cap"
                pkg.caption = "Why the hard cap still matters for holders."
                pkg = attach_render_artifacts(pkg, source_text="", db_path=Path(tmp) / "x.sqlite")
                path = Path(pkg.artifacts.image_paths[0])
                self.assertTrue(path.is_file())
                self.assertGreater(path.stat().st_size, 15_000)
                from PIL import Image

                with Image.open(path) as img:
                    self.assertGreaterEqual(img.width, 1080)
                    self.assertGreaterEqual(img.height, 1080)
                qa = validate_package(pkg)
                self.assertTrue(qa.passed)
            finally:
                object.__setattr__(render_mod, "ARTIFACTS_DIR", prev)
                object.__setattr__(still_mod, "ARTIFACTS_DIR", prev)

    def test_carousel_produces_three_pngs(self):
        with tempfile.TemporaryDirectory() as tmp:
            prev = ARTIFACTS_DIR
            try:
                import media_engine.content_package_render as render_mod
                import media_engine.content_package_still_render as still_mod

                object.__setattr__(render_mod, "ARTIFACTS_DIR", Path(tmp))
                object.__setattr__(still_mod, "ARTIFACTS_DIR", Path(tmp))

                pkg = stub_generate_package(
                    profile_id="test",
                    format="carousel",
                    source_ref="brief",
                    brand_preset="blank",
                )
                pkg.artifacts.package_meta = {
                    "slide_texts": ["Point one", "Point two", "Point three"],
                }
                pkg = attach_render_artifacts(pkg, source_text="", db_path=Path(tmp) / "x.sqlite")
                self.assertEqual(len(pkg.artifacts.slide_paths), 3)
                for slide in pkg.artifacts.slide_paths:
                    p = Path(slide)
                    self.assertTrue(p.is_file())
                    self.assertGreater(p.stat().st_size, 15_000)
                qa = validate_package(pkg)
                self.assertTrue(qa.passed)
            finally:
                object.__setattr__(render_mod, "ARTIFACTS_DIR", prev)
                object.__setattr__(still_mod, "ARTIFACTS_DIR", prev)


if __name__ == "__main__":
    unittest.main()
