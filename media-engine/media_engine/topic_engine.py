"""Autonomous topic proposals from public niche signals (#23).

v1 refresh is batch/hourly-friendly (not sub-minute markets). Signals:

- Hacker News (Algolia front page / search)
- Optional GitHub search (public API, unauthenticated rate limits)

Ranking uses the workspace ``niche`` string plus a TechTalk edu-finance keyword
bias inspired by ``techtalk-autonomous`` topic pools — without forking a second
video stack. Human Review before publish is unchanged.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .db import DEFAULT_WORKSPACE_PROFILE_ID, connect, DEFAULT_DB, initialize
from .workspace_profiles import get_profile

FetchFn = Callable[[str, float], dict[str, Any] | list[Any]]

DEFAULT_NICHE_KEYWORDS = (
    "ai",
    "llm",
    "fintech",
    "crypto",
    "bitcoin",
    "startup",
    "saas",
    "invest",
    "market",
    "bank",
    "payment",
    "cloud",
    "security",
    "automation",
    "agent",
    "openai",
    "nvidia",
)

ANGLE_TEMPLATES = (
    "Pragmatic builder angle: what operators should do this week",
    "Investor lens: who captures the value and who is left holding the bag",
    "Contrarian take: the popular narrative vs the boring truth",
)


class TopicEngineError(RuntimeError):
    pass


@dataclass(frozen=True)
class SignalItem:
    source: str
    title: str
    url: str
    points: int
    summary: str = ""


def _http_json(url: str, timeout: float = 12.0) -> dict[str, Any] | list[Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "otonom-media-topic-engine/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:400]
        raise TopicEngineError(f"signal fetch failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise TopicEngineError(f"signal network error: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TopicEngineError("signal response was not JSON") from exc
    return parsed


def fetch_hacker_news_signals(*, fetch: FetchFn | None = None, limit: int = 30) -> list[SignalItem]:
    fetch = fetch or _http_json
    url = "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=40"
    payload = fetch(url, 12.0)
    if not isinstance(payload, dict):
        raise TopicEngineError("HN response shape unexpected")
    hits = payload.get("hits")
    if not isinstance(hits, list) or not hits:
        raise TopicEngineError("HN feed empty or stale — try again later")
    items: list[SignalItem] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        title = str(hit.get("title") or "").strip()
        if not title:
            continue
        link = str(hit.get("url") or hit.get("story_url") or "").strip()
        if not link:
            object_id = str(hit.get("objectID") or "").strip()
            link = f"https://news.ycombinator.com/item?id={object_id}" if object_id else ""
        points = int(hit.get("points") or 0)
        items.append(
            SignalItem(
                source="hacker_news",
                title=title,
                url=link,
                points=max(0, points),
                summary=str(hit.get("story_text") or "")[:280],
            )
        )
        if len(items) >= limit:
            break
    if not items:
        raise TopicEngineError("HN feed returned no usable titles")
    return items


def fetch_github_repo_signals(query: str, *, fetch: FetchFn | None = None, limit: int = 10) -> list[SignalItem]:
    """Best-effort public GitHub search; failures are soft (empty list)."""
    fetch = fetch or _http_json
    q = urllib.parse.quote((query or "llm fintech").strip()[:80])
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={max(1, min(limit, 15))}"
    try:
        payload = fetch(url, 12.0)
    except TopicEngineError:
        return []
    if not isinstance(payload, dict):
        return []
    items_raw = payload.get("items")
    if not isinstance(items_raw, list):
        return []
    out: list[SignalItem] = []
    for repo in items_raw:
        if not isinstance(repo, dict):
            continue
        title = str(repo.get("full_name") or repo.get("name") or "").strip()
        if not title:
            continue
        out.append(
            SignalItem(
                source="github",
                title=title,
                url=str(repo.get("html_url") or "").strip(),
                points=int(repo.get("stargazers_count") or 0),
                summary=str(repo.get("description") or "")[:280],
            )
        )
    return out


def niche_keywords(niche: str) -> list[str]:
    tokens = [t for t in re.split(r"[^a-z0-9+]+", (niche or "").lower()) if len(t) >= 3]
    merged = list(dict.fromkeys([*tokens, *DEFAULT_NICHE_KEYWORDS]))
    return merged[:40]


def score_signal(item: SignalItem, keywords: list[str]) -> float:
    hay = f"{item.title} {item.summary}".lower()
    hits = sum(1 for kw in keywords if kw in hay)
    # HN points dominate; GitHub stars are larger — dampen.
    popularity = float(item.points)
    if item.source == "github":
        popularity = min(popularity, 5000.0) / 50.0
    return hits * 12.0 + min(popularity, 400.0) * 0.08 + (2.0 if item.source == "hacker_news" else 0.0)


def _confidence(score: float, max_score: float) -> float:
    if max_score <= 0:
        return 0.35
    return round(max(0.2, min(0.98, score / max_score)), 3)


def build_storyboard(title: str, angle: str, sources: list[dict[str, str]]) -> str:
    cites = "\n".join(f"- {s.get('title')} ({s.get('url')})" for s in sources[:4] if s.get("url"))
    return (
        f"TITLE: {title}\n"
        f"ANGLE: {angle}\n"
        f"STRUCTURE:\n"
        f"1) Hook — stake the claim in one sentence\n"
        f"2) Context — what just happened (cite sources)\n"
        f"3) So what — business/investor implication\n"
        f"4) Takeaway — one action for builders this week\n"
        f"SOURCES:\n{cites or '- (none)'}\n"
    )


def propose_topics(
    *,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    limit: int = 5,
    db_path: str | Any = DEFAULT_DB,
    fetch: FetchFn | None = None,
    include_github: bool = True,
) -> dict[str, Any]:
    """Return ranked topic candidates (no Path A generate)."""
    conn = connect(db_path)
    initialize(conn)
    profile = get_profile(conn, profile_id) or {"id": profile_id, "niche": "tech finance ai"}
    conn.close()
    niche = str(profile.get("niche") or "tech finance ai")
    keywords = niche_keywords(niche)

    signals = list(fetch_hacker_news_signals(fetch=fetch))
    if include_github:
        gh_query = " ".join(keywords[:4]) or "llm fintech"
        signals.extend(fetch_github_repo_signals(gh_query, fetch=fetch))

    scored: list[tuple[float, SignalItem]] = [(score_signal(s, keywords), s) for s in signals]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if not scored or scored[0][0] <= 0:
        raise TopicEngineError(
            f"No niche-relevant signals for niche={niche!r}. "
            "Widen media profile niche or retry when feeds have tech/finance stories."
        )
    max_score = scored[0][0]
    limit = max(1, min(int(limit or 5), 12))
    candidates: list[dict[str, Any]] = []
    for idx, (score, item) in enumerate(scored[:limit]):
        angle = ANGLE_TEMPLATES[idx % len(ANGLE_TEMPLATES)]
        source_row = {"source": item.source, "title": item.title, "url": item.url, "points": item.points}
        title = item.title if len(item.title) < 110 else item.title[:107] + "…"
        storyboard = build_storyboard(title, angle, [source_row])
        candidates.append(
            {
                "id": f"topic_{idx + 1}",
                "title": title,
                "angle": angle,
                "confidence": _confidence(score, max_score),
                "score": round(score, 3),
                "sources": [source_row],
                "storyboard": storyboard,
                "niche": niche,
            }
        )
    return {
        "ok": True,
        "profile_id": profile_id,
        "niche": niche,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal_count": len(signals),
        "candidates": candidates,
    }


def generate_next_topic(
    *,
    profile_id: str = DEFAULT_WORKSPACE_PROFILE_ID,
    candidate_id: str = "",
    db_path: str | Any = DEFAULT_DB,
    fetch: FetchFn | None = None,
    start_path_a: bool = True,
) -> dict[str, Any]:
    """
    Pick a proposal (top or ``candidate_id``) and optionally start Path A.

    Manual topic override remains ``POST /api/path-a-generate`` with a non-empty topic.
    """
    proposed = propose_topics(profile_id=profile_id, limit=8, db_path=db_path, fetch=fetch)
    candidates = list(proposed.get("candidates") or [])
    if not candidates:
        raise TopicEngineError("no candidates")
    chosen = candidates[0]
    if candidate_id:
        match = next((c for c in candidates if str(c.get("id")) == candidate_id), None)
        if not match:
            raise TopicEngineError(f"unknown candidate_id: {candidate_id}")
        chosen = match

    proposal_audit = {
        "candidate_id": chosen.get("id"),
        "sources": chosen.get("sources"),
        "confidence": chosen.get("confidence"),
        "angle": chosen.get("angle"),
        "niche": chosen.get("niche"),
        "score": chosen.get("score"),
    }

    path_a_job: dict[str, Any] | None = None
    if start_path_a:
        from .path_a_jobs import start_path_a_generate

        path_a_job = start_path_a_generate(
            topic=str(chosen["title"]),
            title=str(chosen["title"]),
            script=str(chosen.get("storyboard") or ""),
            profile_id=profile_id,
            topic_proposal=proposal_audit,
        )

    return {
        "ok": True,
        "candidate": chosen,
        "path_a": path_a_job,
        "review_required": True,
        "topic_proposal": proposal_audit,
    }
