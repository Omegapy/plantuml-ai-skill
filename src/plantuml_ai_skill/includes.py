"""PlantUML include parsing and dependency classification."""

from __future__ import annotations

import re


INCLUDE_RE = re.compile(
    r"^\s*!(?:include|includeurl|include_many|include_once)\s+(?P<target>\S+)",
    re.IGNORECASE | re.MULTILINE,
)

ICON_LIBRARY_HINTS = ("aws", "azure", "gcp", "k8s", "kubernetes", "material", "font-awesome")
C4_HINTS = ("c4_", "c4-", "c4/")


def parse_include_deps(puml_text: str) -> list[str]:
    """Return raw include targets from a PlantUML document."""

    includes: list[str] = []
    for match in INCLUDE_RE.finditer(puml_text):
        target = match.group("target").strip().strip('"').strip("'")
        if target and not target.startswith("'"):
            includes.append(target)
    return includes


def uses_icon_library(include_deps: list[str], puml_text: str = "") -> bool:
    haystack = " ".join(include_deps + [puml_text]).lower()
    return any(hint in haystack for hint in ICON_LIBRARY_HINTS)


def uses_c4(include_deps: list[str], puml_text: str = "") -> bool:
    haystack = " ".join(include_deps + [puml_text]).lower()
    return any(hint in haystack for hint in C4_HINTS) or "system_boundary" in haystack


def is_remote_include(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def unresolved_include_reason(include_deps: list[str], vendored_roots: list[str]) -> str:
    """Summarize why a diagram cannot be treated as self-contained."""

    if not include_deps:
        return ""
    if any(is_remote_include(dep) for dep in include_deps):
        return "remote_include_blocked"
    if not vendored_roots:
        return "include_roots_not_configured"
    return "include_resolution_required"
