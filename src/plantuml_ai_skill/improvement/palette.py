"""AEther Flow PlantUML palette contract helpers."""

from __future__ import annotations

import html
import re


PALETTE_POLICY_NONE = "none"
PALETTE_POLICY_AETHER_DARK_REQUIRED = "aether_dark_required"
PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED = "aether_dark_rendered_required"
PALETTE_POLICY_ALIASES = {
    "": PALETTE_POLICY_NONE,
    "none": PALETTE_POLICY_NONE,
    "aether-dark": PALETTE_POLICY_AETHER_DARK_REQUIRED,
    "aether_dark_required": PALETTE_POLICY_AETHER_DARK_REQUIRED,
    "aether-dark-rendered": PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED,
    "aether_dark_rendered_required": PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED,
}

CERTIFIED_AETHER_DARK_DIAGRAM_TYPES = frozenset(
    {"sequence", "class", "activity", "state", "component", "usecase", "c4"}
)
UNCERTIFIED_AETHER_DARK_DIAGRAM_TYPES = frozenset(
    {"deployment", "gantt", "mindmap", "object", "timing", "wbs"}
)
KNOWN_AETHER_DARK_DIAGRAM_TYPES = CERTIFIED_AETHER_DARK_DIAGRAM_TYPES | UNCERTIFIED_AETHER_DARK_DIAGRAM_TYPES

AETHER_DARK_ALLOWED_COLORS = frozenset(
    {
        "#000000",
        "#050403",
        "#080401",
        "#fff8ef",
        "#d6c3b4",
        "#0f364d",
        "#164964",
        "#2d7ea0",
        "#48a0c0",
        "#270b01",
        "#702000",
        "#f87800",
        "#f4d6a1",
        "#ffffff",
    }
)
AETHER_DARK_REQUIRED_COLORS = frozenset({"#000000", "#050403", "#fff8ef", "#d6c3b4"})
AETHER_DARK_RENDERED_EXCEPTION_COLORS = frozenset()
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b")
C4_CONTAINER_INCLUDE = "!include <C4/C4_Container.puml>"

AETHER_DARK_BASE_STYLE_BLOCK = """skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
skinparam ArrowHeadColor #d6c3b4
skinparam ArrowThickness 2
skinparam DefaultTextAlignment center
skinparam ParticipantBackgroundColor #050403
skinparam ParticipantBorderColor #d6c3b4
skinparam ParticipantFontColor #fff8ef
skinparam ActorBackgroundColor #0f364d
skinparam ActorBorderColor #d6c3b4
skinparam ActorFontColor #fff8ef
skinparam DatabaseBackgroundColor #080401
skinparam DatabaseBorderColor #f4d6a1
skinparam DatabaseFontColor #fff8ef
skinparam ClassBackgroundColor #050403
skinparam ClassBorderColor #d6c3b4
skinparam ClassFontColor #fff8ef
skinparam ComponentBackgroundColor #050403
skinparam ComponentBorderColor #d6c3b4
skinparam ComponentFontColor #fff8ef
skinparam ActivityBackgroundColor #050403
skinparam ActivityBorderColor #d6c3b4
skinparam ActivityFontColor #fff8ef
skinparam StateBackgroundColor #050403
skinparam StateBorderColor #d6c3b4
skinparam StateFontColor #fff8ef
skinparam UsecaseBackgroundColor #050403
skinparam UsecaseBorderColor #d6c3b4
skinparam UsecaseFontColor #fff8ef
skinparam NoteBackgroundColor #080401
skinparam NoteBorderColor #f4d6a1
skinparam NoteFontColor #fff8ef
skinparam PackageBackgroundColor #080401
skinparam PackageBorderColor #d6c3b4
skinparam PackageFontColor #fff8ef"""

_AETHER_DARK_SEQUENCE_OVERLAY = """skinparam SequenceLifeLineBorderColor #d6c3b4
skinparam SequenceLifeLineBorderThickness 1
skinparam SequenceArrowThickness 2"""

_AETHER_DARK_CLASS_OVERLAY = """hide circle
skinparam ClassAttributeFontColor #fff8ef
skinparam ClassStereotypeFontColor #fff8ef"""

