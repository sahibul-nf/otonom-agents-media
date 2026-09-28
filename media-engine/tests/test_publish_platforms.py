"""Publish destination availability."""

from __future__ import annotations

import unittest

from media_engine.publish_platforms import (
    filter_operator_platforms,
    is_operator_publish_platform,
    is_publish_platform_disabled,
)


class PublishPlatformAvailabilityTests(unittest.TestCase):
    def test_tiktok_is_disabled_but_visible_in_catalog(self):
        self.assertTrue(is_publish_platform_disabled("tiktok"))
        self.assertFalse(is_operator_publish_platform("tiktok"))
        self.assertEqual(
            filter_operator_platforms(
                ["telegram_channel", "youtube_shorts", "tiktok", "facebook_reels"],
            ),
            ["telegram_channel", "youtube_shorts", "facebook_reels"],
        )


if __name__ == "__main__":
    unittest.main()
