<!-- solo-dev-ai-kit:managed -->
# How to run this app (fill in once)

AI agents read this file before UI verification. **Replace every `TBD` with real values.** Delete sections that do not apply.

**App stack:** `web` (`web` · `mobile` · `both`)

## Tests (all stacks)

| Item | Value |
|------|--------|
| **Test command** | `pip install -r media-engine/requirements-dev.txt` then `cd media-engine && PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py'` |
| **Focused test example** | `TBD — e.g. npm test -- src/auth.test.ts OR flutter test test/widgets/header_test.dart` |

## Web app (delete this section if not a web app)

| Item | Value |
|------|--------|
| **Start command** | `TBD — e.g. npm run dev` |
| **Local URL** | `TBD — e.g. http://localhost:3000` |
| **Health check** | `TBD — e.g. curl -s -o /dev/null -w "%{http_code}" http://localhost:3000` |

**UI verify (web):** Cursor IDE browser (default) → Playwright only if already installed. Kit does not auto-install.

## Mobile app (delete this section if not a mobile app)

| Item | Value |
|------|--------|
| **Start command** | `TBD — e.g. flutter run` |
| **Emulator / simulator** | `TBD — e.g. flutter emulators --launch Pixel_7` |
| **Integration test** | `TBD — e.g. flutter test integration_test/login_test.dart` |
| **Widget / golden test** | `TBD — e.g. flutter test test/widgets/` |

**UI verify (mobile):** `flutter test` first → [MobAI](https://mobai.run) optional (`npx mobai-mcp` + MobAI desktop). Kit does not install MobAI.

## Test accounts (if login required)

| Role | Email / user | Password / notes |
|------|----------------|------------------|
| Demo user | `TBD` | `TBD — use test creds only; never commit secrets` |

## Notes

- Staging URL (optional): `TBD`
- Env: copy `.env.example` → `.env` (never commit secrets)
- Known quirks: `TBD — e.g. run migrations before dev server`
