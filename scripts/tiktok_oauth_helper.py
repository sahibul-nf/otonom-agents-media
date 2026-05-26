#!/usr/bin/env python3
"""
TikTok OAuth Helper for Nourbit Sandbox
Usage:
  1. Add redirect URI to TikTok app: http://localhost:3000/callback
  2. Run this script
  3. Open the authorization URL in browser and authorize
  4. Script will automatically capture the callback and exchange tokens
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

# Sandbox credentials
CLIENT_KEY = "sbawp3fupcpjhvsflv"
CLIENT_SECRET = "pCrw2bzBVHP2yNwMWx3QnNyrwAHkNLQC"

# Use ngrok URL (e.g. https://abc123.ngrok.io/callback) or any valid public URL.
# TikTok sandbox does NOT support localhost/127.0.0.1 as redirect URI.
REDIRECT_URI = os.environ.get(
    "TIKTOK_REDIRECT_URI",
    "https://9243-2401-e320-bcc-cc08-ace6-9f66-84c3-e5cf.ngrok-free.app/callback"
)
SCOPES = "user.info.basic,video.upload,video.publish"


def generate_pkce():
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(32)
    ).decode("utf-8").rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode("utf-8").rstrip("=")
    return code_verifier, code_challenge


def get_authorization_url():
    """Build TikTok OAuth authorization URL with PKCE."""
    code_verifier, code_challenge = generate_pkce()
    params = {
        "client_key": CLIENT_KEY,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
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


def exchange_code_for_tokens(code: str, code_verifier: str) -> dict:
    """Exchange authorization code for access_token, refresh_token, and open_id."""
    return _post_form(
        "https://open.tiktokapis.com/v2/oauth/token/",
        {
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )


def refresh_access_token(refresh_token: str) -> dict:
    """Refresh access token using refresh_token."""
    return _post_form(
        "https://open.tiktokapis.com/v2/oauth/token/",
        {
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
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
    print("=" * 60)
    print("TikTok OAuth Helper for Nourbit Sandbox")
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
    print(f"  {REDIRECT_URI}")
    print()
    print("-" * 60)

    # Generate OAuth URL
    auth_url, code_verifier = get_authorization_url()

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
        tokens = exchange_code_for_tokens(CallbackHandler.auth_code, code_verifier)
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
