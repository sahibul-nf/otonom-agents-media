"""Topic engine (#23): niche ranking + generate-next without network."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from media_engine.db import connect, initialize
from media_engine.topic_engine import (
    TopicEngineError,
    generate_next_topic,
    niche_keywords,
    propose_topics,
    score_signal,
    SignalItem,
)


def _fake_hn(_url: str, _timeout: float = 12.0):
    return {
        "hits": [
            {
                "title": "OpenAI launches fintech API for banks",
                "url": "https://example.com/openai-fintech",
                "points": 220,
                "objectID": "1",
            },
            {
                "title": "Cute cat photos of the week",
                "url": "https://example.com/cats",
                "points": 900,
                "objectID": "2",
            },
            {
                "title": "LLM agents automate SaaS onboarding",
                "url": "https://example.com/llm-saas",
                "points": 140,
                "objectID": "3",
            },
        ]
    }


class TopicEngineUnitTests(unittest.TestCase):
    def test_niche_keywords_merges_profile_tokens(self):
        keys = niche_keywords("TechTalk Crypto AI")
        self.assertIn("crypto", keys)
        self.assertIn("techtalk", keys)
        self.assertIn("ai", keys)

    def test_score_prefers_niche_over_viral_offtopic(self):
        keys = niche_keywords("tech finance ai")
        niche = SignalItem("hacker_news", "OpenAI fintech for banks", "https://a", 100)
        viral = SignalItem("hacker_news", "Cute cat photos of the week", "https://b", 900)
        self.assertGreater(score_signal(niche, keys), score_signal(viral, keys))

    def test_propose_topics_ranks_and_cites(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            conn = connect(db)
            initialize(conn)
            conn.execute(
                "UPDATE media_profiles SET niche = ? WHERE id = ?",
                ("tech finance ai fintech", "nourbit"),
            )
            conn.commit()
            conn.close()

            def fetch(url: str, timeout: float = 12.0):
                if "github.com" in url:
                    return {"items": []}
                return _fake_hn(url, timeout)

            result = propose_topics(profile_id="nourbit", limit=3, db_path=db, fetch=fetch)
            self.assertTrue(result["ok"])
            candidates = result["candidates"]
            self.assertGreaterEqual(len(candidates), 1)
            top = candidates[0]
            self.assertIn("fintech", top["title"].lower() + top["angle"].lower() + json.dumps(top["sources"]).lower())
            self.assertTrue(top["sources"][0]["url"])
            self.assertGreater(top["confidence"], 0)
            self.assertIn("SOURCES:", top["storyboard"])

    def test_empty_feed_fails_clearly(self):
        def empty_fetch(url: str, timeout: float = 12.0):
            if "github.com" in url:
                return {"items": []}
            return {"hits": []}

        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            conn = connect(db)
            initialize(conn)
            conn.close()
            with self.assertRaises(TopicEngineError) as ctx:
                propose_topics(db_path=db, fetch=empty_fetch)
            self.assertIn("empty", str(ctx.exception).lower())

    def test_generate_next_attaches_proposal_and_starts_path_a(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            conn = connect(db)
            initialize(conn)
            conn.execute(
                "UPDATE media_profiles SET niche = ? WHERE id = ?",
                ("ai fintech saas", "nourbit"),
            )
            conn.commit()
            conn.close()

            def fetch(url: str, timeout: float = 12.0):
                if "github.com" in url:
                    return {"items": []}
                return _fake_hn(url, timeout)

            fake_job = {
                "job_id": "patha_test",
                "status": "starting",
                "topic": "OpenAI launches fintech API for banks",
                "topic_proposal": {"candidate_id": "topic_1"},
            }
            with mock.patch(
                "media_engine.path_a_jobs.start_path_a_generate",
                return_value=fake_job,
            ) as start:
                result = generate_next_topic(
                    profile_id="nourbit",
                    db_path=db,
                    fetch=fetch,
                    start_path_a=True,
                )
            self.assertTrue(result["review_required"])
            self.assertEqual(result["path_a"]["job_id"], "patha_test")
            self.assertTrue(result["topic_proposal"]["sources"])
            start.assert_called_once()
            kwargs = start.call_args.kwargs
            self.assertTrue(kwargs["topic"])
            self.assertIn("sources", kwargs["topic_proposal"])

    def test_generate_next_without_path_a(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.sqlite"
            conn = connect(db)
            initialize(conn)
            conn.close()

            def fetch(url: str, timeout: float = 12.0):
                if "github.com" in url:
                    return {"items": []}
                return _fake_hn(url, timeout)

            result = generate_next_topic(db_path=db, fetch=fetch, start_path_a=False)
            self.assertIsNone(result["path_a"])
            self.assertTrue(result["candidate"]["title"])


if __name__ == "__main__":
    unittest.main()
