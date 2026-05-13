"""PlantUML block extraction and lightweight diagram classification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Iterable

from .includes import parse_include_deps, uses_c4, uses_icon_library


PLANTUML_BLOCK_RE = re.compile(
    r"(?is)(@start(?P<kind>[A-Za-z0-9_ -]*)\b.*?@end(?P=kind)\b)"
)
FENCE_RE = re.compile(r"(?is)```(?:plantuml|puml|uml)\s+(?P<body>.*?)```")
SUPPORTED_TEXT_SUFFIXES = {".puml", ".plantuml", ".iuml", ".md", ".markdown", ".txt"}
RENDER_SUFFIXES = (".svg", ".png")


@dataclass(frozen=True)
class ExtractedDiagram:
    id: str
    path: Path
    text: str
    diagram_type: str
    published_render_path: Path | None
    include_deps: list[str]
    is_self_contained: bool
    uses_icon_library: bool
    block_index: int = 0


def stable_id(source_name: str, path: Path, text: str) -> str:
    digest = hashlib.sha1(f"{path.as_posix()}\n{text}".encode("utf-8")).hexdigest()[:12]
    safe_source = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")
    safe_stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-") or "diagram"
    return f"{safe_source}-{safe_stem}-{digest}"


def extract_plantuml_blocks(text: str) -> list[str]:
    """Extract PlantUML documents from raw text or fenced Markdown."""

    blocks = [match.group(1).strip() for match in PLANTUML_BLOCK_RE.finditer(text)]
    if blocks:
        return blocks
    fenced_blocks: list[str] = []
    for match in FENCE_RE.finditer(text):
        body = match.group("body").strip()
        if body.lower().startswith("@start"):
            fenced_blocks.append(body)
    return fenced_blocks


def classify_diagram_type(puml_text: str) -> str:
    lowered = puml_text.lower()
    first_start = re.search(r"@start([a-z0-9_ -]*)\b", lowered)
    start_kind = first_start.group(1).strip() if first_start else "uml"
    includes = parse_include_deps(puml_text)
    if uses_c4(includes, puml_text):
        return "c4"
    if start_kind and start_kind != "uml":
        return start_kind.replace(" ", "_")
    if re.search(r"^\s*(class|interface|enum|abstract\s+class)\s+\w+", puml_text, re.MULTILINE):
        return "class"
    if re.search(r"^\s*(actor|usecase)\s+", puml_text, re.MULTILINE):
        return "usecase"
    if re.search(r"[-.]+[ox*]?>|<[-.]+", puml_text):
        return "sequence"
    if re.search(r"^\s*(component|node|database|cloud)\s+", puml_text, re.MULTILINE):
        return "component"
    if re.search(r"^\s*state\s+\w+", puml_text, re.MULTILINE):
        return "state"
    if re.search(r"^\s*:\s*[^;]+;", puml_text, re.MULTILINE):
        return "activity"
    return "uml"


def find_same_basename_render(path: Path) -> Path | None:
    for suffix in RENDER_SUFFIXES:
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def extract_from_file(path: Path, source_name: str) -> list[ExtractedDiagram]:
    text = path.read_text(encoding="utf-8", errors="replace")
    raw_blocks = extract_plantuml_blocks(text)
    if not raw_blocks and path.suffix.lower() in {".puml", ".plantuml", ".iuml"}:
        raw_blocks = [text.strip()]
    diagrams: list[ExtractedDiagram] = []
    for index, block in enumerate(raw_blocks):
        include_deps = parse_include_deps(block)
        render_path = find_same_basename_render(path)
        diagrams.append(
            ExtractedDiagram(
                id=stable_id(
                    source_name,
                    path if index == 0 else path.with_name(f"{path.stem}-{index + 1}{path.suffix}"),
                    block,
                ),
                path=path,
                text=block,
                diagram_type=classify_diagram_type(block),
                published_render_path=render_path,
                include_deps=include_deps,
                is_self_contained=not include_deps,
                uses_icon_library=uses_icon_library(include_deps, block),
                block_index=index,
            )
        )
    return diagrams


def iter_candidate_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_TEXT_SUFFIXES:
            yield path


def extract_from_tree(root: Path, source_name: str = "fixtures") -> list[ExtractedDiagram]:
    diagrams: list[ExtractedDiagram] = []
    for path in iter_candidate_files(root):
        diagrams.extend(extract_from_file(path, source_name))
    return diagrams
