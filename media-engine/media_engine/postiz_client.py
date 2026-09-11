"""Postiz Public API adapter. Connection is per-workspace (vault), not .env."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .credential_vault import get_profile_secrets, set_profile_secrets


class PostizError(RuntimeError):
    pass


DEFAULT_POSTIZ_ORIGIN = "https://api-postiz.nourdaily.com"
POSTIZ_VAULT_KEYS = ("POSTIZ_API_URL", "POSTIZ_API_KEY", "POSTIZ_CHANNEL_MAP")

PLATFORM_IDENTIFIERS: dict[str, set[str]] = {
    "youtube_shorts": {"youtube"},
    "youtube_video": {"youtube"},
    "facebook_reels": {"facebook", "facebook-page"},
    "tiktok": {"tiktok"},
    "telegram_channel": {"telegram"},
    "instagram_reels": {"instagram", "instagram-standalone"},
}


def sanitize_api_key(raw: str) -> str:
    key = (raw or "").strip().strip('"').strip("'")
    if key.lower().startswith("bearer "):
        key = key[7:].strip()
    return key


def _origin_from_url(raw: str) -> str:
    parsed = urlparse(raw)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return DEFAULT_POSTIZ_ORIGIN.rstrip("/")


def candidate_api_bases(raw: str | None) -> list[str]:
    """Self-host backends vary: /public/v1 on the API host, or /api/public/v1 on the app host."""
    text = (raw or "").strip() or DEFAULT_POSTIZ_ORIGIN
    text = text.rstrip("/")
    bases: list[str] = []
    if text.endswith("/api/public/v1"):
        origin = text[: -len("/api/public/v1")]
        bases.extend([text, f"{origin}/public/v1"])
    elif text.endswith("/public/v1"):
        origin = text[: -len("/public/v1")]
        bases.extend([text, f"{origin}/api/public/v1"])
    else:
        origin = _origin_from_url(text)
        bases.extend([f"{origin}/public/v1", f"{origin}/api/public/v1"])
    host = urlparse(bases[0]).netloc
    if host.startswith("api-"):
        sibling = f"{urlparse(bases[0]).scheme}://{host[4:]}"
        bases.extend([f"{sibling}/api/public/v1", f"{sibling}/public/v1"])
    seen: list[str] = []
    for item in bases:
        if item not in seen:
            seen.append(item)
    return seen


def normalize_postiz_api_url(raw: str | None) -> str:
    return candidate_api_bases(raw)[0]


def publish_backend() -> str:
    return (os.environ.get("PUBLISH_BACKEND") or "auto").strip().lower() or "auto"


def _vault(profile_id: str | None) -> dict[str, str]:
    from .credential_vault import active_profile_id

    profile = (profile_id or active_profile_id() or "").strip()
    if not profile:
        return {}
    return get_profile_secrets(profile)


def postiz_api_url(profile_id: str | None = None) -> str:
    return normalize_postiz_api_url(_vault(profile_id).get("POSTIZ_API_URL", ""))


def postiz_api_key(profile_id: str | None = None) -> str:
    return (_vault(profile_id).get("POSTIZ_API_KEY") or "").strip()


def channel_map(profile_id: str | None = None) -> dict[str, dict[str, str]]:
    raw = (_vault(profile_id).get("POSTIZ_CHANNEL_MAP") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    mapped: dict[str, dict[str, str]] = {}
    for platform, value in data.items():
        if isinstance(value, str) and value.strip():
            mapped[str(platform)] = {"id": value.strip(), "name": "", "identifier": ""}
        elif isinstance(value, dict):
            integration_id = str(value.get("id") or "").strip()
            if integration_id:
                mapped[str(platform)] = {
                    "id": integration_id,
                    "name": str(value.get("name") or "").strip(),
                    "identifier": str(value.get("identifier") or "").strip(),
                }
    return mapped


def channel_id_for_platform(platform: str, profile_id: str | None = None) -> str:
    return channel_map(profile_id).get(platform, {}).get("id", "")


def postiz_connected(profile_id: str | None = None) -> bool:
    return bool(postiz_api_key(profile_id))


def uses_postiz(platform: str, profile_id: str | None = None) -> bool:
    if publish_backend() == "native":
        return False
    return bool(postiz_api_key(profile_id) and channel_id_for_platform(platform, profile_id))


def connection_status(profile_id: str) -> dict[str, Any]:
    key = postiz_api_key(profile_id)
    url = postiz_api_url(profile_id) if key else normalize_postiz_api_url(DEFAULT_POSTIZ_ORIGIN)
    channels = channel_map(profile_id)
    return {
        "connected": bool(key),
        "api_url": url,
        "api_origin": DEFAULT_POSTIZ_ORIGIN,
        "channels": channels,
    }


def save_connection(profile_id: str, *, api_url: str, api_key: str) -> dict[str, Any]:
    profile_id = (profile_id or "").strip()
    if not profile_id:
        raise PostizError("profile_id is required")
    key = sanitize_api_key(api_key)
    if not key:
        raise PostizError("Postiz API key is required")
    last_error: PostizError | None = None
    for base in candidate_api_bases(api_url):
        set_profile_secrets(
            profile_id,
            {
                "POSTIZ_API_URL": base,
                "POSTIZ_API_KEY": key,
            },
        )
        try:
            integrations = list_integrations(profile_id)
            return {"status": "connected", "profile_id": profile_id, "api_url": base, "integrations": _public_integrations(integrations)}
        except PostizError as exc:
            last_error = exc
            detail = str(exc)
            if "HTTP 401" in detail or "Invalid API key" in detail or "No API Key" in detail:
                from .credential_vault import unset_profile_secrets

                unset_profile_secrets(profile_id, ["POSTIZ_API_URL", "POSTIZ_API_KEY"])
                raise PostizError(
                    "Postiz rejected the API key. Reveal + copy the key from Settings → Public API (no Bearer prefix)."
                ) from exc
    from .credential_vault import unset_profile_secrets

    unset_profile_secrets(profile_id, ["POSTIZ_API_URL", "POSTIZ_API_KEY"])
    hint = (
        "Tried /public/v1 and /api/public/v1. If this is Cloudflare Access, allow unauthenticated "
        "GET/POST to /public/v1 on the API host. Last error: "
    )
    raise PostizError(hint + str(last_error or "Postiz connect failed"))


def disconnect(profile_id: str) -> dict[str, Any]:
    from .credential_vault import unset_profile_secrets

    unset_profile_secrets(profile_id, list(POSTIZ_VAULT_KEYS))
    return {"status": "disconnected", "profile_id": profile_id}


def map_platform(profile_id: str, platform: str, integration: dict[str, Any] | None) -> dict[str, Any]:
    if platform not in PLATFORM_IDENTIFIERS:
        raise PostizError(f"unsupported platform: {platform}")
    current = channel_map(profile_id)
    if not integration or not str(integration.get("id") or "").strip():
        current.pop(platform, None)
    else:
        current[platform] = {
            "id": str(integration.get("id")).strip(),
            "name": str(integration.get("name") or "").strip(),
            "identifier": str(integration.get("identifier") or "").strip(),
        }
    set_profile_secrets(profile_id, {"POSTIZ_CHANNEL_MAP": json.dumps(current, ensure_ascii=False)})
    return {"profile_id": profile_id, "platform": platform, "channels": current}


def integration_identifier(item: dict[str, Any]) -> str:
    return str(item.get("identifier") or item.get("providerIdentifier") or item.get("name") or "").strip().lower()


def integrations_for_platform(platform: str, integrations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aliases = PLATFORM_IDENTIFIERS.get(platform, set())
    matched = [item for item in integrations if integration_identifier(item) in aliases]
    return _public_integrations(matched or integrations)


def _public_integrations(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    public: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        integration_id = str(item.get("id") or "").strip()
        if not integration_id:
            continue
        public.append(
            {
                "id": integration_id,
                "name": str(item.get("name") or item.get("displayName") or integration_id),
                "identifier": str(item.get("identifier") or item.get("providerIdentifier") or ""),
                "disabled": bool(item.get("disabled")),
            }
        )
    return public


def settings_for_platform(platform: str, *, title: str, caption: str) -> dict[str, Any]:
    safe_title = (title or "Short").strip()[:100]
    if len(safe_title) < 2:
        safe_title = "Short clip"
    if platform in {"youtube_shorts", "youtube_video"}:
        return {
            "__type": "youtube",
            "title": safe_title,
            "type": "public",
            "selfDeclaredMadeForKids": "no",
            "tags": [],
        }
    if platform == "tiktok":
        return {
            "__type": "tiktok",
            "privacy_level": "SELF_ONLY",
            "duet": False,
            "stitch": False,
            "comment": True,
            "autoAddMusic": False,
            "brand_content_toggle": False,
            "brand_organic_toggle": False,
            "content_posting_method": "DIRECT_POST",
        }
    if platform == "facebook_reels":
        return {"__type": "facebook"}
    if platform == "telegram_channel":
        return {"__type": "telegram"}
    if platform == "instagram_reels":
        return {"__type": "instagram", "post_type": "reel"}
    raise PostizError(f"Postiz settings are not defined for {platform}")


def to_postiz_date(value: datetime | str) -> str:
    if isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    else:
        parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


_POSTIZ_POST_ID = re.compile(r"^c[a-z0-9]{20,}$")
_MEDIA_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def is_postiz_post_id(value: str) -> bool:
    return bool(_POSTIZ_POST_ID.match(str(value or "").strip()))


def _collect_ids(payload: Any, found: list[str]) -> None:
    if isinstance(payload, dict):
        for key in ("postId", "post_id", "id"):
            value = str(payload.get(key) or "").strip()
            if value:
                found.append(value)
        for value in payload.values():
            if isinstance(value, (dict, list)):
                _collect_ids(value, found)
        return
    if isinstance(payload, list):
        for item in payload:
            _collect_ids(item, found)


def extract_remote_id(payload: Any, *, exclude: set[str] | None = None) -> str:
    skip = {item for item in (exclude or set()) if item}
    found: list[str] = []
    _collect_ids(payload, found)
    candidates = [item for item in found if item not in skip]
    for item in candidates:
        if is_postiz_post_id(item):
            return item
    for item in candidates:
        if not _MEDIA_UUID.match(item):
            return item
    return ""


POSTIZ_LIVE_STATUSES = {"live", "published"}
POSTIZ_HELD_STATUSES = {"queued", "scheduled", "accepted", "published", "live"}
_POSTIZ_GONE_MARKERS = (
    "HTTP 404",
    "integrationId",
    "Cannot read properties of undefined",
)


def on_postiz_calendar(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    if str(result.get("backend") or "") != "postiz":
        return False
    if not str(result.get("remote_id") or "").strip():
        return False
    return str(result.get("status") or "") in POSTIZ_HELD_STATUSES


def build_create_post_body(
    *,
    integration_id: str,
    caption: str,
    media: dict[str, str],
    platform: str,
    title: str,
    post_type: str = "now",
    date_iso: str | None = None,
) -> dict[str, Any]:
    stamp = to_postiz_date(date_iso) if date_iso else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    kind = (post_type or "now").strip().lower()
    if kind not in {"now", "schedule", "draft"}:
        kind = "now"
    return {
        "type": kind,
        "date": stamp,
        "shortLink": False,
        "tags": [],
        "posts": [
            {
                "integration": {"id": integration_id},
                "value": [
                    {
                        "content": caption or title or "Short",
                        "image": [{"id": media["id"], "path": media["path"]}],
                    }
                ],
                "settings": settings_for_platform(platform, title=title, caption=caption),
            }
        ],
    }


def _request_json(method: str, path: str, *, body: bytes | None = None, content_type: str = "application/json", profile_id: str | None = None, timeout: int = 120) -> Any:
    key = sanitize_api_key(postiz_api_key(profile_id))
    if not key:
        raise PostizError("Connect Postiz in Publish for this workspace first")
    url = f"{postiz_api_url(profile_id)}{path}"
    headers = {
        "Authorization": key,
        "Accept": "application/json",
        "User-Agent": "OtonomMedia/1.0",
    }
    if body is not None:
        headers["Content-Type"] = content_type
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:800]
        raise PostizError(f"Postiz {method} {url} failed: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise PostizError(f"Postiz {method} {url} failed: {exc}") from exc
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def list_integrations(profile_id: str | None = None) -> list[dict[str, Any]]:
    payload = _request_json("GET", "/integrations", profile_id=profile_id)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("integrations") or payload.get("data") or []
        if isinstance(items, list):
            return items
    return []


def _integration_needs_reconnect(item: dict[str, Any]) -> str:
    if bool(item.get("disabled")):
        return "disabled"
    if item.get("refreshNeeded") or item.get("tokenExpired") or item.get("inBetweenSteps"):
        return "token"
    return ""


def validate_channel(platform: str, profile_id: str | None = None) -> dict[str, Any]:
    channel_id = channel_id_for_platform(platform, profile_id)
    if not postiz_api_key(profile_id):
        raise PostizError("Connect Postiz in Publish for this workspace first")
    if not channel_id:
        raise PostizError(f"Map a Postiz channel for {platform} first")
    integrations = list_integrations(profile_id)
    match = next((item for item in integrations if str(item.get("id") or "") == channel_id), None)
    if not match:
        raise PostizError(f"Postiz integration {channel_id} was not found for {platform}")
    reason = _integration_needs_reconnect(match)
    if reason:
        raise PostizError(f"Reconnect {platform} in Postiz before scheduling (channel {reason})")
    return {
        "platform": platform,
        "status": "authorized",
        "backend": "postiz",
        "integration_id": channel_id,
        "raw": match,
    }


def upload_media(video_path: str | Path, profile_id: str | None = None) -> dict[str, str]:
    path = Path(video_path)
    if not path.exists():
        raise PostizError(f"video file is missing: {path}")
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    boundary = f"----Otonom{uuid.uuid4().hex}"
    filename = path.name
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header + path.read_bytes() + footer
    payload = _request_json(
        "POST",
        "/upload",
        body=body,
        content_type=f"multipart/form-data; boundary={boundary}",
        profile_id=profile_id,
    )
    media_id = str(payload.get("id") or "").strip()
    media_path = str(payload.get("path") or "").strip()
    if not media_id or not media_path:
        raise PostizError(f"Postiz upload did not return id/path: {payload}")
    return {"id": media_id, "path": media_path, "name": str(payload.get("name") or filename)}


def create_post(body: dict[str, Any], profile_id: str | None = None) -> dict[str, Any]:
    payload = _request_json("POST", "/posts", body=json.dumps(body).encode("utf-8"), profile_id=profile_id)
    if isinstance(payload, list):
        payload = {"posts": payload}
    if not isinstance(payload, dict):
        raise PostizError(f"Postiz create post returned unexpected payload: {payload}")
    return payload


def flatten_postiz_posts(payload: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = payload.get("posts") or payload.get("data") or payload.get("items")
        if raw is None:
            raw = [payload] if payload.get("id") or payload.get("state") else []
        if isinstance(raw, dict):
            raw = [raw]
    else:
        raw = []
    if not isinstance(raw, list):
        return items
    for item in raw:
        if isinstance(item, dict):
            items.append(item)
    return items


def map_postiz_delivery_status(post: dict[str, Any]) -> str:
    # Postiz can keep state=ERROR after Meta/YouTube already accepted the upload (worker timeout,
    # late releaseURL, etc.). A release URL is stronger proof than the workflow flag.
    url = str(post.get("releaseURL") or post.get("url") or "").strip()
    if url:
        return "live"
    state = _postiz_release_state(post)
    if state in {"published", "ok", "success", "posted"}:
        return "live"
    if state in {"error", "failed", "canceled", "cancelled"}:
        return "failed"
    return "queued"


def index_posts_by_id(posts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}

    def add(item: dict[str, Any], parent: dict[str, Any] | None = None) -> None:
        record = item
        if parent and not _postiz_release_state(item) and _postiz_release_state(parent):
            record = {**item, "state": parent.get("state") or parent.get("status") or parent.get("releaseState")}
        remote = extract_remote_id(item)
        post_id = str(item.get("id") or "").strip()
        if remote:
            indexed[remote] = record
        if post_id:
            indexed[post_id] = record
        nested = item.get("posts")
        if isinstance(nested, list):
            for child in nested:
                if isinstance(child, dict):
                    add(child, item)

    for post in posts:
        if isinstance(post, dict):
            add(post)
    return indexed


def _postiz_utc_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def list_posts(
    profile_id: str | None = None,
    *,
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    if isinstance(start_date, datetime):
        start = _postiz_utc_stamp(start_date)
    elif start_date:
        start = str(start_date)
    else:
        start = _postiz_utc_stamp(now - timedelta(days=14))
    if isinstance(end_date, datetime):
        end = _postiz_utc_stamp(end_date)
    elif end_date:
        end = str(end_date)
    else:
        end = _postiz_utc_stamp(now + timedelta(days=30))
    path = f"/posts?startDate={quote(start)}&endDate={quote(end)}"
    try:
        payload = _request_json("GET", path, profile_id=profile_id, timeout=20)
    except PostizError:
        return []
    return flatten_postiz_posts(payload)


def get_post(post_id: str, profile_id: str | None = None) -> dict[str, Any] | None:
    remote_id = str(post_id or "").strip()
    if not remote_id:
        return None
    try:
        payload = _request_json("GET", f"/posts/{remote_id}", profile_id=profile_id, timeout=12)
    except PostizError as exc:
        if any(marker in str(exc) for marker in _POSTIZ_GONE_MARKERS) or "HTTP 500" in str(exc):
            return None
        raise
    if isinstance(payload, list):
        payload = payload[0] if payload and isinstance(payload[0], dict) else {}
    return payload if isinstance(payload, dict) else None


def _postiz_release_state(payload: dict[str, Any]) -> str:
    for key in ("state", "status", "releaseState"):
        value = str(payload.get(key) or "").strip().lower()
        if value:
            return value
    posts = payload.get("posts")
    if isinstance(posts, list) and posts and isinstance(posts[0], dict):
        return _postiz_release_state(posts[0])
    return ""


def delete_post(post_id: str, profile_id: str | None = None) -> None:
    remote_id = str(post_id or "").strip()
    if not remote_id:
        return
    try:
        _request_json("DELETE", f"/posts/{remote_id}", profile_id=profile_id)
    except PostizError as exc:
        if any(marker in str(exc) for marker in _POSTIZ_GONE_MARKERS):
            return
        raise


def publish_video(
    platform: str,
    payload: dict[str, Any],
    profile_id: str | None = None,
    post_type: str = "now",
    date_iso: str | None = None,
) -> dict[str, Any]:
    validate_channel(platform, profile_id)
    integration_id = channel_id_for_platform(platform, profile_id)
    video_path = str(payload.get("video_path") or "")
    media = upload_media(video_path, profile_id=profile_id)
    kind = (post_type or "now").strip().lower()
    body = build_create_post_body(
        integration_id=integration_id,
        caption=str(payload.get("caption") or ""),
        media=media,
        platform=platform,
        title=str(payload.get("title") or "Short"),
        post_type=kind,
        date_iso=date_iso,
    )
    result = create_post(body, profile_id=profile_id)
    remote_id = extract_remote_id(result, exclude={media.get("id", "")})
    status = "queued" if kind == "schedule" else "accepted"
    remote_url = ""
    polled = None
    if remote_id:
        try:
            polled = get_post(remote_id, profile_id=profile_id)
        except PostizError:
            polled = None
    if polled:
        state = _postiz_release_state(polled)
        if state in {"published", "ok", "success"}:
            status = "live"
            remote_url = str(polled.get("releaseURL") or polled.get("url") or result.get("url") or "")
    return {
        "platform": platform,
        "status": status,
        "backend": "postiz",
        "remote_id": remote_id,
        "remote_url": remote_url,
        "post_type": kind,
        "postiz_media": media,
        "raw": result,
    }
