"""PlantUML block extraction and lightweight diagram classification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import unquote

from .includes import parse_include_deps, uses_c4, uses_icon_library


PLANTUML_BLOCK_RE = re.compile(
    r"(?is)(@start(?P<kind>[A-Za-z0-9_ -]*)\b.*?@end(?P=kind)\b)"
)
FENCE_RE = re.compile(r"(?is)```(?:plantuml|puml|uml)\s+(?P<body>.*?)```")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?P<target>[^)\s]+)(?:\s+['\"][^)]*['\"])?\)")
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
    published_render_pairing_status: str = ""


@dataclass(frozen=True)
class PlantUMLBlock:
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class MarkdownImageReference:
    path: Path
    start: int
    end: int


def stable_id(source_name: str, path: Path, text: str) -> str:
    digest = hashlib.sha1(f"{path.as_posix()}\n{text}".encode("utf-8")).hexdigest()[:12]
    safe_source = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")
    safe_stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-") or "diagram"
    return f"{safe_source}-{safe_stem}-{digest}"


def extract_plantuml_blocks(text: str) -> list[str]:
    """Extract PlantUML documents from raw text or fenced Markdown."""

    documents = extract_plantuml_documents(text)
    if documents:
        return [document.text for document in documents]
    return []


def extract_plantuml_documents(text: str) -> list[PlantUMLBlock]:
    """Extract PlantUML documents and their source offsets."""

    blocks = [
        PlantUMLBlock(match.group(1).strip(), match.start(1), match.end(1))
        for match in PLANTUML_BLOCK_RE.finditer(text)
    ]
    if blocks:
        return blocks
    fenced_blocks: list[PlantUMLBlock] = []
    for match in FENCE_RE.finditer(text):
        body = match.group("body").strip()
        if body.lower().startswith("@start"):
            fenced_blocks.append(PlantUMLBlock(body, match.start("body"), match.end("body")))
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
    if re.search(r"^\s*state\s+\w+", puml_text, re.MULTILINE):
        return "state"
    if re.search(r"^\s*(?:\[\*\]\s*[-.]+>|\w+\s*[-.]+>\s*\[\*\])", puml_text, re.MULTILINE):
        return "state"
    if re.search(r"^\s*(component|node|cloud)\s+", puml_text, re.MULTILINE):
        return "component"
    if re.search(r"^\s*\[[^\]]+\](?:\s+as\s+\w+)?", puml_text, re.IGNORECASE | re.MULTILINE):
        return "component"
    if re.search(r"^\s*usecase\s+", puml_text, re.IGNORECASE | re.MULTILINE):
        return "usecase"
    if re.search(r"[-.]+[ox*]?>|<[-.]+", puml_text):
        return "sequence"
    if re.search(r"^\s*(actor|database)\s+", puml_text, re.MULTILINE):
        return "usecase" if re.search(r"^\s*actor\s+", puml_text, re.MULTILINE) else "component"
    if re.search(r"^\s*:\s*[^;]+;", puml_text, re.MULTILINE):
        return "activity"
    return "uml"


def find_same_basename_render(path: Path) -> Path | None:
    for suffix in RENDER_SUFFIXES:
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def markdown_render_paths_by_block(path: Path, text: str, blocks: list[PlantUMLBlock]) -> dict[int, tuple[Path | None, str]]:
    """Pair Markdown PlantUML blocks with nearby local image references.

    Markdown files often contain multiple PlantUML examples and multiple PNGs.
    Pairing every block to ``file.png`` creates false mismatches, so references
    are claimed by adjacency: prefer the single image after a block before the
    next block, then the single unclaimed image before a block.
    """

    pairings: dict[int, tuple[Path | None, str]] = {index: (None, "") for index in range(len(blocks))}
    if not blocks or path.suffix.lower() not in {".md", ".markdown"}:
        return pairings

    images = _markdown_image_references(path, text)
    if not images:
        if len(blocks) == 1:
            same_basename = find_same_basename_render(path)
            if same_basename:
                pairings[0] = (same_basename, "same_basename")
        return pairings

    claimed: set[Path] = set()
    for index, block in enumerate(blocks):
        next_start = blocks[index + 1].start if index + 1 < len(blocks) else len(text)
        following = [image for image in images if block.end <= image.start < next_start]
        if len(following) == 1:
            pairings[index] = (following[0].path, "markdown_adjacent_after")
            claimed.add(following[0].path)
        elif len(following) > 1:
            pairings[index] = (None, "ambiguous_markdown_reference")

    for index, block in enumerate(blocks):
        if pairings[index][0] is not None:
            continue
        prev_end = blocks[index - 1].end if index > 0 else 0
        preceding = [
            image
            for image in images
            if prev_end <= image.end <= block.start and image.path not in claimed
        ]
        if len(preceding) == 1:
            pairings[index] = (preceding[0].path, "markdown_adjacent_before")
            claimed.add(preceding[0].path)
        elif len(preceding) > 1:
            pairings[index] = (None, "ambiguous_markdown_reference")

    return pairings


def extract_from_file(path: Path, source_name: str) -> list[ExtractedDiagram]:
    text = path.read_text(encoding="utf-8", errors="replace")
    documents = extract_plantuml_documents(text)
    if not documents and path.suffix.lower() in {".puml", ".plantuml", ".iuml"}:
        documents = [PlantUMLBlock(text.strip(), 0, len(text))]
    render_pairings = markdown_render_paths_by_block(path, text, documents)
    diagrams: list[ExtractedDiagram] = []
    for index, document in enumerate(documents):
        block = document.text
        include_deps = parse_include_deps(block)
        render_path, pairing_status = render_pairings.get(index, (None, ""))
        if render_path is None and path.suffix.lower() not in {".md", ".markdown"}:
            render_path = find_same_basename_render(path)
            pairing_status = "same_basename" if render_path else ""
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
                published_render_pairing_status=pairing_status,
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


def _markdown_image_references(path: Path, text: str) -> list[MarkdownImageReference]:
    references: list[MarkdownImageReference] = []
    for match in MARKDOWN_IMAGE_RE.finditer(text):
        target = unquote(match.group("target")).split("#", 1)[0].split("?", 1)[0]
        if not target or re.match(r"(?i)^[a-z][a-z0-9+.-]*:", target):
            continue
        candidate = (path.parent / target).resolve()
        if candidate.suffix.lower() not in RENDER_SUFFIXES or not candidate.exists():
            continue
        references.append(MarkdownImageReference(candidate, match.start(), match.end()))
    return references
