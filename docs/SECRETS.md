# Secrets And API Keys

This repository must never store live API keys, page tokens, OAuth refresh tokens, or app secrets in git.

If a secret was ever committed, deleting it from the latest commit is not enough. It remains in git history. Rotate that credential at the provider, then treat the old value as public. Do not rewrite history unless you intend a force-push and every clone is updated.

## Local Development

1. Copy `.env.example` to `.env.local`.
2. Put real values only in `.env.local` or another ignored env file.
3. Keep provider-specific secrets out of JSON config files unless the file is explicitly ignored.

## Existing Sensitive Files

These files are intentionally ignored and should remain local only:

- `.env`, `.env.local`, and `**/.env` (examples named `.env.example` are the only env files that belong in git)
- `techtalk-autonomous/config/fb_pages.json`
- `media-engine/data/` and `**/*.sqlite`
- `media-engine/artifacts/` and `media-engine/artifacts-dev/`
- cookies, service-account JSON, and `client_secret*.json`

## TikTok (native OAuth)

Otonom does **not** support native TikTok developer OAuth or direct Content Posting API in this repo (the prior dev app was removed). Do not add new `TIKTOK_CLIENT_*` apps for this project.

- Remove stale `TIKTOK_*` values from `.env.local` and the workspace vault (Publish → TikTok → **Clear stale credentials** when shown).
- If TikTok publishing returns, use **Postiz** channel mapping only — not `scripts/tiktok_oauth_helper.py`.

## Recommended Secret Layout

- Root `.env.local`: shared provider credentials for local testing.
- Optional LLM curation keys: `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, and `GROQ_API_KEY`.
- Local media-engine secrets live in ignored `.env.local`. It is okay to copy provider keys from another local project into this file, but never commit it or print key values in logs.
- Platform account tokens: store in ignored env files or an external secret manager.
- SaaS future: use OAuth connect-account flow, encrypted-at-rest token storage, token rotation, and audit logs.

## Before Commit

Run:

```bash
python3 scripts/secret_scan.py
git status --ignored --short
```

The pre-commit hook runs the same scanner automatically.
