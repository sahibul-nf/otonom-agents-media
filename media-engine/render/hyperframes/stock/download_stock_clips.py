#!/usr/bin/env python3
"""Download per-template HyperFrames preview stock (Pexels or Mixkit).

Each template gets `{template_id}.mp4`. With PEXELS_API_KEY in repo `.env.local`,
`--source pexels` (default when key is set) fetches higher-quality portrait clips.

Usage:
  python3 media-engine/render/hyperframes/stock/download_stock_clips.py
  python3 media-engine/render/hyperframes/stock/download_stock_clips.py --source mixkit
  python3 media-engine/render/hyperframes/stock/download_stock_clips.py --source pexels --rewarm-previews
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

STOCK_DIR = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_FILE = REPO_ROOT / ".env.local"
ATTRIBUTION_FILE = STOCK_DIR / "stock_attribution.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Pexels search per template (query + preferred orientation).
TEMPLATE_PEXELS: dict[str, dict[str, str]] = {
    "spiritual_reflective": {"query": "man talking calm portrait", "orientation": "portrait"},
    "energy_warm_question": {"query": "woman recording vertical video phone", "orientation": "portrait"},
    "arion_pink_callout": {"query": "woman smiling street fashion portrait", "orientation": "portrait"},
    "quintessence_serif": {"query": "elegant woman portrait beach", "orientation": "portrait"},
    "archive_magazine": {"query": "reading book editorial portrait", "orientation": "portrait"},
    "story_handwritten": {"query": "woman writing journal creative", "orientation": "portrait"},
    "kai_mustard_uppercase": {"query": "businessman presenting confident", "orientation": "landscape"},
    "byline_trust_quote": {"query": "woman professional interview talking", "orientation": "portrait"},
    "sonnet_botanical": {"query": "botanical plants soft light", "orientation": "portrait"},
    "rocket_glitch": {"query": "gaming neon lights cyber", "orientation": "landscape"},
    "grit_training_stamp": {"query": "gym workout dark mood", "orientation": "portrait"},
    "cove_callout_pill": {"query": "smartphone social media vertical", "orientation": "portrait"},
    "pulse_remember_overlay": {"query": "man speaking microphone podcast", "orientation": "portrait"},
    "neon_seize_future": {"query": "neon lights futuristic city", "orientation": "portrait"},
    "velocity_business_promo": {"query": "business team office dynamic", "orientation": "landscape"},
    "blueprint_grid_paper": {"query": "architecture blueprint technical", "orientation": "landscape"},
    "sketch_post_it": {"query": "creative team brainstorming office", "orientation": "landscape"},
    "prism_pro_pricing": {"query": "laptop saas product demo", "orientation": "landscape"},
    "chalk_word_emphasis": {"query": "teacher classroom talking", "orientation": "portrait"},
}

TEMPLATE_MIXKIT_PAGES: dict[str, str] = {
    "spiritual_reflective": "therapist-in-his-office-talking-to-the-camera-4834",
    "energy_warm_question": "young-woman-recording-a-vertical-video-on-her-phone-40774",
    "arion_pink_callout": "blonde-girl-smiling-head-on-on-the-street-4815",
    "quintessence_serif": "portrait-of-a-woman-at-the-beach-1104",
    "archive_magazine": "girl-reading-a-book-in-nature-4897",
    "story_handwritten": "woman-writing-in-a-notebook-3280",
    "kai_mustard_uppercase": "confident-young-businessman-doing-a-presentation-23117",
    "byline_trust_quote": "woman-speaking-to-a-psychologist-6045",
    "sonnet_botanical": "close-up-of-green-leaves-in-the-wind-1171",
    "rocket_glitch": "programming-and-coding-new-technologies-46635",
    "grit_training_stamp": "man-doing-weightlifting-exercises-32808",
    "cove_callout_pill": "apps-on-a-smartphone-screen-4293",
    "pulse_remember_overlay": "man-speaking-into-the-microphone-at-record-studio-2955",
    "neon_seize_future": "a-woman-wearign-a-futuristic-vr-glasses-concentrates-on-the-51214",
    "velocity_business_promo": "business-man-exposing-graphs-42648",
    "blueprint_grid_paper": "high-tech-circuit-board-with-processor-47051",
    "sketch_post_it": "work-team-planning-meeting-21247",
    "prism_pro_pricing": "man-working-on-his-laptop-308",
    "chalk_word_emphasis": "a-middle-age-man-teacher-wearing-glasses-talking-to-a-50117",
}

LEGACY_POOL_PAGES: dict[str, str] = {
    "portrait_warm_talk.mp4": "man-talking-on-a-video-call-4075",
    "portrait_social_energy.mp4": "young-woman-recording-a-vertical-video-on-her-phone-40774",
    "portrait_handwritten_story.mp4": "woman-writing-in-a-notebook-3280",
    "portrait_training_dark.mp4": "man-doing-weightlifting-exercises-32808",
    "portrait_product_demo.mp4": "apps-on-a-smartphone-screen-4293",
    "landscape_news_desk.mp4": "news-anchor-reading-the-news-4635",
    "landscape_data_screen.mp4": "hands-typing-on-a-computer-keyboard-4916",
    "landscape_editorial_grain.mp4": "aerial-view-of-a-city-at-night-4159",
}


PEXELS_ENV_VAR = "PEXELS_API_KEY"


def _load_pexels_auth() -> str:
    key = (os.environ.get(PEXELS_ENV_VAR) or "").strip()
    if key:
        return key
    if ENV_FILE.exists():
        sys_path = str(REPO_ROOT / "media-engine")
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        try:
            from media_engine.env_loader import load_env_file

            load_env_file(ENV_FILE)
            key = (os.environ.get(PEXELS_ENV_VAR) or "").strip()
        except Exception:
            key = ""
    if not key and ENV_FILE.exists():
        prefix = f"{PEXELS_ENV_VAR}="
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith(prefix):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return key


def _pexels_search(pexels_auth: str, query: str, orientation: str, per_page: int = 8) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "per_page": str(per_page),
            "orientation": orientation,
            "size": "medium",
        }
    )
    url = f"https://api.pexels.com/videos/search?{params}"
    request = urllib.request.Request(url, headers={"Authorization": pexels_auth, "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    videos = payload.get("videos") or []
    return [video for video in videos if isinstance(video, dict)]


def _pick_pexels_file(video: dict[str, Any], orientation: str) -> dict[str, Any] | None:
    files = [item for item in (video.get("video_files") or []) if isinstance(item, dict)]
    if not files:
        return None
    mp4 = [item for item in files if str(item.get("file_type") or "").startswith("video/mp4")]
    candidates = mp4 or files

    def score(item: dict[str, Any]) -> tuple[int, int]:
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        pixels = width * height
        if orientation == "portrait" and height > width:
            return (1, pixels)
        if orientation == "landscape" and width >= height:
            return (1, pixels)
        return (0, pixels)

    return max(candidates, key=score)


def _download_url(url: str, destination: Path, referer: str = "") -> None:
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=240) as response, destination.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def _trim_preview_length(path: Path, max_seconds: int = 20) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or max_seconds <= 0:
        return
    temp = path.with_suffix(".trim.mp4")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(path),
        "-t",
        str(max_seconds),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(temp),
    ]
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0 and temp.exists() and temp.stat().st_size > 0:
        temp.replace(path)


def download_pexels_templates(pexels_auth: str) -> tuple[int, int, dict[str, Any]]:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    attribution: dict[str, Any] = {"source": "pexels", "templates": {}}
    ok = 0
    total = len(TEMPLATE_PEXELS)
    for template_id, spec in TEMPLATE_PEXELS.items():
        destination = STOCK_DIR / f"{template_id}.mp4"
        query = spec["query"]
        orientation = spec.get("orientation") or "portrait"
        try:
            videos = _pexels_search(pexels_auth, query, orientation)
            chosen_file = None
            chosen_video = None
            for video in videos:
                chosen_file = _pick_pexels_file(video, orientation)
                if chosen_file:
                    chosen_video = video
                    break
            if not chosen_file or not chosen_video:
                raise RuntimeError(f"No suitable Pexels video for query={query!r}")

            link = str(chosen_file.get("link") or "")
            if not link:
                raise RuntimeError("Pexels video file missing link")
            _download_url(link, destination, referer="https://www.pexels.com/")
            _trim_preview_length(destination, max_seconds=20)

            user = chosen_video.get("user") or {}
            attribution["templates"][template_id] = {
                "query": query,
                "orientation": orientation,
                "video_id": chosen_video.get("id"),
                "width": chosen_file.get("width"),
                "height": chosen_file.get("height"),
                "pexels_url": chosen_video.get("url"),
                "photographer": user.get("name"),
                "photographer_url": user.get("url"),
            }
            print(
                f"{template_id}.mp4 <- Pexels {chosen_file.get('width')}x{chosen_file.get('height')} "
                f"({user.get('name') or 'unknown'})"
            )
            print(f"  saved {destination.stat().st_size // 1024} KB")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {template_id}: {exc}")
    ATTRIBUTION_FILE.write_text(json.dumps(attribution, indent=2, ensure_ascii=False), encoding="utf-8")
    return ok, total, attribution


def _page_url(slug: str) -> str:
    return f"https://mixkit.co/free-stock-video/{slug}/"


def _best_mixkit_mp4_url(page_url: str) -> str:
    request = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    html = urllib.request.urlopen(request, timeout=45).read().decode("utf-8", errors="ignore")
    links = sorted(set(re.findall(r"https://assets\.mixkit\.co/videos/\d+/\d+-\d+\.mp4", html)))
    if not links:
        raise RuntimeError(f"No mp4 URLs found on {page_url}")

    def resolution(link: str) -> int:
        match = re.search(r"-(\d+)\.mp4$", link)
        return int(match.group(1)) if match else 0

    return max(links, key=resolution)


def _download_mixkit_slug(slug: str, destination: Path) -> str:
    page = _page_url(slug)
    mp4 = _best_mixkit_mp4_url(page)
    _download_url(mp4, destination, referer=page)
    return mp4


def download_mixkit_templates() -> tuple[int, int]:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    total = len(TEMPLATE_MIXKIT_PAGES)
    for template_id, slug in TEMPLATE_MIXKIT_PAGES.items():
        destination = STOCK_DIR / f"{template_id}.mp4"
        try:
            mp4 = _download_mixkit_slug(slug, destination)
            print(f"{template_id}.mp4 <- Mixkit {mp4}")
            print(f"  saved {destination.stat().st_size // 1024} KB")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {template_id}: {exc}")
    return ok, total


def download_legacy_pools() -> tuple[int, int]:
    STOCK_DIR.mkdir(parents=True, exist_ok=True)
    ok = 0
    total = len(LEGACY_POOL_PAGES)
    for filename, slug in LEGACY_POOL_PAGES.items():
        destination = STOCK_DIR / filename
        try:
            mp4 = _download_mixkit_slug(slug, destination)
            print(f"{filename} <- Mixkit {mp4}")
            print(f"  saved {destination.stat().st_size // 1024} KB")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED {filename}: {exc}")
    return ok, total


def rewarm_previews() -> None:
    media_engine = REPO_ROOT / "media-engine"
    previews = media_engine / "artifacts" / "hyperframes_template_previews"
    if previews.exists():
        shutil.rmtree(previews)
    env = os.environ.copy()
    env["HYPERFRAMES_ENABLED"] = "true"
    env.setdefault("PYTHONPATH", str(media_engine))
    if ENV_FILE.exists():
        from media_engine.env_loader import load_env_file

        load_env_file(ENV_FILE)
    script = (
        "from media_engine.hyperframes_previews import prewarm_hyperframes_template_previews; "
        "import json; print(json.dumps(prewarm_hyperframes_template_previews(include_brand=False), indent=2))"
    )
    subprocess.run(
        ["python3", "-c", script],
        cwd=str(media_engine),
        env=env,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("auto", "pexels", "mixkit"), default="auto")
    parser.add_argument("--legacy-pools", action="store_true", help="Also refresh shared pool mp4 files")
    parser.add_argument(
        "--rewarm-previews",
        action="store_true",
        help="Delete and regenerate HyperFrames template previews after download",
    )
    args = parser.parse_args()

    source = args.source
    if source == "auto":
        source = "pexels" if _load_pexels_auth() else "mixkit"

    if source == "pexels":
        pexels_auth = _load_pexels_auth()
        if not pexels_auth:
            print(f"{PEXELS_ENV_VAR} not found in environment or .env.local — falling back to Mixkit.")
            ok, total = download_mixkit_templates()
        else:
            print("Using Pexels API for template stock clips.")
            ok, total, _attribution = download_pexels_templates(pexels_auth)
            print(f"Attribution written to {ATTRIBUTION_FILE}")
    else:
        ok, total = download_mixkit_templates()

    print(f"\nTemplates: {ok}/{total} in {STOCK_DIR}")

    if args.legacy_pools:
        ok2, total2 = download_legacy_pools()
        print(f"Legacy pools: {ok2}/{total2}")

    if args.rewarm_previews and ok == total:
        print("\nRewarming HyperFrames template previews (this may take ~15–20 minutes)...")
        rewarm_previews()

    return 0 if ok == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
