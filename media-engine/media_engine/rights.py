"""Rights and publishing guardrails."""

from __future__ import annotations

import json
from typing import Any

from .models import (
    GuardResult,
    PUBLISH_AUTO,
    PUBLISH_EXPORT_ONLY,
    PUBLISH_OFF,
    PUBLISH_REVIEW_REQUIRED,
    RIGHTS_AUTHORIZED_COMMUNITY,
    RIGHTS_OWN_CHANNEL,
    RIGHTS_PUBLIC_THIRD_PARTY,
    RIGHTS_USER_UPLOAD,
    STATUS_APPROVED,
)


def parse_json_field(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def can_auto_publish(source: dict[str, Any], target: dict[str, Any]) -> GuardResult:
    mode = target["mode"]
    rights_mode = source["permission_status"]
    evidence = source.get("permission_evidence", "").strip()

    if mode == PUBLISH_OFF:
        return GuardResult(False, "publish target is off")

    if mode == PUBLISH_EXPORT_ONLY:
        return GuardResult(False, "target is export-only")

    if mode == PUBLISH_REVIEW_REQUIRED:
        return GuardResult(False, "target requires manual approval")

    if mode != PUBLISH_AUTO:
        return GuardResult(False, f"unsupported publish mode: {mode}")

    if rights_mode in {RIGHTS_AUTHORIZED_COMMUNITY, RIGHTS_OWN_CHANNEL, RIGHTS_USER_UPLOAD, RIGHTS_PUBLIC_THIRD_PARTY}:
        return GuardResult(True, "auto-publish allowed")

    return GuardResult(False, f"unsupported rights mode: {rights_mode}")


def can_publish_candidate(
    source: dict[str, Any],
    target: dict[str, Any],
    candidate: dict[str, Any],
) -> GuardResult:
    mode = target["mode"]

    if mode == PUBLISH_OFF:
        return GuardResult(False, "publish target is off")

    if mode == PUBLISH_EXPORT_ONLY:
        return GuardResult(False, "target is export-only")

    approved_statuses = {STATUS_APPROVED, "scheduled", "ready_to_publish", "publishing"}
    if target.get("require_approval") and candidate["status"] not in approved_statuses:
        return GuardResult(False, "candidate must be approved first")

    if mode == PUBLISH_AUTO:
        return can_auto_publish(source, target)

    if mode == PUBLISH_REVIEW_REQUIRED and candidate["status"] in approved_statuses:
        return GuardResult(True, "approved candidate can publish")

    return GuardResult(False, f"unsupported publish mode: {mode}")
