"""Postiz publish for still and carousel content packages."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine.content_package import ContentPackage, PackageArtifacts
from media_engine.content_package_publish import publish_content_package, resolve_publish_platform
from media_engine.content_package_store import save_package


class ContentPackagePublishImagesTests(unittest.TestCase):
    def test_resolve_platform_prefers_mapped_instagram_for_still(self):
        pkg = ContentPackage(
            id="p1",
            profile_id="test",
            format="still",
            job="inform",
            source_kind="topic",
            source_ref="x",
            caption="cap",
        )
        with patch("media_engine.content_package_publish.channel_id_for_platform", side_effect=lambda plat, _pid: "ig1" if plat == "instagram" else ""):
            self.assertEqual(resolve_publish_platform(pkg, "telegram_channel", "test"), "instagram")

    def test_publish_still_uploads_single_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            img = Path(tmp) / "still.png"
            img.write_bytes(b"\x89PNG\r\n" + b"x" * 200)
            pkg = ContentPackage(
                id="pkg_still",
                profile_id="test",
                format="still",
                job="inform",
                source_kind="topic",
                source_ref="brief",
                caption="Caption",
                artifacts=PackageArtifacts(image_paths=[str(img)]),
                status="approved",
            )
            save_package(pkg, db_path=db)

            with patch(
                "media_engine.content_package_publish.publish_images",
                return_value={"status": "accepted", "remote_id": "post1", "remote_url": ""},
            ) as mock_publish:
                result = publish_content_package(
                    "pkg_still",
                    platform="instagram",
                    profile_id="test",
                    db_path=db,
                )
            mock_publish.assert_called_once()
            paths = mock_publish.call_args.args[1]["image_paths"]
            self.assertEqual(paths, [str(img)])
            self.assertEqual(result["format"], "still")
            self.assertEqual(result["status"], "accepted")

    def test_publish_carousel_requires_three_slides(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            slides = []
            for i in range(3):
                path = Path(tmp) / f"s{i}.png"
                path.write_bytes(b"\x89PNG" + bytes([i]) * 100)
                slides.append(str(path))
            pkg = ContentPackage(
                id="pkg_car",
                profile_id="test",
                format="carousel",
                job="teach",
                source_kind="topic",
                source_ref="brief",
                caption="Carousel caption",
                artifacts=PackageArtifacts(slide_paths=slides),
                status="approved",
            )
            save_package(pkg, db_path=db)

            with patch(
                "media_engine.content_package_publish.publish_images",
                return_value={"status": "accepted", "remote_id": "post2", "remote_url": ""},
            ) as mock_publish:
                publish_content_package("pkg_car", platform="instagram", profile_id="test", db_path=db)
            self.assertEqual(len(mock_publish.call_args.args[1]["image_paths"]), 3)


if __name__ == "__main__":
    unittest.main()
