"""License-family classification and split eligibility."""

from __future__ import annotations

import re

from .constants import COPYLEFT_LICENSES, PERMISSIVE_LICENSES, WEAK_COPYLEFT_LICENSES


def normalize_license(value: str) -> str:
    return re.sub(r"\s+", "-", value.strip().lower())


def license_family(license_text: str) -> str:
    """Return a coarse policy family for a license string."""

    normalized = normalize_license(license_text)
    if not normalized or normalized in {"unknown", "not-clearly-stated", "verify-on-clone"}:
        return "unknown"
    if any(token in normalized for token in PERMISSIVE_LICENSES):
        return "permissive"
    if any(token in normalized for token in WEAK_COPYLEFT_LICENSES):
        return "weak_copyleft"
    if any(token in normalized for token in COPYLEFT_LICENSES):
        return "copyleft"
    if "original-repo-licenses-retained" in normalized:
        return "mixed"
    if "license" in normalized and "verify" in normalized:
        return "unknown"
    return "unknown"


def may_enter_training_split(license_text: str, purpose: list[str]) -> bool:
    """Only permissive records may enter broad training sets by default."""

    if "training" not in purpose:
        return False
    return license_family(license_text) == "permissive"
