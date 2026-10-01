# SaaS readiness checklist (local-first → multi-user)

**Status:** Planning seam — no cloud auth or Postgres in this repo yet.  
**Related:** [#38](https://github.com/sahibul-nf/otonom-agents-media/issues/38), [#34](https://github.com/sahibul-nf/otonom-agents-media/issues/34) (credential vault), [#36](https://github.com/sahibul-nf/otonom-agents-media/issues/36) (workspace CRUD), `docs/explainer-saas-architecture.md` (product shape).

Use this checklist while shipping features on **SQLite + local artifacts**. Each section states what must stay true today and what to swap when deploying multi-user SaaS.

---

## Tenancy model (target)

| Layer | Today | Target SaaS |
|-------|--------|-------------|
| **User** | Single operator on one machine | `owner_user_id` (or org id) from auth provider |
| **Workspace** | `media_profiles.id` (“workspace”) | Many workspaces per user/org; same `profile_id` column semantics |
| **Data** | All rows keyed by `profile_id` | Row-level scope: every query filters `profile_id` ∈ caller’s workspaces |
| **Auth** | None (trusted local dashboard) | Middleware: session/JWT → `owner_user_id` → allowed `profile_id` list |

**Rule:** Add features behind **workspace scope** (`profile_id`), not global singletons. Auth is a **middleware seam** (inject tenant context), not a rewrite of clip/review/schedule logic.

---

## Database

| Item | Current boundary | Migration notes |
|------|------------------|-----------------|
| Engine | SQLite (`MEDIA_ENGINE_DB` or `data/media_engine.sqlite`) | Postgres (or managed SQL) with same schema + migrations |
| Keys | `profile_id` on sources, clips, schedules, jobs, targets | Keep column names; add `owner_user_id` on `media_profiles` or join table `user_workspaces` |
| Migrations | `db.py` `SCHEMA` + incremental ALTERs | Port to Alembic/Flyway; no dual-write until cutover plan exists |
| Connections | Single-writer local process | Pool per API worker; avoid SQLite-on-NFS for multi-instance |

**While building:** New tables and APIs must include `profile_id` (or derive it from the authenticated workspace). Do not add cross-workspace queries without an explicit admin role.

---

## Credentials & secrets

| Item | Current boundary | Migration notes |
|------|------------------|-----------------|
| Account tokens | Per-workspace JSON vault (`data/credentials/{profile_id}.json`) via `credential_vault.py` | Encrypted secret store (KMS, Vault, or provider-native secrets) keyed by `profile_id` |
| OAuth app ids | Global `.env` / `ALLOWED_ENV_KEYS` (client id/secret) | Stay app-level env; never copy refresh tokens back into `.env` |
| Postiz / platform | `POSTIZ_*` and platform tokens in vault when connected per workspace | Same split: app config global, account tokens per workspace |
| Context | `use_profile_credentials(profile_id)` for publish paths | Request-scoped credential resolver from auth + workspace |

**While building:** Do **not** re-globalize per-account secrets into root `.env` for convenience. New integrations follow vault + `profile_id` (see #34).

---

## Artifacts & media files

| Item | Current boundary | Migration notes |
|------|------------------|-----------------|
| Renders / previews | `artifacts/` (override `MEDIA_ENGINE_ARTIFACTS`) | Object storage (S3/R2/Blob) with keys like `{profile_id}/{candidate_id}/…` |
| Paths in DB | Relative or absolute paths in job rows | Store object keys + signed URL generation at read time |
| Local disk | Mac Mini / ops clone | Workers read/write object storage; dashboard streams via CDN or signed URLs |

**While building:** Prefer stable logical ids (`candidate_id`, `job_id`) in APIs; treat filesystem paths as implementation details.

---

## API & dashboard

| Item | Current boundary | Migration notes |
|------|------------------|-----------------|
| Scoping | `review_server.py` routes take `profile_id` query/body (default workspace when omitted) | Require workspace from session; reject cross-tenant `profile_id` |
| Dashboard | Active workspace in client state (`MediaStudioApp`) | Workspace list filtered by `owner_user_id` |
| Profiles | `media_profiles` + `profiles/*.json` style packs | DB-backed config; JSON packs become seeds/templates only |

**While building:** When adding endpoints, mirror existing pattern: load row → verify `profile_id` matches request workspace → mutate.

---

## Workers & deploy shape

Today (local / Mini):

- **Review API** — `review_server.py` (default port **8765**)
- **Dashboard** — Next.js (`DASHBOARD_PORT`, default **3100**)
- **Publisher / schedule** — PM2 apps in `scripts/media-engine-pm2.config.cjs`
- **Clip / generate / watch** — subprocess or separate PM2 workers (`run_watch_poll_worker.sh`, etc.)

Target SaaS separation (incremental, not big-bang):

```text
                    ┌─────────────────┐
  Browser ─────────►│ Dashboard (CDN) │
                    └────────┬────────┘
                             │ HTTPS + auth
                    ┌────────▼────────┐
                    │ Review / API    │  stateless, scales horizontally
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    Postgres            Object store      Queue (optional)
           │                 │                 │
           └────────┬────────┴────────┬────────┘
                    ▼                 ▼
            Clip worker        Publish worker
            (FFmpeg/HF)        (Postiz/native)
```

**While building:** Keep clip generation and publish side effects out of the HTTP request thread where possible (already true for long jobs). New background work should accept `profile_id` in the job payload.

---

## Explicit out of scope (until a dedicated issue)

- Provisioning Supabase / Firebase / Appwrite / Neon
- Login UI, SSO, or billing
- Postgres migration, dual-write, or production data move
- Multi-region deploy

---

## Pre-ship verification (manual)

Before calling the app “SaaS-ready,” confirm:

- [ ] Every new API mutation checks workspace ownership (or documents why admin-only).
- [ ] No new secrets in committed `.env` examples beyond OAuth **app** credentials.
- [ ] Artifacts and DB paths remain overridable via env for staging.
- [ ] `docs/explainer-saas-architecture.md` still matches orchestration choices (HeyGen Path A, HyperFrames local render).

---

## Priority order (product)

North star remains **clip → review → schedule → publish** reliability on the current stack. Tenancy and cloud storage are **enablers** for a later hosted SKU, not blockers for the weekly operator loop on the Mac Mini.
