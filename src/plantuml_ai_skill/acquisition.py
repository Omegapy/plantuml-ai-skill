"""Acquisition adapters and fixture manifest generation."""

from __future__ import annotations

from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable
import urllib.request

from .config import SourceDefinition, load_sources_config
from .constants import PLANTUML_VERSION, PROJECT_ROOT
from .extraction import ExtractedDiagram, extract_from_tree
from .license_policy import license_family
from .manifest import CorpusRecord, write_jsonl


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)


def records_from_diagrams(
    diagrams: Iterable[ExtractedDiagram],
    source_name: str,
    source_url: str,
    source_kind: str,
    source_ref: str,
    license_text: str,
    purpose: list[str],
    root: Path,
    attribution: str = "",
    license_path: str = "",
    source_commit: str = "",
    source_repo_url: str = "",
) -> list[CorpusRecord]:
    family = license_family(license_text)
    records: list[CorpusRecord] = []
    for diagram in diagrams:
        puml_path = str(diagram.path.relative_to(root)) if diagram.path.is_relative_to(root) else str(diagram.path)
        render_path = ""
        if diagram.published_render_path:
            render_path = (
                str(diagram.published_render_path.relative_to(root))
                if diagram.published_render_path.is_relative_to(root)
                else str(diagram.published_render_path)
            )
        records.append(
            CorpusRecord(
                id=diagram.id,
                source_name=source_name,
                source_url=source_url,
                source_kind=source_kind,
                source_ref=source_ref,
                license=license_text,
                license_family=family,
                diagram_type=diagram.diagram_type,
                puml_path=puml_path,
                published_render_path=render_path,
                python_source_paths=[],
                include_deps=diagram.include_deps,
                is_self_contained=diagram.is_self_contained,
                uses_include=bool(diagram.include_deps),
                uses_icon_library=diagram.uses_icon_library,
                plantuml_version=PLANTUML_VERSION,
                graphviz_version="",
                render_status="not_rendered",
                render_hash_svg="",
                render_hash_png="",
                verification_status="not_verified",
                render_fail_reason="",
                purpose=purpose,
                attribution=attribution or source_name,
                license_path=license_path,
                source_commit=source_commit,
                source_repo_url=source_repo_url or source_url,
                extra={"block_index": diagram.block_index},
            )
        )
    return records


def acquire_fixtures(
    fixture_root: Path | str = PROJECT_ROOT / "tests" / "fixtures",
    output_path: Path | str = PROJECT_ROOT / "data" / "manifests" / "fixtures.jsonl",
) -> list[CorpusRecord]:
    root = Path(fixture_root)
    plantuml_root = root / "plantuml"
    diagrams = extract_from_tree(plantuml_root, source_name="fixtures")
    records = records_from_diagrams(
        diagrams,
        source_name="fixtures",
        source_url=str(plantuml_root),
        source_kind="local_fixtures",
        source_ref="local",
        license_text="MIT",
        purpose=["training", "gold_eval", "renderer_regression"],
        root=root,
        attribution="PlantUML AI Skill test fixtures",
        license_path="",
        source_commit="local",
        source_repo_url=str(root),
    )
    records.extend(_python_source_records(root))
    write_jsonl(records, output_path)
    return records


def _python_source_records(root: Path) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    for expected_path in sorted((root / "python_source").glob("*.expected.puml")):
        source_path = expected_path.with_suffix("").with_suffix(".py")
        puml_text = expected_path.read_text(encoding="utf-8")
        diagram = extract_from_tree(expected_path.parent, source_name="fixtures")
        matching = [item for item in diagram if item.path.name == expected_path.name]
        diagram_type = matching[0].diagram_type if matching else "class"
        records.append(
            CorpusRecord(
                id=f"fixtures-python-{expected_path.stem.replace('.expected', '')}",
                source_name="fixtures",
                source_url=str(root / "python_source"),
                source_kind="python_source_fixture",
                source_ref="local",
                license="MIT",
                license_family="permissive",
                diagram_type=diagram_type,
                puml_path=str(expected_path.relative_to(root)),
                published_render_path="",
                python_source_paths=[str(source_path.relative_to(root))],
                include_deps=[],
                is_self_contained=True,
                uses_include=False,
                uses_icon_library=False,
                plantuml_version=PLANTUML_VERSION,
                graphviz_version="",
                render_status="not_rendered",
                render_hash_svg="",
                render_hash_png="",
                verification_status="not_verified",
                render_fail_reason="",
                purpose=["source_conditioned_eval", "gold_eval"],
                attribution="PlantUML AI Skill test fixtures",
                license_path="",
                source_commit="local",
                source_repo_url=str(root),
            )
        )
        _ = puml_text
    return records


