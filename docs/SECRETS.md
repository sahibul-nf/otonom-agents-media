# Secrets And API Keys

This repository must never store live API keys, page tokens, OAuth refresh tokens, or app secrets in git.

## Local Development

1. Copy `.env.example` to `.env.local`.
2. Put real values only in `.env.local` or another ignored env file.
3. Keep provider-specific secrets out of JSON config files unless the file is explicitly ignored.

## Existing Sensitive Files

These files are intentionally ignored and should remain local only:

- `techtalk-autonomous/.env`
- `techtalk-autonomous/config/fb_pages.json`
- `media-engine/data/*.sqlite`
- `media-engine/artifacts/**`

## Recommended Secret Layout

- Root `.env.local`: shared provider credentials for local testing.
- Optional LLM curation keys: `OPENAI_API_KEY` and `DEEPSEEK_API_KEY`.
- Platform account tokens: store in ignored env files or an external secret manager.
- SaaS future: use OAuth connect-account flow, encrypted-at-rest token storage, token rotation, and audit logs.

## Before Commit

Run:

```bash
python3 scripts/secret_scan.py
git status --ignored --short
```

The pre-commit hook runs the same scanner automatically.
