"""Acquisition adapters and fixture manifest generation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable
import urllib.request
from urllib.parse import unquote, urlparse

from .config import SourceDefinition, load_sources_config
from .constants import DEFAULT_LICENSE_OVERRIDES_PATH, PLANTUML_VERSION, PROJECT_ROOT
from .extraction import ExtractedDiagram, extract_from_file, extract_from_tree, stable_id
from .license_policy import license_family, license_override_for_repo, load_license_overrides
from .manifest import CorpusRecord, write_jsonl


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
PY2PUML_ITEM_RE = re.compile(
    r"^\s*(?:abstract\s+)?(?:class|enum|interface)\s+"
    r"(?P<fqn>[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)+)",
    re.MULTILINE,
)
REPO_PLANTUML_DATASET_ID = "repo-plantuml-dataset"
SYNTHETIC_UML_DATASET_ID = "synthetic-uml-diagram-dataset"
SYNTHETIC_UML_DATASET_ROOT_NAME = "PlantUML_Data"


@dataclass(frozen=True)
class SourcePairing:
    paths: list[Path]
    confidence: str
    reason: str


@dataclass(frozen=True)
class RepoPlantUmlMetadata:
    repo_name: str
    extension: str
    puml_file_links: list[str]
    language: str
    stargazers_count: str
    forks_count: str
    open_issues_count: str
    watchers_count: str
    created_at: str
    updated_at: str
    size_kb: str


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
        extra = {"block_index": diagram.block_index}
        if diagram.published_render_pairing_status:
            extra["published_render_pairing_status"] = diagram.published_render_pairing_status
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
                extra=extra,
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
    subsets: list[str] | None = None,
    partitions: list[str] | None = None,
    max_records_per_subset: int = 0,
    acquisition_stats: dict[str, int] | None = None,
) -> list[CorpusRecord]:
    """Acquire one configured source.

    External acquisition is intentionally conservative: git sources can be
    cloned, docs pages can be fetched from declared seed URLs, and dataset
    sources require explicit manual staging because their licensing terms need
    per-file review before training use.
    """

    if source_id == "fixtures":
        _reject_synthetic_options(source_id, subsets, partitions, max_records_per_subset)
        return acquire_fixtures(output_path=output_path)
    config = load_sources_config()
    source = next((item for item in config.sources if item.id == source_id), None)
    if not source:
        raise ValueError(f"unknown source: {source_id}")
    if dry_run:
        if source.id != SYNTHETIC_UML_DATASET_ID:
            _reject_synthetic_options(source_id, subsets, partitions, max_records_per_subset)
        write_jsonl([], output_path)
        return []
    if source.id == REPO_PLANTUML_DATASET_ID:
        _reject_synthetic_options(source_id, subsets, partitions, max_records_per_subset)
        return acquire_repo_plantuml_dataset(
            source,
            Path(raw_dir) / source.id,
            output_path,
        )
    if source.id == SYNTHETIC_UML_DATASET_ID:
        return acquire_synthetic_uml_diagram_dataset(
            source,
            Path(raw_dir) / SYNTHETIC_UML_DATASET_ROOT_NAME,
            output_path,
            subsets=subsets,
            partitions=partitions,
            max_records_per_subset=max_records_per_subset,
            acquisition_stats=acquisition_stats,
        )
    _reject_synthetic_options(source_id, subsets, partitions, max_records_per_subset)
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


def acquire_synthetic_uml_diagram_dataset(
    source: SourceDefinition,
    dataset_root: Path | str,
    output_path: Path | str,
    subsets: list[str] | None = None,
    partitions: list[str] | None = None,
    max_records_per_subset: int = 0,
    acquisition_stats: dict[str, int] | None = None,
) -> list[CorpusRecord]:
    """Acquire same-stem PlantUML text and PNG pairs from a staged synthetic dataset."""

    root = Path(dataset_root)
    if not root.exists():
        raise RuntimeError(f"{source.id} must be staged under {root}")
    if max_records_per_subset < 0:
        raise ValueError("max_records_per_subset must be >= 0")

    subset_filters = {item for item in subsets or [] if item}
    partition_filters = {_normalize_partition(item) for item in partitions or [] if item}
    subset_dirs = [
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (not subset_filters or path.name in subset_filters)
    ]
    missing_subsets = subset_filters - {path.name for path in subset_dirs}
    if missing_subsets:
        raise RuntimeError(
            f"{source.id} subset(s) not found under {root}: {', '.join(sorted(missing_subsets))}"
        )

    stats = acquisition_stats if acquisition_stats is not None else {}
    records: list[CorpusRecord] = []
    stats.setdefault("paired_records", 0)
    stats.setdefault("txt_without_png", 0)
    stats.setdefault("png_without_txt", 0)
    stats.setdefault("skipped_by_cap", 0)

    for subset_dir in subset_dirs:
        subset_count = 0
        subset_png_stems = _synthetic_png_stems(subset_dir, partition_filters)
        seen_txt_stems: set[str] = set()
        for txt_path in sorted(subset_dir.rglob("*.txt")):
            relative_txt = txt_path.relative_to(subset_dir)
            if not _matches_partition(relative_txt.parent.as_posix(), partition_filters):
                continue
            relative_stem = relative_txt.with_suffix("").as_posix()
            seen_txt_stems.add(relative_stem)
            png_path = txt_path.with_suffix(".png")
            if not png_path.exists():
                stats["txt_without_png"] += 1
                continue
            if max_records_per_subset and subset_count >= max_records_per_subset:
                stats["skipped_by_cap"] += 1
                continue
            diagrams = extract_from_file(txt_path, source.id)
            paired = [diagram for diagram in diagrams if diagram.published_render_path == png_path]
            if not paired:
                stats["txt_without_png"] += 1
                continue
            for diagram in paired:
                records.append(_synthetic_record(source, root, subset_dir, txt_path, png_path, diagram))
                subset_count += 1
                stats["paired_records"] += 1
                if max_records_per_subset and subset_count >= max_records_per_subset:
                    break

        stats["png_without_txt"] += len(subset_png_stems - seen_txt_stems)

    write_jsonl(records, output_path)
    return records


def _synthetic_record(
    source: SourceDefinition,
    dataset_root: Path,
    subset_dir: Path,
    txt_path: Path,
    png_path: Path,
    diagram: ExtractedDiagram,
) -> CorpusRecord:
    relative_txt = txt_path.relative_to(dataset_root)
    relative_png = png_path.relative_to(dataset_root)
    relative_to_subset = txt_path.relative_to(subset_dir)
    partition = relative_to_subset.parent.as_posix()
    split = relative_to_subset.parts[0] if relative_to_subset.parts else ""
    shard = "/".join(relative_to_subset.parts[1:-1])
    content_sha1 = hashlib.sha1(diagram.text.encode("utf-8", errors="replace")).hexdigest()
    include_deps = diagram.include_deps
    return CorpusRecord(
        id=stable_id(source.id, relative_txt, diagram.text),
        source_name=source.id,
        source_url=source.url,
        source_kind=source.kind,
        source_ref=subset_dir.name,
        license="verify-on-clone",
        license_family=license_family("verify-on-clone"),
        diagram_type=_synthetic_diagram_type(subset_dir.name, diagram.diagram_type),
        puml_path=str(relative_txt),
        published_render_path=str(relative_png),
        python_source_paths=[],
        include_deps=include_deps,
        is_self_contained=not include_deps,
        uses_include=bool(include_deps),
        uses_icon_library=diagram.uses_icon_library,
        plantuml_version=PLANTUML_VERSION,
        graphviz_version="",
        render_status="not_rendered",
        render_hash_svg="",
        render_hash_png="",
        verification_status="not_verified",
        render_fail_reason="",
        purpose=list(source.default_purpose),
        attribution=source.name,
        license_path="",
        source_commit=source.ref,
        source_repo_url=source.url,
        extra={
            "block_index": diagram.block_index,
            "content_sha1": content_sha1,
            "dataset_subset": subset_dir.name,
            "dataset_split": split,
            "dataset_shard": shard,
            "dataset_partition": partition,
            "dataset_repo_path": str(relative_txt),
            "published_render_pairing_status": "same_basename",
        },
    )


def _synthetic_png_stems(subset_dir: Path, partition_filters: set[str]) -> set[str]:
    stems: set[str] = set()
    for png_path in sorted(subset_dir.rglob("*.png")):
        relative_png = png_path.relative_to(subset_dir)
        if _matches_partition(relative_png.parent.as_posix(), partition_filters):
            stems.add(relative_png.with_suffix("").as_posix())
    return stems


def _synthetic_diagram_type(subset_name: str, fallback: str) -> str:
    if "_Act_" in subset_name:
        return "activity"
    if "_Seq_" in subset_name:
        return "sequence"
    return fallback


def _normalize_partition(value: str) -> str:
    return Path(value.strip("/")).as_posix()


def _matches_partition(relative_parent: str, partition_filters: set[str]) -> bool:
    if not partition_filters:
        return True
    normalized_parent = _normalize_partition(relative_parent)
    return any(
        normalized_parent == partition or normalized_parent.startswith(f"{partition}/")
        for partition in partition_filters
    )


def _reject_synthetic_options(
    source_id: str,
    subsets: list[str] | None,
    partitions: list[str] | None,
    max_records_per_subset: int,
) -> None:
    if subsets or partitions or max_records_per_subset:
        raise ValueError(
            "--subset, --partition, and --max-records-per-subset are only supported "
            f"for {SYNTHETIC_UML_DATASET_ID}, not {source_id}"
        )


def acquire_repo_plantuml_dataset(
    source: SourceDefinition,
    dataset_root: Path | str,
    output_path: Path | str,
    license_overrides_path: Path | str = DEFAULT_LICENSE_OVERRIDES_PATH,
) -> list[CorpusRecord]:
    """Acquire a manually staged Repo-PlantUML-Dataset checkout.

    The staged tree keeps source files under ``data/<owner>__<repo>/...`` and
    attribution metadata in ``metadata.csv``. Records remain training
    candidates, but default to ``verify-on-clone`` until a repo-level override
    explicitly records a permissive license.
    """

    staged_root = Path(dataset_root)
    data_root = staged_root / "data"
    metadata_path = staged_root / "metadata.csv"
    if not data_root.exists() or not metadata_path.exists():
        raise RuntimeError(
            f"{source.id} must be staged with data/ and metadata.csv under {staged_root}"
        )

    metadata_by_repo = _load_repo_plantuml_metadata(metadata_path)
    source_urls_by_path = _repo_dataset_urls_by_path(data_root, metadata_by_repo.values())
    license_overrides = load_license_overrides(license_overrides_path)
    dataset_commit = _git_commit(staged_root) if (staged_root / ".git").exists() else source.ref
    records: list[CorpusRecord] = []

    for diagram in extract_from_tree(data_root, source_name=source.id):
        support_reason = _repo_dataset_support_file_reason(diagram, data_root)
        if support_reason:
            continue
        relative_to_data = diagram.path.relative_to(data_root)
        repo_folder = relative_to_data.parts[0]
        repo_name = repo_folder.replace("__", "/")
        metadata = metadata_by_repo.get(repo_name)
        original_url = source_urls_by_path.get(diagram.path.resolve(), "")
        override = license_override_for_repo(repo_name, license_overrides)
        license_text = override.license if override else "verify-on-clone"
        render_path = ""
        if diagram.published_render_path:
            render_path = str(diagram.published_render_path.relative_to(staged_root))
        extra = {
            "block_index": diagram.block_index,
            "repo_name": repo_name,
            "original_puml_url": original_url,
            "dataset_commit": dataset_commit,
            "dataset_repo_path": str(relative_to_data),
            "content_sha1": hashlib.sha1(
                diagram.text.encode("utf-8", errors="replace")
            ).hexdigest(),
        }
        if metadata:
            extra.update(_repo_metadata_extra(metadata))
        if override and override.notes:
            extra["license_override_notes"] = override.notes
        if diagram.published_render_pairing_status:
            extra["published_render_pairing_status"] = diagram.published_render_pairing_status
        records.append(
            CorpusRecord(
                id=diagram.id,
                source_name=source.id,
                source_url=original_url or source.url,
                source_kind=source.kind,
                source_ref=repo_name,
                license=license_text,
                license_family=license_family(license_text),
                diagram_type=diagram.diagram_type,
                puml_path=str(diagram.path.relative_to(staged_root)),
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
                purpose=list(source.default_purpose),
                attribution=repo_name,
                license_path=override.license_path if override else "",
                source_commit=dataset_commit,
                source_repo_url=f"https://github.com/{repo_name}",
                extra=extra,
            )
        )
    write_jsonl(records, output_path)
    return records


def _load_repo_plantuml_metadata(path: Path) -> dict[str, RepoPlantUmlMetadata]:
    rows: dict[str, RepoPlantUmlMetadata] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            repo_name = str(row.get("repo_name", "")).strip()
            if not repo_name:
                continue
            rows[repo_name] = RepoPlantUmlMetadata(
                repo_name=repo_name,
                extension=str(row.get("extension", "")),
                puml_file_links=[
                    item.strip()
                    for item in str(row.get("puml_file_links", "")).split(";")
                    if item.strip()
                ],
                language=str(row.get("language", "")),
                stargazers_count=str(row.get("stargazers_count", "")),
                forks_count=str(row.get("forks_count", "")),
                open_issues_count=str(row.get("open_issues_count", "")),
                watchers_count=str(row.get("watchers_count", "")),
                created_at=str(row.get("created_at", "")),
                updated_at=str(row.get("updated_at", "")),
                size_kb=str(row.get("size_kb", "")),
            )
    return rows


def _repo_dataset_urls_by_path(
    data_root: Path,
    metadata_rows: Iterable[RepoPlantUmlMetadata],
) -> dict[Path, str]:
    urls: dict[Path, str] = {}
    for metadata in metadata_rows:
        for url in metadata.puml_file_links:
            local_path = _repo_dataset_local_path_for_raw_url(data_root, metadata.repo_name, url)
            if local_path and local_path.exists():
                urls[local_path.resolve()] = url
    return urls


def _repo_dataset_local_path_for_raw_url(
    data_root: Path,
    repo_name: str,
    url: str,
) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "raw.githubusercontent.com":
        return None
    parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(parts) < 4:
        return None
    if f"{parts[0]}/{parts[1]}".lower() != repo_name.lower():
        return None
    repo_root = data_root / repo_name.replace("/", "__")
    relative_path = Path(*parts[3:])
    candidate = repo_root / relative_path
    if candidate.exists():
        return candidate
    matches = [
        path
        for path in repo_root.rglob(relative_path.name)
        if path.is_file() and path.as_posix().endswith(relative_path.as_posix())
    ]
    return matches[0] if len(matches) == 1 else None


def _repo_metadata_extra(metadata: RepoPlantUmlMetadata) -> dict[str, str]:
    return {
        "repo_language": metadata.language,
        "repo_stars": metadata.stargazers_count,
        "repo_forks": metadata.forks_count,
        "repo_open_issues": metadata.open_issues_count,
        "repo_watchers": metadata.watchers_count,
        "repo_created_at": metadata.created_at,
        "repo_updated_at": metadata.updated_at,
        "repo_size_kb": metadata.size_kb,
        "repo_declared_extensions": metadata.extension,
    }


def _repo_dataset_support_file_reason(diagram: ExtractedDiagram, data_root: Path) -> str:
    text = diagram.text.strip()
    if not text:
        return "empty_file"
    relative = diagram.path.relative_to(data_root)
    parts = {part.lower() for part in relative.parts}
    name = diagram.path.name.lower()
    if name in {"style.puml", "styles.puml"}:
        return "style_include"
    if name.startswith("puml-theme-") or "plantuml-config" in name:
        return "theme_or_config_include"
    if {"includes", "partials"} & parts:
        return "include_partial"
    if "lib" in parts and (name == "c4.puml" or name.startswith("c4_")):
        return "c4_library_include"
    return ""


def vendor_include_source(
    source_id: str = "c4-plantuml",
    output_dir: Path | str = PROJECT_ROOT / "data" / "vendor" / "c4-plantuml",
    force: bool = False,
    raw_dir: Path | str = PROJECT_ROOT / "data" / "raw",
) -> list[Path]:
    """Vendor PlantUML include files from a configured source."""

    config = load_sources_config()
    source = next((item for item in config.sources if item.id == source_id), None)
    if not source:
        raise ValueError(f"unknown source: {source_id}")
    if source.acquisition_mode not in {"git", "local"}:
        raise ValueError(f"{source_id} cannot be vendored from acquisition mode {source.acquisition_mode}")
    staged_root = _stage_source(source, Path(raw_dir))
    vendor_root = Path(output_dir)
    if force and vendor_root.exists():
        shutil.rmtree(vendor_root)
    return copy_vendor_include_files(staged_root, vendor_root)


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


def copy_vendor_include_files(staged_root: Path, vendor_root: Path) -> list[Path]:
    """Copy PlantUML include files from a staged tree into a vendor root."""

    copied: list[Path] = []
    vendor_root.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(staged_root.rglob("*")):
        if not source_path.is_file() or source_path.suffix.lower() not in {".puml", ".iuml"}:
            continue
        if ".git" in source_path.parts:
            continue
        relative = source_path.relative_to(staged_root)
        target = vendor_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
        copied.append(target)
    return copied


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
        pairing = python_source_pairing_for_expected_puml(puml_path, staged_root)
        if pairing.paths:
            record.python_source_paths = [str(path.relative_to(staged_root)) for path in pairing.paths]
            record.extra["source_pairing_confidence"] = pairing.confidence
            record.extra["source_pairing_reason"] = pairing.reason
            if "source_conditioned_eval" not in record.purpose:
                record.purpose.append("source_conditioned_eval")
        elif "source_conditioned_eval" in record.purpose:
            record.purpose = [purpose for purpose in record.purpose if purpose != "source_conditioned_eval"]


def python_sources_for_expected_puml(puml_path: Path, staged_root: Path) -> list[Path]:
    """Heuristically pair py2puml expected .puml files with Python sources."""

    return python_source_pairing_for_expected_puml(puml_path, staged_root).paths


def python_source_pairing_for_expected_puml(puml_path: Path, staged_root: Path) -> SourcePairing:
    """Pair a py2puml expected diagram with Python source files."""

    if not puml_path.exists() or puml_path.suffix.lower() not in {".puml", ".plantuml", ".iuml"}:
        return SourcePairing([], "none", "not_expected_puml")
    fqn_sources = _python_sources_from_puml_fqns(puml_path, staged_root)
    if fqn_sources:
        return SourcePairing(fqn_sources, "high", "matched_fully_qualified_diagram_items")
    same_stem = puml_path.with_suffix(".py")
    if same_stem.exists():
        return SourcePairing([same_stem], "high", "matched_same_stem_python_source")
    parent = puml_path.parent
    candidates = sorted(
        path
        for path in parent.rglob("*.py")
        if path.name != "__init__.py" and ".git" not in path.parts
    )
    if candidates:
        return SourcePairing(candidates, "heuristic", "used_nearby_package_python_sources")
    init_file = parent / "__init__.py"
    if init_file.exists():
        return SourcePairing([init_file], "heuristic", "used_package_init_python_source")
    return SourcePairing([], "none", "no_python_source_match")


def _python_sources_from_puml_fqns(puml_path: Path, staged_root: Path) -> list[Path]:
    puml_text = puml_path.read_text(encoding="utf-8", errors="replace")
    roots = _python_module_roots(puml_path, staged_root)
    sources: dict[str, Path] = {}
    for match in PY2PUML_ITEM_RE.finditer(puml_text):
        module_parts = match.group("fqn").split(".")[:-1]
        source_path = _module_parts_to_python_path(module_parts, roots)
        if source_path:
            sources[source_path.as_posix()] = source_path
    return [sources[key] for key in sorted(sources)]


def _python_module_roots(puml_path: Path, staged_root: Path) -> list[Path]:
    candidates = [
        staged_root,
        staged_root / "src",
        puml_path.parent,
        puml_path.parent / "src",
        puml_path.parent.parent,
        puml_path.parent.parent / "src",
    ]
    roots: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)
    return roots


def _module_parts_to_python_path(module_parts: list[str], roots: list[Path]) -> Path | None:
    if not module_parts:
        return None
    relative = Path(*module_parts)
    for root in roots:
        module_file = root / relative.with_suffix(".py")
        if module_file.exists():
            return module_file
        init_file = root / relative / "__init__.py"
        if init_file.exists():
            return init_file
    return None


def ensure_generated_dirs() -> None:
    for path in (
        PROJECT_ROOT / "data" / "raw",
        PROJECT_ROOT / "data" / "rendered",
        PROJECT_ROOT / "data" / "manifests",
        PROJECT_ROOT / "data" / "reports",
        PROJECT_ROOT / "data" / "vendor",
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
