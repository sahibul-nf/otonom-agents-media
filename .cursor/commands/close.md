<!-- solo-dev-ai-kit:managed -->
Phase 3 — close-out after human QA for issue `#N` (user must confirm *works* / *ok* / *sudah work*).

Human should have reviewed the PR from **Human Review** (or **AI Review** for agent verify) before close-out.

1. Verify AC against code/commits (read-only).
2. Write closing comment from `docs/close-comment.example.md` → save e.g. `/tmp/close-N.md`.
3. Run:

```bash
./scripts/gh-close-verified-issue.sh N --comment-file /tmp/close-N.md
```

This checks AC boxes, posts comment, closes issue, and sets board **Done**.

Use `--no-close` only if user explicitly wants comment-only. See `scripts/README.md` for flags.
