import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine.hyperframes_oss import HYPERFRAMES_DIR, _brand_vars, _sanitize_vendored_html
from media_engine.styles import persist_brand_social_assets, resolve_brand_asset_path


class BrandSocialProfileTests(unittest.TestCase):
    def test_brand_vars_use_custom_handle_and_follower_count(self):
        brand = _brand_vars(
            {
                "style": {
                    "brand": {
                        "watermark_text": "Nourbit Clips",
                        "social_handle": "nourbit.official",
                        "social_follower_count": "18.2K followers",
                    }
                }
            }
        )
        self.assertEqual(brand["handle"], "@nourbit.official")
        self.assertEqual(brand["follower_count"], "18.2K followers")
        self.assertEqual(brand["hide_follower_count"], "0")

    def test_brand_vars_hide_follower_count_when_optional_empty(self):
        brand = _brand_vars({"style": {"brand": {"watermark_text": "Brand Clips"}}})
        self.assertEqual(brand["hide_follower_count"], "1")

    def test_sanitize_instagram_follow_replaces_handle_and_hides_followers(self):
        raw = (HYPERFRAMES_DIR / "compositions/instagram-follow.html").read_text(encoding="utf-8")
        brand = _brand_vars(
            {
                "style": {
                    "brand": {
                        "watermark_text": "Nourbit Clips",
                        "social_handle": "@nourbitclips",
                    }
                }
            }
        )
        html = _sanitize_vendored_html(raw, brand)
        self.assertIn("@nourbitclips", html)
        self.assertNotIn("@heygen_official", html)
        self.assertIn('data-brand-social-hide="counts"', html)

    def test_sanitize_x_post_uses_short_branded_tweet_and_safe_offsets(self):
        raw = (HYPERFRAMES_DIR / "compositions/x-post.html").read_text(encoding="utf-8")
        brand = _brand_vars(
            {
                "style": {
                    "brand": {
                        "watermark_text": "Nourbit Clips",
                        "social_handle": "@nourbitclips",
                    }
                }
            }
        )
        html = _sanitize_vendored_html(raw, brand)
        self.assertIn("Nourbit Clips", html)
        self.assertIn("@nourbitclips", html)
        self.assertIn("New episode out now.", html)
        self.assertNotIn("Prompt to replace this text", html)
        self.assertNotIn("y: 400", html)
        self.assertNotIn("y: 64", html)
        self.assertIn("gsap.set(card, { opacity: 0 });", html)

    def test_persist_brand_social_assets_writes_avatar_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            profiles = Path(tmp) / "profiles"
            profiles.mkdir()
            data_url = (
                "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            )
            with patch("media_engine.styles.ROOT", profiles.parent), patch("media_engine.styles.PROFILES_DIR", profiles):
                style = persist_brand_social_assets(
                    {
                        "brand": {
                            "watermark_text": "Demo",
                            "social_handle": "@demo",
                            "social_avatar_data_url": data_url,
                        }
                    },
                    "custom_demo_brand",
                )
                asset = style["brand"]["social_avatar_asset"]
                self.assertTrue((profiles / "assets" / "custom_demo_brand" / "social-avatar.jpg").exists())
                resolved = resolve_brand_asset_path(asset)
            self.assertTrue(resolved.exists())


if __name__ == "__main__":
    unittest.main()
