"""Workspace-scoped credential vault tests."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine import credential_vault as vault
from media_engine.live_publishers import _env_first


class CredentialVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault_dir = Path(self.tmp.name) / "credentials"
        self.vault_dir.mkdir(parents=True)
        self._patchers = [
            patch.object(vault, "VAULT_DIR", self.vault_dir),
        ]
        for item in self._patchers:
            item.start()

    def tearDown(self) -> None:
        for item in self._patchers:
            item.stop()
        self.tmp.cleanup()

    def test_set_and_resolve_are_profile_scoped(self):
        vault.set_profile_secrets("nourbit", {"META_PAGE_ACCESS_TOKEN": "nourbit-token", "META_PAGE_ID": "111"})
        vault.set_profile_secrets("workspace", {"META_PAGE_ACCESS_TOKEN": "workspace-token", "META_PAGE_ID": "222"})

        with vault.use_profile_credentials("nourbit"):
            self.assertEqual(_env_first("META_PAGE_ACCESS_TOKEN"), "nourbit-token")
            self.assertEqual(_env_first("META_PAGE_ID"), "111")
        with vault.use_profile_credentials("workspace"):
            self.assertEqual(_env_first("META_PAGE_ACCESS_TOKEN"), "workspace-token")
            self.assertEqual(_env_first("META_PAGE_ID"), "222")

    def test_account_keys_do_not_leak_from_global_env_when_profile_active(self):
        os.environ["META_PAGE_ACCESS_TOKEN"] = "global-token"
        vault.set_profile_secrets("nourbit", {"META_PAGE_ACCESS_TOKEN": "vault-token"})
        with vault.use_profile_credentials("workspace"):
            # workspace vault empty → must not fall back to global account token
            self.assertEqual(_env_first("META_PAGE_ACCESS_TOKEN"), "")
        with vault.use_profile_credentials("nourbit"):
            self.assertEqual(_env_first("META_PAGE_ACCESS_TOKEN"), "vault-token")
        os.environ.pop("META_PAGE_ACCESS_TOKEN", None)

    def test_credential_status_per_profile(self):
        os.environ["YOUTUBE_CLIENT_ID"] = "cid"
        os.environ["YOUTUBE_CLIENT_SECRET"] = "secret"
        vault.set_profile_secrets("nourbit", {"YOUTUBE_REFRESH_TOKEN": "refresh-n"})
        status_n = vault.credential_status_for_profile("nourbit")
        status_w = vault.credential_status_for_profile("workspace")
        self.assertTrue(status_n["platforms"]["youtube_shorts"]["ready"])
        self.assertFalse(status_w["platforms"]["youtube_shorts"]["ready"])
        self.assertIn("YOUTUBE_REFRESH_TOKEN", status_w["platforms"]["youtube_shorts"]["missing_keys"][0] or "YOUTUBE_REFRESH_TOKEN")
        os.environ.pop("YOUTUBE_CLIENT_ID", None)
        os.environ.pop("YOUTUBE_CLIENT_SECRET", None)

    def test_migrate_env_file_once(self):
        env_path = Path(self.tmp.name) / ".env.local"
        env_path.write_text(
            "\n".join(
                [
                    "META_PAGE_ID=999",
                    "META_PAGE_ACCESS_TOKEN=from_env",
                    "TELEGRAM_BOT_TOKEN=tg",
                    "TELEGRAM_CHANNEL_ID=@ch",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        # ALLOWED keys need to be loadable - patch load by writing values into environ manually for migrate
        os.environ["META_PAGE_ID"] = "999"
        os.environ["META_PAGE_ACCESS_TOKEN"] = "from_env"
        os.environ["TELEGRAM_BOT_TOKEN"] = "tg"
        os.environ["TELEGRAM_CHANNEL_ID"] = "@ch"
        result = vault.migrate_env_file_to_profile(env_path, "nourbit")
        self.assertTrue(result["migrated"])
        secrets = vault.get_profile_secrets("nourbit")
        self.assertEqual(secrets["META_PAGE_ACCESS_TOKEN"], "from_env")
        self.assertEqual(secrets["TELEGRAM_BOT_TOKEN"], "tg")
        again = vault.migrate_env_file_to_profile(env_path, "nourbit")
        self.assertFalse(again["migrated"])
        for key in ["META_PAGE_ID", "META_PAGE_ACCESS_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"]:
            os.environ.pop(key, None)

    def test_unset_disconnect_keys(self):
        vault.set_profile_secrets(
            "nourbit",
            {"META_PAGE_ID": "1", "META_PAGE_ACCESS_TOKEN": "t", "NOURBIT_FACEBOOK_PAGE_TOKEN": "legacy"},
        )
        vault.unset_profile_secrets("nourbit", ["META_PAGE_ACCESS_TOKEN", "META_PAGE_ID"])
        secrets = vault.get_profile_secrets("nourbit")
        self.assertNotIn("META_PAGE_ACCESS_TOKEN", secrets)
        self.assertNotIn("META_PAGE_ID", secrets)
        self.assertNotIn("NOURBIT_FACEBOOK_PAGE_TOKEN", secrets)


if __name__ == "__main__":
    unittest.main()
