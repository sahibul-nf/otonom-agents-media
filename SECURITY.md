# Security

Otonom Agents Media is a local-first media pipeline. Live API keys, OAuth tokens, cookies, and database files stay on your machine.

## Supported versions

Security fixes land on `dev`, then `main`. There is no separate LTS branch yet.

## Reporting a vulnerability

Do not open a public GitHub issue for a leaked credential, auth bypass, or anything that includes a secret.

Email the maintainer through the address on the GitHub profile for `sahibul-nf`, or open a private GitHub security advisory on this repository. Include:

- what is affected
- how to reproduce it without pasting live tokens
- the impact you observed

## What must never be committed

- `.env`, `.env.local`, and any file that is not `*.env.example`
- OAuth client secrets, refresh tokens, bot tokens, cookies, and service-account JSON
- `media-engine/data/`, `artifacts/`, `artifacts-dev/`, and SQLite databases
- Hardcoded keys inside scripts

Copy [`.env.example`](.env.example) and read [`docs/SECRETS.md`](docs/SECRETS.md). Before you commit:

```bash
python3 scripts/secret_scan.py
```

The pre-commit hook runs the same scanner when `core.hooksPath` is `.githooks`.
