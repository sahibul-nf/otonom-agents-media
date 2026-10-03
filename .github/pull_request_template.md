## Summary

<!-- What this PR does and why. One issue: Fixes #N -->

Fixes #

## Base branch (required)

- [ ] This PR targets **`dev`**, not `main`
- [ ] Branch was created from **`dev`** (`feat/#N-slug` or `fix/#N-slug`)
- [ ] I did **not** push to `main` or restart PM2 / the ops checkout

## Tests (required before merge to `dev`)

```bash
cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'
```

- [ ] Full suite ran (paste counts: ran / failed / errors)
- [ ] New or extended tests cover this issue’s acceptance criteria if none existed
- [ ] Full suite **exit 0** — otherwise **do not merge**

## How to test (UI) — for Sahibul

<!-- 3–8 bullets: URL, clicks, expected result. Dashboard :3100 is production; use isolated :3101 if this is only on `dev`. -->

## Deploy safety

- [ ] No production ports stolen (`8765` / `3100`)
- [ ] No live `data/` or `artifacts/` from the ops clone

**Agent:** merge into **`dev`** only if the full suite is green. Never merge **`main`**. Human still does the UI check, then *sudah work #N*.
