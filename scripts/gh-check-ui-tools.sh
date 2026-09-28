#!/usr/bin/env bash
# solo-dev-ai-kit:managed
# Report UI verification tool availability (check only — never installs).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=_load-config.sh
source "$(dirname "$0")/_load-config.sh"
_load_config "$ROOT"

APP_STACK="${APP_STACK:-web}"

echo "UI verification tools (check only — kit does not install tools):"
echo "  App stack: $APP_STACK (web | mobile | both)"
echo ""

if [[ "$APP_STACK" == "web" || "$APP_STACK" == "both" ]]; then
  echo "Web UI:"
  if [[ -n "${CURSOR_AGENT:-}" || -n "${CURSOR_TRACE_ID:-}" ]]; then
    echo "  Cursor IDE browser: available (native MCP in Cursor)"
  else
    echo "  Cursor IDE browser: use when working in Cursor (native MCP)"
  fi

  if command -v npx >/dev/null 2>&1; then
    if npx --yes @playwright/cli@latest --version >/dev/null 2>&1; then
      echo "  Playwright CLI: yes (optional web fallback)"
    else
      echo "  Playwright CLI: not detected (optional — install manually if needed)"
    fi
  else
    echo "  Playwright CLI: npx unavailable"
  fi
  echo ""
fi

if [[ "$APP_STACK" == "mobile" || "$APP_STACK" == "both" ]]; then
  echo "Mobile UI:"
  if command -v flutter >/dev/null 2>&1; then
    echo "  Flutter: yes ($(flutter --version 2>/dev/null | head -n1 || echo detected))"
  else
    echo "  Flutter: not detected"
  fi

  mobai_found=false
  if command -v mobai >/dev/null 2>&1; then
    echo "  MobAI CLI: yes"
    mobai_found=true
  fi
  if [[ -d "/Applications/MobAI.app" ]] || [[ -d "$HOME/Applications/MobAI.app" ]]; then
    echo "  MobAI desktop: installed"
    mobai_found=true
  fi
  if ! $mobai_found; then
    echo "  MobAI: not detected (optional — https://mobai.run ; MCP: npx mobai-mcp)"
  fi

  if command -v npx >/dev/null 2>&1; then
    echo "  mobai-mcp: run 'npx mobai-mcp' when MobAI desktop is open (not auto-started)"
  fi
  echo ""
fi

if [[ -f "docs/how-to-run.md" ]]; then
  echo "docs/how-to-run.md: present"
  if [[ "$APP_STACK" == "web" || "$APP_STACK" == "both" ]]; then
    if grep -qE 'https?://[^[:space:]]+' docs/how-to-run.md 2>/dev/null \
      && ! grep -q 'TBD — e.g. http' docs/how-to-run.md 2>/dev/null; then
      echo "  Web URL: filled in"
    else
      echo "  Web URL: replace TBD in docs/how-to-run.md"
    fi
  fi
  if [[ "$APP_STACK" == "mobile" || "$APP_STACK" == "both" ]]; then
    if grep -qE 'flutter run|emulator|simulator' docs/how-to-run.md 2>/dev/null \
      && ! grep -q 'TBD — e.g. flutter run' docs/how-to-run.md 2>/dev/null; then
      echo "  Mobile run: filled in"
    else
      echo "  Mobile run: replace TBD in docs/how-to-run.md"
    fi
  fi
else
  echo "docs/how-to-run.md: missing — bootstrap will create template"
fi

echo ""
echo "Verify scope: acceptance criteria only (not full app) unless user requests E2E."
echo "Verify max rounds (default): ${VERIFY_MAX_ROUNDS:-3} — override per task in chat or edit .workflow-kit.env"
echo "Prefer automated tests over screenshots. Kit never auto-installs MobAI or Playwright."
