"""PlantUML include parsing and dependency classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse


INCLUDE_RE = re.compile(
    r"^\s*!(?:include|includeurl|include_many|include_once)\s+(?P<target>\S+)",
    re.IGNORECASE | re.MULTILINE,
)
INCLUDE_LINE_RE = re.compile(
    r"^(?P<prefix>\s*!(?:include|includeurl|include_many|include_once)\s+)(?P<quote>['\"]?)(?P<target>\S+?)(?P=quote)(?P<suffix>\s*(?:'.*)?)$",
    re.IGNORECASE,
)

ICON_LIBRARY_HINTS = ("aws", "azure", "gcp", "k8s", "kubernetes", "material", "font-awesome")
C4_HINTS = ("c4_", "c4-", "c4/")
TRUSTED_C4_REMOTE_PREFIXES = (
    "/plantuml-stdlib/C4-PlantUML/master/",
    "/RicardoNiepel/C4-PlantUML/master/",
)


@dataclass(frozen=True)
class IncludeResolution:
    """Resolution result for a PlantUML include dependency."""

    target: str
    resolved_path: Path | None
    reason: str = ""


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


def resolve_include_deps(
    include_deps: list[str],
    include_roots: list[Path | str],
    source_dir: Path | str | None = None,
) -> list[IncludeResolution]:
    """Resolve includes against local source and vendor roots.

    Arbitrary remote includes are intentionally not resolved; batch rendering
    should only use local, auditable include trees. A small allowlist maps
    PlantUML-Examples' historical C4-PlantUML ``master`` URLs to the pinned
    local C4 vendor snapshot.
    """

    vendor_roots = [Path(root) for root in include_roots]
    roots = list(vendor_roots)
    if source_dir:
        roots.insert(0, Path(source_dir))
    resolutions: list[IncludeResolution] = []
    for dep in include_deps:
        target = dep.strip().strip('"').strip("'")
        if is_remote_include(target):
            trusted_remote = _trusted_remote_include_path(target, vendor_roots)
            if trusted_remote:
                resolutions.append(IncludeResolution(dep, trusted_remote.resolve(), "trusted_remote_mirrored"))
            else:
                resolutions.append(IncludeResolution(dep, None, "remote_include_blocked"))
            continue
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        candidates = _include_candidates(target, roots)
        resolved = next((candidate for candidate in candidates if candidate.exists()), None)
        if resolved:
            resolutions.append(IncludeResolution(dep, resolved.resolve()))
        else:
            resolutions.append(IncludeResolution(dep, None, "include_resolution_required"))
    return resolutions


def all_includes_resolved(
    include_deps: list[str],
    include_roots: list[Path | str],
    source_dir: Path | str | None = None,
) -> bool:
    return all(
        resolution.resolved_path is not None
        for resolution in resolve_include_deps(include_deps, include_roots, source_dir)
    )


def rewrite_includes_to_local_paths(puml_text: str, resolutions: list[IncludeResolution]) -> str:
    """Rewrite resolved include directives to absolute local paths."""

    resolved_by_target = {
        resolution.target: resolution.resolved_path
        for resolution in resolutions
        if resolution.resolved_path is not None
    }
    if not resolved_by_target:
        return puml_text
    rewritten_lines: list[str] = []
    for line in puml_text.splitlines():
        match = INCLUDE_LINE_RE.match(line)
        if not match:
            rewritten_lines.append(line)
            continue
        target = match.group("target").strip().strip('"').strip("'")
        resolved = resolved_by_target.get(target)
        if resolved is None:
            rewritten_lines.append(line)
            continue
        rewritten_lines.append(f'{match.group("prefix")}"{resolved.as_posix()}"{match.group("suffix")}')
    if puml_text.endswith("\n"):
        return "\n".join(rewritten_lines) + "\n"
    return "\n".join(rewritten_lines)


def inline_resolved_includes(
    puml_text: str,
    resolutions: list[IncludeResolution],
    _seen: set[Path] | None = None,
) -> str:
    """Inline resolved include files so sandboxed rendering needs no filesystem access."""

    seen = _seen or set()
    resolved_by_target = {
        _normalize_include_target(resolution.target): resolution.resolved_path
        for resolution in resolutions
        if resolution.resolved_path is not None
    }
    if not resolved_by_target:
        return puml_text
    inlined_lines: list[str] = []
    for line in puml_text.splitlines():
        match = INCLUDE_LINE_RE.match(line)
        if not match:
            inlined_lines.append(line)
            continue
        target = _normalize_include_target(match.group("target"))
        resolved = resolved_by_target.get(target)
        if resolved is None:
            inlined_lines.append(line)
            continue
        inlined_lines.append(f"' begin inlined include: {target}")
        if resolved in seen:
            inlined_lines.append(f"' skipped recursive include: {target}")
        else:
            include_text = resolved.read_text(encoding="utf-8", errors="replace")
            nested_resolutions = resolve_include_deps(
                parse_include_deps(include_text),
                [resolved.parent],
                resolved.parent,
            )
            include_text = inline_resolved_includes(include_text, nested_resolutions, seen | {resolved})
            inlined_lines.extend(include_text.splitlines())
        inlined_lines.append(f"' end inlined include: {target}")
    if puml_text.endswith("\n"):
        return "\n".join(inlined_lines) + "\n"
    return "\n".join(inlined_lines)


def unresolved_include_reason(
    include_deps: list[str],
    include_roots: list[Path | str],
    source_dir: Path | str | None = None,
) -> str:
    """Summarize why a diagram cannot be treated as self-contained."""

    if not include_deps:
        return ""
    if not include_roots and not source_dir:
        return "include_roots_not_configured"
    resolutions = resolve_include_deps(include_deps, include_roots, source_dir)
    unresolved = [resolution for resolution in resolutions if resolution.resolved_path is None]
    if not unresolved:
        return ""
    if any(resolution.reason == "remote_include_blocked" for resolution in unresolved):
        return "remote_include_blocked"
    return "include_resolution_required"


def unresolved_resolution_reason(resolutions: list[IncludeResolution]) -> str:
    """Summarize why a resolved dependency list still contains gaps."""

    unresolved = [resolution for resolution in resolutions if resolution.resolved_path is None]
    if not unresolved:
        return ""
    if any(resolution.reason == "remote_include_blocked" for resolution in unresolved):
        return "remote_include_blocked"
    return "include_resolution_required"


def _include_candidates(target: str, roots: list[Path]) -> list[Path]:
    target_path = Path(target)
    names = [target_path]
    if target_path.suffix == "":
        names.append(target_path.with_suffix(".puml"))
        names.append(target_path.with_suffix(".iuml"))
    names.extend(_c4_alias_names(target_path))
    names.extend(_azure_alias_names(target_path))
    if target_path.is_absolute():
        return names
    candidates: list[Path] = []
    for root in roots:
        for name in names:
            candidates.append(root / name)
    return candidates


def _normalize_include_target(target: str) -> str:
    return target.strip().strip('"').strip("'")


def _trusted_remote_include_path(target: str, roots: list[Path]) -> Path | None:
    parsed = urlparse(target)
    if parsed.scheme != "https" or parsed.netloc.lower() != "raw.githubusercontent.com":
        return None
    prefix = next((value for value in TRUSTED_C4_REMOTE_PREFIXES if parsed.path.startswith(value)), "")
    if not prefix:
        return None
    relative = parsed.path.removeprefix(prefix)
    if "/" in relative or not relative.lower().endswith((".puml", ".iuml")):
        return None
    candidates = _include_candidates(relative, roots)
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _c4_alias_names(target_path: Path) -> list[Path]:
    parts = target_path.parts
    if not parts or parts[0].lower() != "c4":
        return []
    relative = Path(*parts[1:])
    aliases = [relative]
    if relative.suffix == "":
        aliases.append(relative.with_suffix(".puml"))
        aliases.append(relative.with_suffix(".iuml"))
    return aliases


def _azure_alias_names(target_path: Path) -> list[Path]:
    parts = target_path.parts
    if len(parts) < 2 or parts[0].lower() != "azurepuml":
        return []
    relative = Path(*parts[1:])
    aliases = [relative, Path("dist") / relative]
    if relative.suffix == "":
        aliases.extend([relative.with_suffix(".puml"), relative.with_suffix(".iuml")])
        aliases.extend([Path("dist") / relative.with_suffix(".puml"), Path("dist") / relative.with_suffix(".iuml")])
    return aliases
