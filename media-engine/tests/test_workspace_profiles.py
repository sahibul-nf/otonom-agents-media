"""Workspace profile CRUD tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine import credential_vault as vault
from media_engine.db import connect, initialize, seed_profile
from media_engine.workspace_profiles import (
    WorkspaceProfileError,
    create_profile,
    delete_profile,
    list_profiles,
    slugify_profile_id,
    update_profile,
)


class WorkspaceProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.sqlite"
        self.vault_dir = Path(self.tmp.name) / "credentials"
        self.vault_dir.mkdir(parents=True)
        self.conn = connect(self.db_path)
        initialize(self.conn)
        self._patchers = [patch.object(vault, "VAULT_DIR", self.vault_dir)]
        for item in self._patchers:
            item.start()
        seed_profile(
            self.conn,
            {
                "id": "nourbit",
                "name": "Nourbit",
                "niche": "Islamic",
                "languages": ["id"],
                "default_render_preset": "lecture_clean",
                "cta_text": "",
                "watermark_text": "",
                "publish_targets": [],
            },
        )
        seed_profile(
            self.conn,
            {
                "id": "workspace",
                "name": "Workspace",
                "niche": "General",
                "languages": ["id", "en"],
                "default_render_preset": "short_clean",
                "cta_text": "",
                "watermark_text": "",
                "publish_targets": [],
            },
        )

    def tearDown(self) -> None:
        for item in self._patchers:
            item.stop()
        self.conn.close()
        self.tmp.cleanup()

    def test_slugify(self):
        self.assertEqual(slugify_profile_id("Acme Clips!"), "acme_clips")

    def test_create_update_delete(self):
        created = create_profile(
            self.conn,
            {"name": "Acme Clips", "niche": "SaaS tips", "cta_text": "Follow", "watermark_text": "Acme"},
        )
        self.assertEqual(created["id"], "acme_clips")
        self.assertFalse(created["protected"])
        self.assertTrue((self.vault_dir / "acme_clips.json").exists())

        updated = update_profile(self.conn, {"id": "acme_clips", "name": "Acme Pro", "niche": "Growth"})
        self.assertEqual(updated["name"], "Acme Pro")
        self.assertEqual(updated["niche"], "Growth")

        ids = {row["id"] for row in list_profiles(self.conn)}
        self.assertIn("acme_clips", ids)

        deleted = delete_profile(self.conn, {"id": "acme_clips", "confirm": "acme_clips"})
        self.assertTrue(deleted["deleted"])
        self.assertFalse((self.vault_dir / "acme_clips.json").exists())
        ids = {row["id"] for row in list_profiles(self.conn)}
        self.assertNotIn("acme_clips", ids)

    def test_protect_builtin_delete(self):
        with self.assertRaises(WorkspaceProfileError):
            delete_profile(self.conn, {"id": "nourbit", "confirm": "nourbit", "force": True})

    def test_delete_requires_force_when_clips_exist(self):
        create_profile(self.conn, {"id": "client_a", "name": "Client A"})
        self.conn.execute(
            """
            INSERT INTO source_manifests
              (id, profile_id, source_url, owner_type, permission_status,
               permission_evidence, allowed_use_json, monetization_allowed,
               attribution_rule, publish_restrictions_json)
            VALUES ('src_a', 'client_a', 'https://youtu.be/x', 'user_submitted', 'user_attested',
                    '', '[]', 0, '', '[]')
            """
        )
        self.conn.execute(
            """
            INSERT INTO clip_candidates
              (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason,
               transcript_span, risk_flags_json, status)
            VALUES ('clip_a', 'client_a', 'src_a', 0, 1000, 'Hook', 'Reason', 'span', '[]', 'pending_review')
            """
        )
        self.conn.commit()
        with self.assertRaises(WorkspaceProfileError):
            delete_profile(self.conn, {"id": "client_a", "confirm": "client_a"})
        deleted = delete_profile(self.conn, {"id": "client_a", "confirm": "client_a", "force": True})
        self.assertTrue(deleted["deleted"])
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM clip_candidates WHERE profile_id = ?", ("client_a",)).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
