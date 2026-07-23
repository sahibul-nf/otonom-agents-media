# Explainer Mode (Phase 0 + thin MCP)

Agent-driven hybrid long-form: **avatar fixtures** (from HeyGen MCP / web) + **HyperFrames/FFmpeg** text-broll + stitch → **dashboard review**.

No HeyGen Direct API required for this phase.

Canonical architecture: [`explainer-saas-architecture.md`](./explainer-saas-architecture.md)  
Issues: [#5](https://github.com/sahibul-nf/otonom-agents-media/issues/5), [#6](https://github.com/sahibul-nf/otonom-agents-media/issues/6)

---

## Operator flow (Cursor agent → dashboard)

1. Generate short avatar clips with **HeyGen MCP** (Creator plan credits).
2. Create an Explainer job (CLI or Otonom MCP `create_explainer`).
3. Import each clip into the job fixtures (`import_avatar_clip` or copy files).
4. Run stitch (`explainer-run` / `run_explainer`).
5. Open the dashboard **Review** tab → preview → approve / schedule.

Approve and publish stay **dashboard-first** (no silent auto-publish from MCP).

---

## CLI

From `media-engine/` (or `PYTHONPATH=media-engine`):

```bash
# 1) Plan only
python3 -m media_engine.cli explainer-plan --topic "Apa itu Bitcoin?"

# 2) Create job + empty fixtures folder
python3 -m media_engine.cli explainer-create --topic "Apa itu Bitcoin?"
# → prints job_id, fixtures_dir

# 3) Drop avatar MP4s into fixtures_dir using names from scenes.json
#    e.g. scene_01.mp4, scene_04.mp4, scene_06.mp4

# 4) Stitch + register review candidate
python3 -m media_engine.cli explainer-run --job-id JOB_ID --ffmpeg-only
```

One-shot with an existing scenes file + clips directory:

```bash
python3 -m media_engine.cli explainer-run \
  --scenes /path/to/scenes.json \
  --clips-dir /path/to/fixtures \
  --topic "Apa itu Bitcoin?" \
  --ffmpeg-only
```

`--ffmpeg-only` uses FFmpeg title cards for text/broll (reliable). Omit it to prefer HyperFrames when `HYPERFRAMES_ENABLED=true` and runtime is ready.

---

## Fixture naming

For each `avatar` scene in `scenes.json`:

| Preference | Example |
|------------|---------|
| `clip_file` field | `scene_01.mp4` |
| Fallback | `{scene.id}.mp4` |

Download HeyGen outputs from the web app / MCP `video_url`, then copy into `fixtures_dir`.

---

## Otonom MCP (Cursor)

Example Cursor MCP config entry:

```json
{
  "mcpServers": {
    "otonom-media": {
      "command": "python3",
      "args": ["-m", "media_engine.otonom_mcp"],
      "cwd": "/ABS/PATH/otonom-agents-media/media-engine",
      "env": {
        "PYTHONPATH": "/ABS/PATH/otonom-agents-media/media-engine"
      }
    }
  }
}
```

Checked-in example: [`docs/otonom-mcp.cursor.example.json`](./otonom-mcp.cursor.example.json)

### Tools

| Tool | Purpose |
|------|---------|
| `create_explainer` | Plan + job folder |
| `import_avatar_clip` | Local path or HTTPS URL → fixtures |
| `run_explainer` | Stitch + review queue |
| `get_explainer_status` | Job status / paths |
| `list_explainer_jobs` | Recent jobs |
| `list_review_queue` | Dashboard review items |

### Suggested agent prompt

```text
1. Use HeyGen MCP to generate short avatar clips for each avatar scene script.
2. create_explainer with topic.
3. import_avatar_clip for each clip into fixtures (scene_01.mp4, …).
4. run_explainer with ffmpeg_only true.
5. Tell me to open the dashboard Review tab.
```

---

## Brand constants (TechTalk)

- Avatar look: `0f4dca86e0bd42d8a8afdae9948338ce`
- Voice: `LXpG1p9h8viifHEGQiFJ`
- Direct API (later #7): engine `avatar_iii`

---

## Artifacts layout

```text
media-engine/artifacts/{profile}/explainers/{job_id}/
  scenes.json
  status.json
  fixtures/
  segments/
  final.mp4
  manifest.json
```

Review candidate id: `cand_{job_id}` with `status=rendered`.