_AETHER_DARK_ACTIVITY_OVERLAY = """skinparam ActivityDiamondFontColor #fff8ef
skinparam ActivityBorderThickness 1"""

_AETHER_DARK_STATE_OVERLAY = """skinparam StateAttributeFontColor #fff8ef"""

_AETHER_DARK_COMPONENT_OVERLAY = """skinparam ComponentBorderThickness 1"""

_AETHER_DARK_USECASE_OVERLAY = """skinparam UsecaseBorderThickness 1"""

AETHER_DARK_C4_STYLE_BLOCK = """skinparam backgroundColor #000000
skinparam shadowing false
skinparam defaultFontName Inter
skinparam defaultFontColor #fff8ef
skinparam ArrowColor #d6c3b4
skinparam ArrowFontColor #fff8ef
UpdateElementStyle("person", $bgColor="#0f364d", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_person", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("system", $bgColor="#050403", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_system", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("container", $bgColor="#050403", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateElementStyle("external_container", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#f4d6a1")
UpdateElementStyle("boundary", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateRelStyle($textColor="#fff8ef", $lineColor="#d6c3b4")
UpdateBoundaryStyle("system", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateBoundaryStyle("container", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
UpdateBoundaryStyle("", $bgColor="#080401", $fontColor="#fff8ef", $borderColor="#d6c3b4")
AddRelTag("risk", $textColor="#fff8ef", $lineColor="#f87800", $lineStyle=DashedLine())"""

_FAMILY_OVERLAYS = {
    "sequence": _AETHER_DARK_SEQUENCE_OVERLAY,
    "class": _AETHER_DARK_CLASS_OVERLAY,
    "activity": _AETHER_DARK_ACTIVITY_OVERLAY,
    "state": _AETHER_DARK_STATE_OVERLAY,
    "component": _AETHER_DARK_COMPONENT_OVERLAY,
    "usecase": _AETHER_DARK_USECASE_OVERLAY,
}

# Backward-compatible default for callers that have not yet selected a family.
AETHER_DARK_STYLE_BLOCK = "\n".join([AETHER_DARK_BASE_STYLE_BLOCK, _AETHER_DARK_SEQUENCE_OVERLAY])

AETHER_DARK_FORBIDDEN_RENDERED_TEXTS = (
    "Please use '!option handwritten true' to enable handwritten",
    "Syntax Error?",
    "Function not found",
)

AETHER_DARK_TEXT_CONTRAST_PAIRS = (
    ("#fff8ef", "#050403", 4.5),
    ("#fff8ef", "#080401", 4.5),
    ("#fff8ef", "#0f364d", 4.5),
    ("#fff8ef", "#270b01", 4.5),
)
AETHER_DARK_LINE_CONTRAST_PAIRS = (
    ("#d6c3b4", "#000000", 3.0),
    ("#d6c3b4", "#050403", 3.0),
    ("#d6c3b4", "#080401", 3.0),
    ("#d6c3b4", "#0f364d", 7.0),
)
AETHER_DARK_ACCENT_CONTRAST_PAIRS = tuple(
    (accent, background, 3.0)
    for accent in ("#48a0c0", "#f4d6a1", "#f87800")
    for background in ("#000000", "#050403", "#080401")
)


def normalize_palette_policy(value: str | None) -> str:
    normalized = PALETTE_POLICY_ALIASES.get((value or "").strip().lower())
    if normalized is None:
        raise ValueError(f"unknown palette_policy: {value}")
    return normalized


def aether_dark_style_block(diagram_type: str | None) -> str:
    """Return the complete AEther dark style block for a PlantUML family."""

    normalized = _normalize_diagram_type(diagram_type)
    if normalized not in KNOWN_AETHER_DARK_DIAGRAM_TYPES:
        known = ", ".join(sorted(KNOWN_AETHER_DARK_DIAGRAM_TYPES))
        raise ValueError(f"unknown AEther dark diagram_type: {diagram_type!r}; known types: {known}")
    if normalized == "c4":
        return AETHER_DARK_C4_STYLE_BLOCK
    overlay = _FAMILY_OVERLAYS.get(normalized, "")
    return "\n".join(part for part in (AETHER_DARK_BASE_STYLE_BLOCK, overlay) if part)


