"""License-family classification and split eligibility."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from .constants import (
    COPYLEFT_LICENSES,
    DEFAULT_LICENSE_OVERRIDES_PATH,
    PERMISSIVE_LICENSES,
    WEAK_COPYLEFT_LICENSES,
)


@dataclass(frozen=True)
class LicenseOverride:
    """A reviewed repository-level license decision."""

    license: str
    license_path: str = ""
    notes: str = ""


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


def training_block_reason(license_text: str, purpose: list[str]) -> str:
    if "training" not in purpose:
        return "not_marked_for_training"
    family = license_family(license_text)
    if family == "permissive":
        return ""
    return f"blocked_{family}_license"


def load_license_overrides(
    path: Path | str = DEFAULT_LICENSE_OVERRIDES_PATH,
) -> dict[str, LicenseOverride]:
    """Load reviewed per-repository license decisions.

    The file is named ``.yml`` for operator familiarity, but like
    ``config/sources.yml`` it is JSON-valid YAML and intentionally parsed with
    the standard library.
    """

    override_path = Path(path)
    if not override_path.exists():
        return {}
    payload = json.loads(override_path.read_text(encoding="utf-8"))
    repositories = payload.get("repositories", {})
    if not isinstance(repositories, dict):
        raise ValueError(f"{override_path}: repositories must be an object")
    overrides: dict[str, LicenseOverride] = {}
    for repo_name, value in repositories.items():
        normalized_repo = normalize_repo_name(str(repo_name))
        if isinstance(value, str):
            overrides[normalized_repo] = LicenseOverride(license=value)
            continue
        if not isinstance(value, dict):
            raise ValueError(f"{override_path}: override for {repo_name!r} must be a string or object")
        overrides[normalized_repo] = _license_override_from_mapping(value, override_path, repo_name)
    return overrides


def license_override_for_repo(
    repo_name: str,
    overrides: dict[str, LicenseOverride],
) -> LicenseOverride | None:
    return overrides.get(normalize_repo_name(repo_name))


def normalize_repo_name(value: str) -> str:
    return value.strip().lower()


def _license_override_from_mapping(
    data: dict[str, Any],
    path: Path,
    repo_name: object,
) -> LicenseOverride:
    license_text = str(data.get("license", "")).strip()
    if not license_text:
        raise ValueError(f"{path}: override for {repo_name!r} is missing license")
    return LicenseOverride(
        license=license_text,
        license_path=str(data.get("license_path", "")),
        notes=str(data.get("notes", "")),
    )
