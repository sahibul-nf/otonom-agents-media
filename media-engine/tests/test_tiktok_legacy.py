"""TikTok native OAuth removed — disconnect keys and legacy helper gate."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from media_engine.credential_vault import get_profile_secrets, set_profile_secrets, unset_profile_secrets

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "tiktok_oauth_helper.py"

TIKTOK_KEYS = [
    "TIKTOK_ACCESS_TOKEN",
    "TIKTOK_REFRESH_TOKEN",
    "TIKTOK_OPEN_ID",
    "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET",
]


class TikTokLegacyTests(unittest.TestCase):
    def test_disconnect_clears_tiktok_vault_keys(self):
        profile = "test_tiktok_disconnect"
        set_profile_secrets(
            profile,
            {k: f"value-{k}" for k in TIKTOK_KEYS},
        )
        unset_profile_secrets(profile, TIKTOK_KEYS)
        secrets = get_profile_secrets(profile)
        for key in TIKTOK_KEYS:
            self.assertNotIn(key, secrets)

    def test_oauth_helper_exits_without_legacy_flag(self):
        if not HELPER.is_file():
            self.skipTest("helper script missing")
        completed = subprocess.run(
            [sys.executable, str(HELPER)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("disabled", (completed.stderr + completed.stdout).lower())


if __name__ == "__main__":
    unittest.main()