def palette_policy_for_diagram_type(diagram_type: str | None) -> str:
    normalized = _normalize_diagram_type(diagram_type)
    if normalized in CERTIFIED_AETHER_DARK_DIAGRAM_TYPES:
        return PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED
    return PALETTE_POLICY_AETHER_DARK_REQUIRED


def hex_colors(text: str) -> set[str]:
    return {match.group(0).lower() for match in HEX_COLOR_RE.finditer(text)}


def aether_dark_palette_issues(text: str) -> tuple[list[str], list[str]]:
    colors = hex_colors(text)
    missing = sorted(AETHER_DARK_REQUIRED_COLORS - colors)
    unapproved = sorted(colors - AETHER_DARK_ALLOWED_COLORS)
    return missing, unapproved


def aether_dark_rendered_palette_issues(
    svg: str | bytes,
    puml: str = "",
    diagram_type: str = "",
) -> dict[str, object]:
    text = svg.decode("utf-8", errors="replace") if isinstance(svg, bytes) else svg
    colors = hex_colors(text)
    allowed = AETHER_DARK_ALLOWED_COLORS | AETHER_DARK_RENDERED_EXCEPTION_COLORS
    normalized_text = _normalized_rendered_text(text)
    forbidden_texts = [
        item for item in AETHER_DARK_FORBIDDEN_RENDERED_TEXTS if item.lower() in normalized_text.lower()
    ]
    required_colors = _required_rendered_colors(puml, diagram_type)
    contrast_failures = aether_dark_contrast_failures()
    return {
        "forbidden_texts": forbidden_texts,
        "missing_role_colors": sorted(required_colors - colors),
        "unapproved_colors": sorted(colors - allowed),
        "contrast_failures": contrast_failures,
    }


def has_rendered_palette_issues(issues: dict[str, object]) -> bool:
    return any(bool(value) for value in issues.values())


def aether_dark_contrast_failures() -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    for foreground, background, minimum in (
        AETHER_DARK_TEXT_CONTRAST_PAIRS + AETHER_DARK_LINE_CONTRAST_PAIRS + AETHER_DARK_ACCENT_CONTRAST_PAIRS
    ):
        ratio = contrast_ratio(foreground, background)
        if ratio < minimum:
            failures.append(
                {
                    "foreground": foreground,
                    "background": background,
                    "ratio": round(ratio, 2),
                    "minimum": minimum,
                }
            )
    return failures


def contrast_ratio(foreground: str, background: str) -> float:
    fore = _relative_luminance(foreground)
    back = _relative_luminance(background)
    lighter = max(fore, back)
    darker = min(fore, back)
    return (lighter + 0.05) / (darker + 0.05)


def _required_rendered_colors(puml: str, diagram_type: str) -> set[str]:
    required = set(AETHER_DARK_REQUIRED_COLORS)
    source = puml.lower()
    normalized_type = _normalize_diagram_type(diagram_type)
    if normalized_type in {"usecase", "c4"} or re.search(r"(?m)^\s*actor\b", source) or "person(" in source:
        required.update({"#0f364d", "#d6c3b4"})
    if re.search(r"(?m)^\s*database\b", source) or "note " in source:
        required.update({"#080401", "#f4d6a1"})
    if "#f87800" in source or "$tags=\"risk\"" in source or "$tags='risk'" in source:
        required.add("#f87800")
    return required


def _relative_luminance(color: str) -> float:
    value = color.lstrip("#")
    red, green, blue = (int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
    return 0.2126 * _linear_channel(red) + 0.7152 * _linear_channel(green) + 0.0722 * _linear_channel(blue)


def _linear_channel(value: float) -> float:
    if value <= 0.03928:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _normalized_rendered_text(text: str) -> str:
    return " ".join(html.unescape(text).replace("\xa0", " ").split())


def _normalize_diagram_type(diagram_type: str | None) -> str:
    return (diagram_type or "").strip().lower().replace("-", "_")