def acquire_source(
    source_id: str,
    output_path: Path | str,
    dry_run: bool = False,
    raw_dir: Path | str = PROJECT_ROOT / "data" / "raw",
) -> list[CorpusRecord]:
    """Acquire one configured source.

    External acquisition is intentionally conservative: git sources can be
    cloned, docs pages can be fetched from declared seed URLs, and dataset
    sources require explicit manual staging because their licensing terms need
    per-file review before training use.
    """

    if source_id == "fixtures":
        return acquire_fixtures(output_path=output_path)
    config = load_sources_config()
    source = next((item for item in config.sources if item.id == source_id), None)
    if not source:
        raise ValueError(f"unknown source: {source_id}")
    if dry_run:
        write_jsonl([], output_path)
        return []
    staged_root = _stage_source(source, Path(raw_dir))
    source_commit = _git_commit(staged_root) if (staged_root / ".git").exists() else source.ref
    license_path = _find_license_file(staged_root)
    diagrams = extract_from_tree(staged_root, source_name=source.id)
    records = records_from_diagrams(
        diagrams,
        source_name=source.id,
        source_url=source.url,
        source_kind=source.kind,
        source_ref=source.ref,
        license_text=_license_from_policy(source),
        purpose=source.default_purpose,
        root=staged_root,
        attribution=source.name,
        license_path=str(license_path.relative_to(staged_root)) if license_path else "",
        source_commit=source_commit,
        source_repo_url=source.url,
    )
    if source.id == "py2puml":
        _attach_py2puml_python_sources(records, staged_root)
    write_jsonl(records, output_path)
    return records


def _stage_source(source: SourceDefinition, raw_dir: Path) -> Path:
    destination = raw_dir / source.id
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.acquisition_mode == "git":
        if destination.exists():
            subprocess.run(["git", "-C", str(destination), "fetch", "--tags"], check=False)
        else:
            command = ["git", "clone"]
            if not _looks_like_commit(source.ref):
                command.extend(["--depth", "1"])
            if source.ref and source.pin_strategy in {"tag", "branch"}:
                command.extend(["--branch", source.ref])
            command.extend([source.url, str(destination)])
            subprocess.run(command, check=True)
        if source.ref:
            subprocess.run(["git", "-C", str(destination), "checkout", "--detach", source.ref], check=True)
        return destination
    if source.acquisition_mode == "docs_crawl":
        destination.mkdir(parents=True, exist_ok=True)
        for index, url in enumerate(source.seed_urls):
            target = destination / f"page-{index + 1}.html"
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
        return destination
    if source.acquisition_mode in {"manual_dataset", "huggingface_dataset"}:
        raise RuntimeError(
            f"{source.id} must be staged manually under {destination} after license review."
        )
    if source.acquisition_mode == "local":
        return Path(source.url)
    raise RuntimeError(f"unsupported acquisition mode: {source.acquisition_mode}")


def _license_from_policy(source: SourceDefinition) -> str:
    if source.license_policy.startswith("permissive:"):
        return source.license_policy.split(":", 1)[1]
    if "mit" in source.license_policy.lower():
        return "MIT"
    if "apache" in source.license_policy.lower():
        return "Apache-2.0"
    if "mixed" in source.license_policy.lower():
        return "Original repo licenses retained"
    return "verify-on-clone"


def _looks_like_commit(ref: str) -> bool:
    return bool(ref and COMMIT_RE.match(ref))


def _git_commit(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", errors="replace").strip()


def _find_license_file(root: Path) -> Path | None:
    candidates = []
    for pattern in ("LICENSE", "LICENSE.*", "COPYING", "COPYING.*", "NOTICE", "NOTICE.*"):
        candidates.extend(root.glob(pattern))
    return sorted((path for path in candidates if path.is_file()), key=lambda path: path.name.lower())[0] if candidates else None


def _attach_py2puml_python_sources(records: list[CorpusRecord], staged_root: Path) -> None:
    for record in records:
        puml_path = staged_root / record.puml_path
        python_sources = python_sources_for_expected_puml(puml_path, staged_root)
        if python_sources:
            record.python_source_paths = [str(path.relative_to(staged_root)) for path in python_sources]
            if "source_conditioned_eval" not in record.purpose:
                record.purpose.append("source_conditioned_eval")
        elif "source_conditioned_eval" in record.purpose:
            record.purpose = [purpose for purpose in record.purpose if purpose != "source_conditioned_eval"]


def python_sources_for_expected_puml(puml_path: Path, staged_root: Path) -> list[Path]:
    """Heuristically pair py2puml expected .puml files with Python sources."""

    if not puml_path.exists() or puml_path.suffix.lower() not in {".puml", ".plantuml", ".iuml"}:
        return []
    same_stem = puml_path.with_suffix(".py")
    if same_stem.exists():
        return [same_stem]
    parent = puml_path.parent
    candidates = sorted(
        path
        for path in parent.rglob("*.py")
        if path.name != "__init__.py" and ".git" not in path.parts
    )
    if candidates:
        return candidates
    init_file = parent / "__init__.py"
    if init_file.exists():
        return [init_file]
    if puml_path.name == "py2puml.domain.puml":
        domain_root = staged_root / "src" / "py2puml" / "domain"
        return sorted(domain_root.glob("*.py")) if domain_root.exists() else []
    return []


def ensure_generated_dirs() -> None:
    for path in (
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "data" / "rendered",
        PROJECT_ROOT / "data" / "manifests",
        PROJECT_ROOT / "data" / "reports",
    ):
        path.mkdir(parents=True, exist_ok=True)


def reset_generated_dirs() -> None:
    for path in (
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "data" / "rendered",
        PROJECT_ROOT / "data" / "manifests",
        PROJECT_ROOT / "data" / "reports",
    ):
        if path.exists():
            shutil.rmtree(path)
