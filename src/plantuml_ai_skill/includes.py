"""PlantUML include parsing and dependency classification."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


INCLUDE_RE = re.compile(
    r"^\s*!(?:include|includeurl|include_many|include_once)\s+(?P<target>\S+)",
    re.IGNORECASE | re.MULTILINE,
)
INCLUDE_LINE_RE = re.compile(
    r"^(?P<prefix>\s*!(?:include|include_many|include_once)\s+)(?P<quote>['\"]?)(?P<target>\S+?)(?P=quote)(?P<suffix>\s*(?:'.*)?)$",
    re.IGNORECASE,
)

ICON_LIBRARY_HINTS = ("aws", "azure", "gcp", "k8s", "kubernetes", "material", "font-awesome")
C4_HINTS = ("c4_", "c4-", "c4/")


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

    Remote includes are intentionally not resolved; batch rendering should only
    use local, auditable include trees.
    """

    roots = [Path(root) for root in include_roots]
    if source_dir:
        roots.insert(0, Path(source_dir))
    resolutions: list[IncludeResolution] = []
    for dep in include_deps:
        target = dep.strip().strip('"').strip("'")
        if is_remote_include(target):
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


def inline_resolved_includes(puml_text: str, resolutions: list[IncludeResolution]) -> str:
    """Inline resolved include files so sandboxed rendering needs no filesystem access."""

    resolved_by_target = {
        resolution.target: resolution.resolved_path
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
        target = match.group("target").strip().strip('"').strip("'")
        resolved = resolved_by_target.get(target)
        if resolved is None:
            inlined_lines.append(line)
            continue
        inlined_lines.append(f"' begin inlined include: {target}")
        inlined_lines.extend(resolved.read_text(encoding="utf-8", errors="replace").splitlines())
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


def _include_candidates(target: str, roots: list[Path]) -> list[Path]:
    target_path = Path(target)
    names = [target_path]
    if target_path.suffix == "":
        names.append(target_path.with_suffix(".puml"))
        names.append(target_path.with_suffix(".iuml"))
    if target_path.is_absolute():
        return names
    candidates: list[Path] = []
    for root in roots:
        for name in names:
            candidates.append(root / name)
    return candidates
