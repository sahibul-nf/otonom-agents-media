"""CONTENT_OS_PATH wordmark resolution."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine.brand_pack import resolve_brand_assets, resolve_wordmark_path


class BrandPackAssetTests(unittest.TestCase):
    def test_wordmark_resolves_under_content_os(self):
        with tempfile.TemporaryDirectory() as tmp:
            mark = Path(tmp) / "techtalk-production" / "brand" / "techtalk-intel-wordmark-cropped.png"
            mark.parent.mkdir(parents=True)
            mark.write_bytes(b"\x89PNG\r\n")
            with patch.dict(os.environ, {"CONTENT_OS_PATH": tmp}, clear=False):
                resolved = resolve_wordmark_path(preset="techtalk")
            self.assertEqual(resolved, mark)

    def test_missing_content_os_returns_none(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("CONTENT_OS_PATH", None)
            self.assertIsNone(resolve_wordmark_path(preset="techtalk"))

    def test_brand_assets_dataclass(self):
        with tempfile.TemporaryDirectory() as tmp:
            logo = Path(tmp) / "techtalk-production" / "brand" / "techtalk-intel-logo.png"
            logo.parent.mkdir(parents=True)
            logo.write_bytes(b"\x89PNG")
            with patch.dict(os.environ, {"CONTENT_OS_PATH": tmp}, clear=False):
                assets = resolve_brand_assets(preset="techtalk")
            self.assertEqual(assets.wordmark_path, logo)
            self.assertEqual(assets.logo_path, logo)


if __name__ == "__main__":
    unittest.main()
