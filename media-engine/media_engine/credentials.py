"""Credential presence checks for local publish connectors."""

from __future__ import annotations

from typing import Any

from .credential_vault import DEFAULT_MIGRATE_PROFILE, credential_status_for_profile


def credential_status(profile_id: str | None = None) -> dict[str, Any]:
    return credential_status_for_profile(profile_id or DEFAULT_MIGRATE_PROFILE)
