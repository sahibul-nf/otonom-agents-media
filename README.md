# Otonom Agents Media

Workspace for autonomous media systems across multiple niches.

## Projects

- `media-engine/` — shared local-first multimedia engine, currently focused on Nourbit video clipping, review, render contracts, and multi-platform dry-run publishing.
- `techtalk-autonomous/` — existing standalone TechTalk Intel automation.

## Security First

Live credentials are local-only. Start from:

- `.env.example`
- `techtalk-autonomous/config/fb_pages.example.json`
- `docs/SECRETS.md`

Before committing:

```bash
python3 scripts/secret_scan.py
git status --ignored --short
```

Git hooks are configured with:

```bash
git config core.hooksPath .githooks
```

## Tests

```bash
PYTHONPATH=media-engine python3 -m unittest discover -s media-engine/tests -v
```
