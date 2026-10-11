<!-- solo-dev-ai-kit:managed -->
# How to run this app

AI agents read this file before UI verification.

**App stack:** `web`

## Tests

| Item | Value |
|------|--------|
| **Test command** | `pip install -r media-engine/requirements-dev.txt` then `cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'` |
| **Focused test example** | `cd media-engine && PYTHONPATH=. python3 -m unittest tests.test_credential_vault` |

## Web app

| Item | Value |
|------|--------|
| **Start command** | From the repo root: `npm install && cd apps/dashboard && npm install && cd ../.. && npm run dev` |
| **Local URL** | `http://127.0.0.1:3100` |
| **Health check** | `npm run health` (API defaults to `http://127.0.0.1:8765`) |

Copy `.env.example` to `.env.local` before the first start. The dashboard proxies engine calls with `MEDIA_ENGINE_API_BASE` (default `http://127.0.0.1:8765`).

**Python (media-engine):** create a venv and install once:

```bash
python3 -m venv media-engine/.venv
source media-engine/.venv/bin/activate
pip install -r media-engine/requirements-dev.txt
```

`npm run dev` still works if system `python3` already has deps; the venv is recommended for a clean clone.

**UI verify (web):** Cursor IDE browser. Playwright only if it is already installed.

## Notes

- Docs map: [`docs/README.md`](README.md).
- **Mac Mini ops (PM2 + Postiz):** see [`docs/local-ops.md`](local-ops.md) — ops on `:8765`/`:3100` (`next start`); coding uses `npm run dev:isolated` → `:8766`/`:3101` + own `MEDIA_ENGINE_DB`.
- Isolated worktree (do not steal PM2 ports `8765` / `3100`): `npm run dev:isolated` → API `:8766`, dashboard `:3101`.
- Env: copy `.env.example` → `.env.local`. Never commit secrets. See `docs/SECRETS.md`. Postiz API key + channel map live in the **workspace vault** (Publish → Connect), not `.env`.
- Login: the local dashboard has no hosted demo account. Platform publish needs your own OAuth tokens in `.env.local` (YouTube, Meta, Telegram) **or** Postiz mapping. **TikTok:** native OAuth is not supported — see `docs/SECRETS.md`.
- Engine CLI details: `media-engine/README.md`.
- Brand presets: `brand-pack/` (`techtalk`, `personal`, `blank`) or `CONTENT_OS_PATH`.
- Content packages API: `GET /api/content-packages`, `POST /api/content-package-create`, `POST /api/content-package-approve`.

