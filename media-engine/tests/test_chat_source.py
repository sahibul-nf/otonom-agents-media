"""Chat source sanitization."""

from __future__ import annotations

import unittest

from media_engine.chat_source import sanitize_chat_transcript


class ChatSourceTests(unittest.TestCase):
    def test_strips_secrets_and_noise(self):
        raw = """
        user: hello team
        assistant: sure
        Contact me at secret@example.com or +62 812 3456 7890
        fakekey-abcdefghijklmnopqrstuvwxyz1234567890
        """ + ("word " * 20)
        out = sanitize_chat_transcript(raw)
        self.assertNotIn("secret@example.com", out)
        self.assertIn("[email]", out)
        self.assertIn("[redacted-secret]", out)
        self.assertNotIn("user:", out.lower())


if __name__ == "__main__":
    unittest.main()
