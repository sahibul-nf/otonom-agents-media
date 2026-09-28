import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from media_engine.db import connect, initialize
from media_engine.rerender import (
    _has_look_override,
    _hydrate_timed_captions,
    _hyperframes_settings,
    _prepare_timed_captions_for_render,
    _resolve_rerender_style,
    attach_active_rerender_jobs,
    create_batch_rerender_jobs,
    rerender_candidate,
)


class RerenderCaptionTests(unittest.TestCase):
    def test_hydrate_timed_captions_prefers_manual_edits(self):
        candidate = {
            "caption_corrections": {
                "edited_captions": [{"startMs": 0, "endMs": 1000, "text": "edited"}],
            }
        }
        render_metadata = {"captions": [{"startMs": 0, "endMs": 1000, "text": "rendered"}]}

        self.assertTrue(_hydrate_timed_captions(candidate, render_metadata))
        self.assertEqual(candidate["timed_captions"][0]["text"], "edited")
        self.assertEqual(candidate["caption_source"], "manual_edit")

    def test_hydrate_timed_captions_falls_back_to_render_metadata(self):
        candidate = {"caption_corrections": {}}
        render_metadata = {"captions": [{"startMs": 0, "endMs": 1000, "text": "rendered"}]}

        self.assertTrue(_hydrate_timed_captions(candidate, render_metadata))
        self.assertEqual(candidate["timed_captions"][0]["text"], "rendered")

    def test_has_look_override_detects_brand_template(self):
        self.assertFalse(_has_look_override("auto", None, None))
        self.assertTrue(_has_look_override(None, "brand:custom_demo", "brand:custom_demo"))
        self.assertTrue(_has_look_override("profiles/custom_acme.json", None, None))

    def test_has_look_override_detects_builtin_recipe(self):
        self.assertTrue(_has_look_override("auto", "energy_warm_question", None))
        self.assertFalse(_has_look_override("auto", "auto", None))

    def test_hyperframes_settings_clears_brand_on_recipe_override(self):
        settings = _hyperframes_settings(
            {
                "hyperframesTemplate": "spiritual_reflective",
                "hyperframesFormat": "short_9_16",
                "brandSystemTemplateId": "brand:custom_demo",
            },
            {},
            hyperframes_template="energy_warm_question",
            brand_system_template_id="",
        )
        self.assertEqual(settings["hyperframes_template"], "energy_warm_question")
        self.assertEqual(settings["brand_system_template_id"], "")

    def test_resolve_rerender_style_uses_recipe_override(self):
        embedded = {"template_only": True, "caption": {"preset": "karaoke"}, "brand": {"watermark_text": "Old"}}
        render_metadata = {"style": embedded, "hyperframesTemplate": "spiritual_reflective"}
        hf_settings = _hyperframes_settings(
            render_metadata,
            {},
            hyperframes_template="energy_warm_question",
            brand_system_template_id="",
        )
        with patch("media_engine.rerender.load_style_for_render") as load_style:
            load_style.return_value = {"from_recipe": True}
            resolved = _resolve_rerender_style("auto", render_metadata, hf_settings, look_override=True)
        load_style.assert_called_once()
        self.assertEqual(load_style.call_args.kwargs["hyperframes_template"], "energy_warm_question")
        self.assertEqual(resolved, {"from_recipe": True})

    def test_resolve_rerender_style_prefers_embedded_style_without_override(self):
        embedded = {"template_only": True, "caption": {"preset": "karaoke"}, "brand": {"watermark_text": "Old"}}
        render_metadata = {"style": embedded, "hyperframesTemplate": "spiritual_reflective"}
        hf_settings = _hyperframes_settings(render_metadata, {})
        resolved = _resolve_rerender_style("auto", render_metadata, hf_settings, look_override=False)
        self.assertEqual(resolved, embedded)

    def test_resolve_rerender_style_uses_brand_path_when_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles = Path(tmpdir) / "profiles"
            profiles.mkdir(parents=True)
            custom_path = profiles / "custom_review_look.json"
            custom_path.write_text(
                json.dumps(
                    {
                        "id": "custom_review_look",
                        "label": "Review Look",
                        "brand_system": {"starter_template": "spiritual_reflective", "cta_overlay": "tiktok-follow"},
                        "brand": {"watermark_text": "Review Watermark"},
                    }
                ),
                encoding="utf-8",
            )
            embedded = {"template_only": True, "brand": {"watermark_text": "Old"}}
            render_metadata = {
                "style": embedded,
                "hyperframesTemplate": "spiritual_reflective",
                "hyperframesFormat": "short_9_16",
            }
            hf_settings = {
                "hyperframes_template": "brand:custom_review_look",
                "hyperframes_format": "short_9_16",
                "brand_system_template_id": "brand:custom_review_look",
                "genres": [],
            }
            with patch("media_engine.db.ROOT", Path(tmpdir)), patch("media_engine.styles.ROOT", Path(tmpdir)):
                resolved = _resolve_rerender_style(
                    str(custom_path.relative_to(Path(tmpdir))),
                    render_metadata,
                    hf_settings,
                    look_override=True,
                )
            self.assertEqual(resolved.get("brand", {}).get("watermark_text"), "Review Watermark")

    def test_hyperframes_settings_reads_saved_template(self):
        settings = _hyperframes_settings(
            {
                "hyperframesTemplate": "spiritual_reflective",
                "hyperframesFormat": "short_9_16",
                "brandSystemTemplateId": "",
                "genres": ["kajian"],
            },
            {"curation_metadata": {"genres": ["ignored_when_contract_has_genres"]}},
        )
        self.assertEqual(settings["hyperframes_template"], "spiritual_reflective")
        self.assertEqual(settings["hyperframes_format"], "short_9_16")
        self.assertEqual(settings["genres"], ["kajian"])

    def test_prepare_timed_captions_rebases_absolute_timeline_without_regeneration(self):
        candidate = {
            "start_ms": 125_000,
            "timed_captions": [
                {
                    "text": "kajian",
                    "startMs": 130_000,
                    "endMs": 130_800,
                    "words": [{"text": "kajian", "startMs": 130_000, "endMs": 130_800}],
                }
            ],
            "asr_metadata": {},
            "cost": {},
        }
        regenerate_calls: list[str] = []

        def fake_regenerate(item, *args, **kwargs):
            regenerate_calls.append(item["id"])
            item["timed_captions"] = [{"startMs": 0, "endMs": 1000, "text": "regenerated"}]

        with patch("media_engine.rerender._regenerate_captions", side_effect=fake_regenerate), patch(
            "media_engine.rerender.probe_duration_ms",
            return_value=60_000,
        ):
            regenerated = _prepare_timed_captions_for_render(
                candidate,
                "source.mp4",
                style={"caption": {}},
                source_url="https://youtube.com/watch?v=test",
                profile={"niche": "kajian"},
                regenerate_captions=False,
            )

        self.assertFalse(regenerated)
        self.assertEqual(regenerate_calls, [])
        self.assertEqual(candidate["timed_captions"][0]["startMs"], 120)
        self.assertEqual(candidate["timed_captions"][0]["words"][0]["startMs"], 120)

    def test_rerender_reuses_render_metadata_captions_without_regeneration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "media_engine.sqlite"
            source_dir = Path(tmpdir) / "artifacts" / "nourbit" / "clip_1" / "source"
            source_dir.mkdir(parents=True)
            source_clip = source_dir / "section.mp4"
            source_clip.write_bytes(b"\x00" * 32)

            conn = connect(db_path)
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO source_manifests
                  (id, profile_id, source_url, owner_type, permission_status, allowed_use_json, publish_restrictions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("source_1", "nourbit", "https://youtube.com/watch?v=test", "third_party", "allowed", "[]", "[]"),
            )
            conn.execute(
                """
                INSERT INTO clip_candidates
                  (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason, transcript_span,
                   risk_flags_json, caption_corrections_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("clip_1", "nourbit", "source_1", 0, 60_000, "Hook", "Reason", "span", "[]", "{}", "rendered"),
            )
            contract = {
                "sourceVideoPath": str(source_clip),
                "sourceUrl": "https://youtube.com/watch?v=test",
                "cropStrategy": "center",
                "captionStyle": "caption",
                "hyperframesTemplate": "spiritual_reflective",
                "hyperframesFormat": "short_9_16",
                "genres": ["kajian"],
                "style": {"template_only": True, "caption": {"preset": "karaoke"}},
                "captions": [{"startMs": 0, "endMs": 1000, "text": "saved caption", "words": []}],
            }
            conn.execute(
                """
                INSERT INTO render_jobs
                  (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("render_1", "clip_1", "premium", "center", "caption", "rendered", str(Path(tmpdir) / "out.mp4"), json.dumps(contract)),
            )
            conn.commit()
            conn.close()

            regenerate_calls: list[str] = []

            def fake_regenerate(candidate, *args, **kwargs):
                regenerate_calls.append(candidate["id"])
                candidate["timed_captions"] = [{"startMs": 0, "endMs": 1000, "text": "regenerated"}]

            hyperframes_calls: list[dict[str, str]] = []

            def fake_hyperframes(*args, **kwargs):
                hyperframes_calls.append(
                    {
                        "template": str(kwargs.get("hyperframes_template") or ""),
                        "format": str(kwargs.get("hyperframes_format") or ""),
                    }
                )
                return (str(Path(tmpdir) / "rerender.mp4"), contract)

            with patch("media_engine.rerender._regenerate_captions", side_effect=fake_regenerate), patch(
                "media_engine.rerender.apply_silence_trim_for_render",
                side_effect=lambda source, candidate, **kwargs: str(source),
            ), patch(
                "media_engine.rerender.render_premium_hyperframes",
                side_effect=fake_hyperframes,
            ), patch(
                "media_engine.rerender.build_render_quality_report",
                return_value={"quality_score": 90},
            ):
                result = rerender_candidate("clip_1", db_path=db_path)

            self.assertEqual(regenerate_calls, [])
            self.assertEqual(hyperframes_calls, [{"template": "spiritual_reflective", "format": "short_9_16"}])
            self.assertEqual(result["candidate_id"], "clip_1")

    def test_attach_active_rerender_jobs_adds_running_job_to_review_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "media_engine.sqlite"
            conn = connect(db_path)
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO source_manifests
                  (id, profile_id, source_url, owner_type, permission_status, allowed_use_json, publish_restrictions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("source_1", "nourbit", "https://youtube.com/watch?v=test", "third_party", "allowed", "[]", "[]"),
            )
            conn.execute(
                """
                INSERT INTO clip_candidates
                  (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason, transcript_span,
                   risk_flags_json, status)
                VALUES ('clip_1', 'nourbit', 'source_1', 0, 60_000, 'Hook', 'Reason', 'span', '[]', 'rendered')
                """,
            )
            conn.execute(
                """
                INSERT INTO rerender_jobs
                  (id, candidate_id, renderer, quality, style_path, force_source_refresh, regenerate_captions,
                   status, progress, message, result_json, error)
                VALUES ('rerender_1', 'clip_1', 'hyperframes', 'production', '', 0, 0,
                        'running', 52, 'Rendering video with HyperFrames', '{}', '')
                """,
            )
            conn.commit()
            rows = [{"id": "clip_1"}]
            attach_active_rerender_jobs(conn, rows)
            conn.close()
            self.assertEqual(rows[0]["rerender_job"]["status"], "running")
            self.assertEqual(rows[0]["rerender_job"]["progress"], 52)

    def test_create_batch_rerender_jobs_queues_eligible_clips(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "media_engine.sqlite"
            source_dir = Path(tmpdir) / "artifacts" / "nourbit" / "clip_1" / "source"
            source_dir.mkdir(parents=True)
            source_clip = source_dir / "section.mp4"
            source_clip.write_bytes(b"\x00" * 32)

            conn = connect(db_path)
            initialize(conn)
            conn.execute(
                "INSERT INTO media_profiles (id, name, niche, languages_json, default_render_preset, cta_text, watermark_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("nourbit", "Nourbit", "kajian", "[]", "premium", "cta", "watermark"),
            )
            conn.execute(
                """
                INSERT INTO source_manifests
                  (id, profile_id, source_url, owner_type, permission_status, allowed_use_json, publish_restrictions_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("source_1", "nourbit", "https://youtube.com/watch?v=test", "third_party", "allowed", "[]", "[]"),
            )
            conn.execute(
                """
                INSERT INTO clip_candidates
                  (id, profile_id, source_id, start_ms, end_ms, title_hook, viral_reason, transcript_span,
                   risk_flags_json, caption_corrections_json, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("clip_1", "nourbit", "source_1", 0, 60_000, "Hook", "Reason", "span", "[]", "{}", "rendered"),
            )
            contract = {
                "sourceVideoPath": str(source_clip),
                "sourceUrl": "https://youtube.com/watch?v=test",
                "cropStrategy": "center",
                "captionStyle": "caption",
                "captions": [{"startMs": 0, "endMs": 1000, "text": "saved caption", "words": []}],
            }
            conn.execute(
                """
                INSERT INTO render_jobs
                  (id, candidate_id, preset, crop_strategy, caption_style, status, output_path, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("render_1", "clip_1", "premium", "center", "caption", "rendered", str(Path(tmpdir) / "out.mp4"), json.dumps(contract)),
            )
            conn.commit()
            conn.close()

            with patch("media_engine.rerender._run_rerender_job"):
                result = create_batch_rerender_jobs(["clip_1", "missing"], db_path=db_path)

            self.assertEqual(len(result["queued"]), 1)
            self.assertEqual(result["queued"][0]["candidate_id"], "clip_1")
            self.assertEqual(result["skipped"][0]["id"], "missing")


if __name__ == "__main__":
    unittest.main()
