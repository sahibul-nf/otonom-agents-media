#!/usr/bin/env python3
"""
LEGACY — not supported for Otonom Media.

Native TikTok developer OAuth was removed from this project (dev app deleted).
Use manual TikTok posting or Postiz when TikTok is offered there.

This script remains only for operators who explicitly opt in with:

  ALLOW_LEGACY_TIKTOK_OAUTH=1

Never hardcode client key or secret; read from the environment.
"""

import os
import secrets
import hashlib
import base64
import urllib.parse
import urllib.request
import json
import http.server
import socketserver
import threading
import webbrowser

def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Missing {name}. Set it in the environment or .env.local. Do not commit it.")
    return value


def _legacy_allowed() -> bool:
    return os.environ.get("ALLOW_LEGACY_TIKTOK_OAUTH", "").strip().lower() in {"1", "true", "yes"}


def _load_tiktok_config() -> tuple[str, str, str, str]:
    client_key = _required_env("TIKTOK_CLIENT_KEY")
    client_secret = _required_env("TIKTOK_CLIENT_SECRET")
    redirect_uri = _required_env("TIKTOK_REDIRECT_URI")
    scopes = os.environ.get("TIKTOK_SCOPES", "user.info.basic,video.upload,video.publish")
    return client_key, client_secret, redirect_uri, scopes


def generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode("utf-8").rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def get_authorization_url(client_key: str, redirect_uri: str, scopes: str):
    """Build TikTok OAuth authorization URL with PKCE."""
    code_verifier, code_challenge = generate_pkce()
    params = {
        "client_key": client_key,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "response_type": "code",
        "state": "nourbit123",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
    return auth_url, code_verifier


def _post_form(url: str, data: dict) -> dict:
    """POST application/x-www-form-urlencoded data and return JSON response."""
    encoded = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    *,
    client_key: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for access_token, refresh_token, and open_id."""
    return _post_form(
        "https://open.tiktokapis.com/v2/oauth/token/",
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
    )


def refresh_access_token(refresh_token: str, *, client_key: str, client_secret: str) -> dict:
    """Refresh access token using refresh_token."""
    return _post_form(
        "https://open.tiktokapis.com/v2/oauth/token/",
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP server to capture OAuth callback and immediately exchange tokens."""
    auth_code = None
    tokens = None
    exchange_error = None

    def do_GET(self):
        if self.path.startswith("/callback"):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            CallbackHandler.auth_code = params.get("code", [None])[0]

            if CallbackHandler.auth_code:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authorization received! Exchanging tokens...</h1>"
                    b"<p>Check your terminal for results.</p>"
                )
                print("\nAuthorization code captured, exchanging tokens now...")
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Error: No authorization code found</h1>")
                print("\nERROR: No authorization code in callback")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress default logging
        pass


def start_callback_server(port=3000):
    """Start HTTP server to capture OAuth callback."""
    with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
        print(f"Callback server listening on http://localhost:{port}")
        httpd.serve_forever()


def main():
    if not _legacy_allowed():
        raise SystemExit(
            "Native TikTok OAuth is disabled in this repo (developer app removed).\n"
            "Clear stale TIKTOK_* keys in the dashboard vault. To run this legacy helper anyway:\n"
            "  ALLOW_LEGACY_TIKTOK_OAUTH=1 python3 scripts/tiktok_oauth_helper.py"
        )
    client_key, client_secret, redirect_uri, scopes = _load_tiktok_config()
    print("=" * 60)
    print("TikTok OAuth Helper (legacy opt-in)")
    print("=" * 60)
    print()
    print("IMPORTANT: TikTok sandbox does NOT support localhost/127.0.0.1")
    print("as redirect URI. You MUST use a public URL (e.g. ngrok).")
    print()
    print("Quick setup with ngrok:")
    print("  1. Install: brew install ngrok")
    print("  2. Run:    ngrok http 3000")
    print("  3. Copy the https://xxx.ngrok.io URL")
    print("  4. Set:    export TIKTOK_REDIRECT_URI='https://xxx.ngrok.io/callback'")
    print("  5. Add that URI in TikTok Developer Portal → Login Kit → Redirect URI")
    print()
    print("Current Redirect URI:")
    print(f"  {redirect_uri}")
    print()
    print("-" * 60)

    # Generate OAuth URL
    auth_url, code_verifier = get_authorization_url(client_key, redirect_uri, scopes)

    # Start callback server in background thread
    server_thread = threading.Thread(target=start_callback_server, daemon=True)
    server_thread.start()

    # Wait a moment for server to start
    import time
    time.sleep(1)

    print()
    print("Opening authorization URL in browser...")
    print()
    print(f"  {auth_url}")
    print()
    webbrowser.open(auth_url)

    # Wait for callback
    print("Waiting for authorization callback...")
    print("(After authorizing in TikTok, you will be redirected back)")
    print()

    for _ in range(120):  # Wait up to 2 minutes
        time.sleep(0.5)
        if CallbackHandler.auth_code:
            break

    if not CallbackHandler.auth_code:
        print("\nTIMEOUT: No authorization code received.")
        print("Please check if you were redirected to the callback URL.")
        return

    # Exchange tokens immediately while code is still fresh
    print("\nExchanging code for tokens...")
    try:
        tokens = exchange_code_for_tokens(
            CallbackHandler.auth_code,
            code_verifier,
            client_key=client_key,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        # TikTok returns tokens at root level (not under "data")
        if tokens.get("access_token"):
            print("\n" + "=" * 60)
            print("SUCCESS! Tokens obtained:\n")
            print(f"  TIKTOK_ACCESS_TOKEN : {tokens.get('access_token')}")
            print(f"  TIKTOK_REFRESH_TOKEN: {tokens.get('refresh_token')}")
            print(f"  TIKTOK_OPEN_ID      : {tokens.get('open_id')}")
            print(f"  expires_in          : {tokens.get('expires_in')} seconds")
            print("=" * 60)
            print()
            print("Add these to your .env.local file:")
            print()
            print(f"  TIKTOK_ACCESS_TOKEN={tokens.get('access_token')}")
            print(f"  TIKTOK_REFRESH_TOKEN={tokens.get('refresh_token')}")
            print(f"  TIKTOK_OPEN_ID={tokens.get('open_id')}")
            print()
        else:
            print("\nToken exchange failed. Full response:")
            print(json.dumps(tokens, indent=2))
    except Exception as e:
        print(f"\nFAILED: {e}")


if __name__ == "__main__":
    main()
