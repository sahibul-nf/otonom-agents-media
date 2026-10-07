"""Postiz text-only post body."""

from __future__ import annotations

import unittest

from media_engine.postiz_client import build_create_text_post_body


class PostizTextPostTests(unittest.TestCase):
    def test_text_body_has_no_image(self):
        body = build_create_text_post_body(
            integration_id="int_1",
            caption="Hello world",
            platform="telegram_channel",
            title="Hello",
        )
        value = body["posts"][0]["value"][0]
        self.assertEqual(value["content"], "Hello world")
        self.assertNotIn("image", value)


if __name__ == "__main__":
    unittest.main()
