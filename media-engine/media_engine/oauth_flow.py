"""Local OAuth connect/reconnect flows for publish platforms."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .env_loader import load_env_file
from .credential_vault import resolve_env_value, set_profile_secrets


class OAuthFlowError(RuntimeError):
    pass


OAUTH_TTL_SECONDS = 15 * 60
_OAUTH_STATES: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class OAuthStartResult:
    platform: str
    auth_url: str
    state: str
    expires_in: int
    profile_id: str = "nourbit"


def _env_first(*keys: str, profile_id: str | None = None) -> str:
    return resolve_env_value(*keys, profile_id=profile_id)


def _json_get(url: str, headers: dict[str, str] | None = None, timeout_seconds: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
            return json.loads(text or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise OAuthFlowError(raw or f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OAuthFlowError(f"request failed: {exc}") from exc


def _form_post(url: str, fields: dict[str, str], timeout_seconds: int = 30) -> dict[str, Any]:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            text = response.read().decode("utf-8")
            return json.loads(text or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise OAuthFlowError(raw or f"HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OAuthFlowError(f"request failed: {exc}") from exc


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode("utf-8").rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("utf-8").rstrip("=")
    return verifier, challenge


def _remember_state(state: str, platform: str, payload: dict[str, Any] | None = None) -> None:
    _OAUTH_STATES[state] = {
        "platform": platform,
        "created_at": int(time.time()),
        "payload": payload or {},
    }


def _pop_state(state: str, platform: str) -> dict[str, Any]:
    row = _OAUTH_STATES.pop(state, None)
    if not row:
        raise OAuthFlowError("OAuth session expired. Start connect again.")
    if row.get("platform") != platform:
        raise OAuthFlowError("OAuth state mismatch. Start connect again.")
    if int(time.time()) - int(row.get("created_at") or 0) > OAUTH_TTL_SECONDS:
        raise OAuthFlowError("OAuth session timed out. Start connect again.")
    return row.get("payload") or {}


def _redirect_for(platform: str, server_base: str) -> str:
    keys: list[str] = []
    if platform == "youtube_shorts":
        keys.append("YOUTUBE_REDIRECT_URI")
    elif platform == "facebook_reels":
        keys.append("META_REDIRECT_URI")
    elif platform == "tiktok":
        keys.append("TIKTOK_REDIRECT_URI")
    explicit = _env_first(*keys) if keys else ""
    if explicit:
        return explicit
    return f"{server_base.rstrip('/')}/api/oauth/callback/{platform}"


def start_oauth(
    platform: str,
    server_base: str,
    env_file: str | Path,
    profile_id: str = "nourbit",
) -> OAuthStartResult:
    load_env_file(env_file)
    profile_id = (profile_id or "nourbit").strip() or "nourbit"
    state = secrets.token_urlsafe(24)
    redirect_uri = _redirect_for(platform, server_base)
    base_payload = {"profile_id": profile_id}

    if platform == "youtube_shorts":
        client_id = _env_first("YOUTUBE_CLIENT_ID")
        if not client_id:
            raise OAuthFlowError("YOUTUBE_CLIENT_ID is missing")
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
        _remember_state(state, platform, base_payload)
        return OAuthStartResult(platform=platform, auth_url=auth_url, state=state, expires_in=OAUTH_TTL_SECONDS, profile_id=profile_id)

    if platform == "facebook_reels":
        app_id = _env_first("META_APP_ID")
        api_version = _env_first("META_API_VERSION") or "v20.0"
        if not app_id:
            raise OAuthFlowError("META_APP_ID is missing")
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
            "scope": ",".join(
                [
                    "pages_show_list",
                    "pages_manage_posts",
                    "pages_read_engagement",
                    "pages_manage_metadata",
                    "pages_manage_videos",
                ]
            ),
        }
        auth_url = f"https://www.facebook.com/{api_version}/dialog/oauth?" + urllib.parse.urlencode(params)
        _remember_state(state, platform, base_payload)
        return OAuthStartResult(platform=platform, auth_url=auth_url, state=state, expires_in=OAUTH_TTL_SECONDS, profile_id=profile_id)

    if platform == "tiktok":
        client_key = _env_first("TIKTOK_CLIENT_KEY")
        if not client_key:
            raise OAuthFlowError("TIKTOK_CLIENT_KEY is missing")
        verifier, challenge = _pkce_pair()
        scopes = _env_first("TIKTOK_SCOPES") or "user.info.basic,video.upload,video.publish"
        params = {
            "client_key": client_key,
            "redirect_uri": redirect_uri,
            "scope": scopes,
            "response_type": "code",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        auth_url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
        _remember_state(state, platform, {**base_payload, "code_verifier": verifier, "redirect_uri": redirect_uri})
        return OAuthStartResult(platform=platform, auth_url=auth_url, state=state, expires_in=OAUTH_TTL_SECONDS, profile_id=profile_id)

    raise OAuthFlowError(f"OAuth is not supported for {platform}")


def complete_oauth(platform: str, query: dict[str, str], server_base: str, env_file: str | Path) -> dict[str, Any]:
    load_env_file(env_file)
    error = (query.get("error") or "").strip()
    if error:
        raise OAuthFlowError(f"OAuth failed: {error}")
    state = (query.get("state") or "").strip()
    code = (query.get("code") or "").strip()
    if not state or not code:
        raise OAuthFlowError("Missing OAuth state or code")
    payload = _pop_state(state, platform)
    profile_id = str(payload.get("profile_id") or "nourbit").strip() or "nourbit"
    redirect_uri = payload.get("redirect_uri") or _redirect_for(platform, server_base)

    if platform == "youtube_shorts":
        client_id = _env_first("YOUTUBE_CLIENT_ID")
        client_secret = _env_first("YOUTUBE_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise OAuthFlowError("YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET are required")
        token = _form_post(
            "https://oauth2.googleapis.com/token",
            {
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        refresh = str(token.get("refresh_token") or "").strip()
        if not refresh:
            current = _env_first("YOUTUBE_REFRESH_TOKEN", profile_id=profile_id)
            if not current:
                raise OAuthFlowError("OAuth completed but no refresh token was returned. Remove app access and reconnect with consent.")
            refresh = current
        set_profile_secrets(profile_id, {"YOUTUBE_REFRESH_TOKEN": refresh})
        return {"platform": platform, "status": "connected", "profile_id": profile_id}

    if platform == "facebook_reels":
        app_id = _env_first("META_APP_ID")
        app_secret = _env_first("META_APP_SECRET")
        api_version = _env_first("META_API_VERSION") or "v20.0"
        if not app_id or not app_secret:
            raise OAuthFlowError("META_APP_ID and META_APP_SECRET are required")
        token = _json_get(
            "https://graph.facebook.com/" + api_version + "/oauth/access_token?"
            + urllib.parse.urlencode(
                {
                    "client_id": app_id,
                    "client_secret": app_secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                }
            ),
        )
        user_access_token = str(token.get("access_token") or "").strip()
        if not user_access_token:
            raise OAuthFlowError(f"Facebook did not return access_token: {token}")
        page_id = _env_first("META_PAGE_ID", "NOURBIT_FACEBOOK_PAGE_ID", profile_id=profile_id)
        page_tok = ""
        resolved_page_id = page_id
        if page_id:
            page_info = _json_get(
                "https://graph.facebook.com/" + api_version + "/" + page_id + "?"
                + urllib.parse.urlencode({"fields": "id,name,access_token", "access_token": user_access_token}),
            )
            raw_page = page_info.get("access_token") or ""
            page_tok = str(raw_page).strip()
        else:
            pages = _json_get(
                "https://graph.facebook.com/" + api_version + "/me/accounts?"
                + urllib.parse.urlencode({"access_token": user_access_token}),
            )
            data = pages.get("data") or []
            if not data:
                raise OAuthFlowError("No Facebook pages found for this account")
            first = data[0]
            resolved_page_id = str(first.get("id") or "").strip()
            raw_page = first.get("access_token") or ""
            page_tok = str(raw_page).strip()
        if not resolved_page_id or not page_tok:
            raise OAuthFlowError("Unable to resolve Facebook page token")
        set_profile_secrets(
            profile_id,
            {
                "META_PAGE_ID": resolved_page_id,
                "META_PAGE_ACCESS_TOKEN": page_tok,
            },
        )
        return {"platform": platform, "status": "connected", "page_id": resolved_page_id, "profile_id": profile_id}

    if platform == "tiktok":
        client_key = _env_first("TIKTOK_CLIENT_KEY")
        client_secret = _env_first("TIKTOK_CLIENT_SECRET")
        code_verifier = str(payload.get("code_verifier") or "").strip()
        if not client_key or not client_secret:
            raise OAuthFlowError("TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET are required")
        if not code_verifier:
            raise OAuthFlowError("TikTok OAuth verifier is missing. Start connect again.")
        token = _form_post(
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
        access = str(token.get("access_token") or "").strip()
        refresh = str(token.get("refresh_token") or "").strip()
        open_id = str(token.get("open_id") or "").strip()
        if not access or not refresh:
            raise OAuthFlowError(f"TikTok did not return access/refresh token: {token}")
        updates = {
            "TIKTOK_ACCESS_TOKEN": access,
            "TIKTOK_REFRESH_TOKEN": refresh,
        }
        if open_id:
            updates["TIKTOK_OPEN_ID"] = open_id
        set_profile_secrets(profile_id, updates)
        return {"platform": platform, "status": "connected", "profile_id": profile_id}

    raise OAuthFlowError(f"OAuth is not supported for {platform}")
