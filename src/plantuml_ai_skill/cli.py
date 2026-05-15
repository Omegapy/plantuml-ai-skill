"""Command-line interface for the PlantUML training-data pipeline."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import tempfile
import time

from .acquisition import (
    SYNTHETIC_UML_DATASET_ID,
    SYNTHETIC_UML_DATASET_ROOT_NAME,
    acquire_source,
    ensure_generated_dirs,
    vendor_include_source,
)
from .assets import init_assets
from .config import load_sources_config
from .constants import DEFAULT_JAR_PATH, DEFAULT_LICENSE_BLOCKLIST_PATH, PROJECT_ROOT
from .contact_sheet import write_png_mismatch_contact_sheet
from .curation import DEFAULT_CURATION_PATH, apply_curation, load_curation_decisions
from .doctor import run_doctor
from .extraction import extract_from_tree, extract_plantuml_blocks
from .includes import inline_resolved_includes, resolve_include_deps, unresolved_resolution_reason
from .license_policy import blocked_license_review_for_repo, load_license_blocklist, training_block_reason
from .manifest import CorpusRecord, read_jsonl, write_jsonl
from .recommendation_coverage import check_recommendation_coverage
from .renderer import PlantUMLRenderer, RenderResult, render_version_label
from .reporting import (
    render_failure_report,
    render_failure_summary_report,
    render_failure_triage_report,
    write_render_failure_report,
    write_render_failure_summary_report,
    write_render_failure_triage_report,
    write_report,
)
from .splits import build_splits
from .verify import (
    PNG_PERCEPTUAL_MAX_DISTANCE,
    png_average_hash,
    png_dimensions,
    png_hash_distance,
    svg_hash,
    svg_matches,
)
from .improvement.cli import add_improve_parser, dispatch as dispatch_improve
from .release_packages import add_package_parser, dispatch as dispatch_package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantuml-skill")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check Java, Graphviz, pinned jar, and -testdot")
    doctor.add_argument("--jar", default=str(DEFAULT_JAR_PATH))
    doctor.add_argument("--java", default="")
    doctor.add_argument("--json", action="store_true")

    assets = sub.add_parser("init-assets", help="download and verify the pinned PlantUML jar")
    assets.add_argument("--asset-dir", default=str(DEFAULT_JAR_PATH.parent))
    assets.add_argument("--force", action="store_true")

    acquire = sub.add_parser("acquire", help="acquire a configured source into a manifest")
    acquire.add_argument("--source", required=True)
    acquire.add_argument("--output", default=str(PROJECT_ROOT / "data" / "manifests" / "source.jsonl"))
    acquire.add_argument("--dry-run", action="store_true")
    acquire.add_argument(
        "--subset",
        action="append",
        default=[],
        help="synthetic dataset subset to acquire; may be passed multiple times",
    )
    acquire.add_argument(
        "--partition",
        action="append",
        default=[],
        help="synthetic dataset partition such as Train/1 or Test/Test_1; may be passed multiple times",
    )
    acquire.add_argument(
        "--max-records-per-subset",
        type=int,
        default=0,
        help="synthetic dataset cap per selected subset; 0 means no cap",
    )

    vendor = sub.add_parser("vendor-includes", help="vendor include files from a configured source")
    vendor.add_argument("--source", default="c4-plantuml")
    vendor.add_argument("--output", default=str(PROJECT_ROOT / "data" / "vendor" / "c4-plantuml"))
    vendor.add_argument("--force", action="store_true")

    extract = sub.add_parser("extract", help="extract PlantUML blocks from a local tree")
    extract.add_argument("--input", required=True)
    extract.add_argument("--source-name", default="local")
    extract.add_argument("--output", required=True)

    render = sub.add_parser("render", help="render manifest records to SVG")
    render.add_argument("--manifest", required=True)
    render.add_argument("--source-root", default="")
    render.add_argument("--output", default=str(PROJECT_ROOT / "data" / "manifests" / "rendered.jsonl"))
    render.add_argument("--render-dir", default=str(PROJECT_ROOT / "data" / "rendered"))
    render.add_argument("--jar", default=str(DEFAULT_JAR_PATH))
    render.add_argument("--java", default="")
    render.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="render records in PlantUML file batches; 1 keeps the per-record pipe renderer",
    )
    render.add_argument(
        "--progress-interval",
        type=int,
        default=None,
        help=(
            "write render progress telemetry to stderr every N records; 0 disables progress output; "
            "defaults to 100 in batched mode and off in serial mode"
        ),
    )
    render.add_argument(
        "--include-root",
        action="append",
        default=[],
        help="local vendored include root; may be passed multiple times",
    )

    verify = sub.add_parser("verify", help="verify rendered SVG/PNG against published references")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--source-root", default="")
    verify.add_argument("--output", default=str(PROJECT_ROOT / "data" / "manifests" / "verified.jsonl"))
    verify.add_argument(
        "--workers",
        type=int,
        default=1,
        help="parallel verifier worker processes; 1 keeps the serial verifier",
    )
    verify.add_argument(
        "--progress-interval",
        type=int,
        default=None,
        help=(
            "write progress telemetry to stderr every N records; 0 disables progress output; "
            "defaults to 100 in parallel mode and off in serial mode"
        ),
    )
    verify.add_argument(
        "--chunk-size",
        type=int,
        default=0,
        help="records per parallel worker task; 0 chooses a conservative default",
    )

    audit = sub.add_parser("audit-licenses", help="summarize license families in a manifest")
    audit.add_argument("--manifest", required=True)

    candidates = sub.add_parser(
        "license-candidates",
        help="rank unknown-license repositories and annotate reviewed blocks",
    )
    candidates.add_argument("--manifest", required=True)
    candidates.add_argument("--blocklist", default=str(DEFAULT_LICENSE_BLOCKLIST_PATH))
    candidates.add_argument("--limit", type=int, default=40)

    splits = sub.add_parser("build-splits", help="build deterministic train/eval split manifests")
    splits.add_argument("--manifest", required=True)
    splits.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "manifests" / "splits"))
    splits.add_argument("--synthetic-cap", type=int, default=5000)
    splits.add_argument("--curation", default=str(DEFAULT_CURATION_PATH))

    report = sub.add_parser("report", help="write a Markdown corpus report")
    report.add_argument("--manifest", required=True)
    report.add_argument("--output", default=str(PROJECT_ROOT / "data" / "reports" / "corpus-report.md"))
    report.add_argument("--curation", default=str(DEFAULT_CURATION_PATH))

    failures = sub.add_parser("render-failures", help="list failed and skipped render records as TSV")
    failures.add_argument("--manifest", required=True)
    failures.add_argument("--output", default="")

    failure_triage = sub.add_parser(
        "render-failure-triage",
        help="classify failed and skipped render records as TSV",
    )
    failure_triage.add_argument("--manifest", required=True)
    failure_triage.add_argument("--output", default="")

    failure_summary = sub.add_parser(
        "render-failure-summary",
        help="group failed and skipped renders by repo, license, class, and actionability as TSV",
    )
    failure_summary.add_argument("--manifest", required=True)
    failure_summary.add_argument("--output", default="")

    contact = sub.add_parser("png-contact-sheet", help="write an HTML contact sheet for PNG mismatches")
    contact.add_argument("--manifest", required=True)
    contact.add_argument("--source-root", default="")
    contact.add_argument("--curation", default=str(DEFAULT_CURATION_PATH))
    contact.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "reports" / "png-mismatch-contact-sheet.html"),
    )

    coverage = sub.add_parser("coverage", help="check report recommendation coverage")
    coverage.add_argument("--config", default=str(PROJECT_ROOT / "config" / "sources.yml"))
    coverage.add_argument("--json", action="store_true")

    add_improve_parser(sub)
    add_package_parser(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_generated_dirs()
    try:
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "init-assets":
            jar = init_assets(args.asset_dir, force=args.force)
            print(f"PlantUML jar ready: {jar}")
            return 0
        if args.command == "acquire":
            acquisition_stats: dict[str, int] = {}
            records = acquire_source(
                args.source,
                args.output,
                dry_run=args.dry_run,
                subsets=args.subset,
                partitions=args.partition,
                max_records_per_subset=args.max_records_per_subset,
                acquisition_stats=acquisition_stats,
            )
            print(f"Wrote {len(records)} records to {args.output}")
            if acquisition_stats:
                print(
                    "Synthetic pairing stats: "
                    f"paired={acquisition_stats.get('paired_records', 0)}; "
                    f"txt_without_png={acquisition_stats.get('txt_without_png', 0)}; "
                    f"png_without_txt={acquisition_stats.get('png_without_txt', 0)}; "
                    f"skipped_by_cap={acquisition_stats.get('skipped_by_cap', 0)}"
                )
            return 0
        if args.command == "vendor-includes":
            copied = vendor_include_source(args.source, args.output, force=args.force)
            print(f"Vendored {len(copied)} include files to {args.output}")
            return 0
        if args.command == "extract":
            return _extract(args)
        if args.command == "render":
            return _render(args)
        if args.command == "verify":
            return _verify(args)
        if args.command == "audit-licenses":
            return _audit_licenses(args)
        if args.command == "license-candidates":
            return _license_candidates(args)
        if args.command == "build-splits":
            return _build_splits(args)
        if args.command == "report":
            records = _read_curated_records(args.manifest, args.curation)
            path = write_report(records, args.output)
            print(f"Wrote report: {path}")
            return 0
        if args.command == "render-failures":
            records = read_jsonl(args.manifest)
            if args.output:
                path = write_render_failure_report(records, args.output)
                print(f"Wrote render failure report: {path}")
            else:
                print(render_failure_report(records), end="")
            return 0
        if args.command == "render-failure-triage":
            records = read_jsonl(args.manifest)
            if args.output:
                path = write_render_failure_triage_report(records, args.output)
                print(f"Wrote render failure triage report: {path}")
            else:
                print(render_failure_triage_report(records), end="")
            return 0
        if args.command == "render-failure-summary":
            records = read_jsonl(args.manifest)
            if args.output:
                path = write_render_failure_summary_report(records, args.output)
                print(f"Wrote render failure summary report: {path}")
            else:
                print(render_failure_summary_report(records), end="")
            return 0
        if args.command == "png-contact-sheet":
            records = _read_curated_records(args.manifest, args.curation)
            path, count = write_png_mismatch_contact_sheet(records, args.output, args.source_root or None)
            print(f"Wrote {count} PNG mismatch rows to {path}")
            return 0
        if args.command == "coverage":
            return _coverage(args)
        if args.command == "improve":
            return dispatch_improve(args)
        if args.command == "package":
            return dispatch_package(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error("unreachable command")
    return 2


def _doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(args.jar, java_bin=args.java or None)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        for check in checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.message}")
            if check.details:
                print(f"  {check.details}")
    return 0 if all(check.ok for check in checks) else 1


def _extract(args: argparse.Namespace) -> int:
    from .acquisition import records_from_diagrams

    root = Path(args.input)
    diagrams = extract_from_tree(root, source_name=args.source_name)
    records = records_from_diagrams(
        diagrams,
        source_name=args.source_name,
        source_url=str(root),
        source_kind="local",
        source_ref="local",
        license_text="verify-on-clone",
        purpose=["gold_eval"],
        root=root,
    )
    write_jsonl(records, args.output)
    print(f"Wrote {len(records)} records to {args.output}")
    return 0


def _render(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    include_roots = _include_roots(args.include_root)
    renderer = PlantUMLRenderer(jar_path=args.jar, java_bin=args.java or None, include_roots=include_roots)
    render_dir = Path(args.render_dir)
    render_dir.mkdir(parents=True, exist_ok=True)
    batch_size = max(1, int(args.batch_size or 1))
    progress_interval = _render_progress_interval(args.progress_interval, batch_size)
    if batch_size > 1:
        return _render_batched(
            records,
            renderer,
            render_dir,
            args.output,
            args.source_root,
            include_roots,
            batch_size,
            progress_interval,
        )
    return _render_serial(
        records,
        renderer,
        render_dir,
        args.output,
        args.source_root,
        include_roots,
        progress_interval,
    )


def _render_serial(
    records: list[CorpusRecord],
    renderer: PlantUMLRenderer,
    render_dir: Path,
    output: str,
    source_root: str,
    include_roots: list[Path],
    progress_interval: int,
) -> int:
    progress = _RenderProgress(len(records), progress_interval)
    updated: list[CorpusRecord] = []
    for record in records:
        try:
            puml_text = _prepare_render_text(record, source_root, include_roots)
            if record.render_status == "skipped":
                updated.append(record)
                continue
            result = renderer.render_svg(puml_text)
            if result.ok:
                svg_path = render_dir / f"{record.id}.svg"
                svg_path.write_bytes(result.output)
                record.render_status = "ok"
                record.render_hash_svg = svg_hash(result.output)
                record.plantuml_version = render_version_label()
                record.render_fail_reason = ""
                record.extra["rendered_svg_path"] = str(svg_path)
                if record.published_render_path.lower().endswith(".png"):
                    png_result = renderer.render_png(puml_text)
                    if png_result.ok:
                        png_path = render_dir / f"{record.id}.png"
                        png_path.write_bytes(png_result.output)
                        record.render_hash_png = str(png_average_hash(png_result.output))
                        record.extra["rendered_png_path"] = str(png_path)
                    else:
                        record.render_status = "failed"
                        record.render_fail_reason = png_result.stderr or f"png_returncode_{png_result.returncode}"
            else:
                record.render_status = "failed"
                record.render_fail_reason = result.stderr or f"returncode_{result.returncode}"
        except Exception as exc:
            record.render_status = "failed"
            record.render_fail_reason = str(exc)
        updated.append(record)
        progress.record(record)
    write_jsonl(updated, output)
    failed = sum(record.render_status == "failed" for record in updated)
    rendered = sum(record.render_status == "ok" for record in updated)
    skipped = sum(record.render_status == "skipped" for record in updated)
    print(f"Rendered {rendered}/{len(updated)} records; skipped {skipped}; wrote {output}")
    return 0 if failed == 0 else 1


@dataclass(frozen=True)
class _BatchRenderItem:
    index: int
    record: CorpusRecord
    puml_text: str


class _RenderProgress:
    def __init__(self, total: int, interval: int) -> None:
        self.total = total
        self.interval = max(0, interval)
        self.started_at = time.monotonic()
        self.processed = 0
        self.counts: Counter[str] = Counter()

    def record(self, record: CorpusRecord) -> None:
        self.processed += 1
        if record.render_status == "ok":
            self.counts["rendered"] += 1
        elif record.render_status == "failed":
            self.counts["failed"] += 1
        elif record.render_status == "skipped":
            self.counts["skipped"] += 1
        if self.interval and (self.processed % self.interval == 0 or self.processed == self.total):
            self.emit()

    def emit(self) -> None:
        elapsed = max(time.monotonic() - self.started_at, 1e-9)
        rows_per_minute = self.processed * 60 / elapsed
        print(
            "render progress: "
            f"processed={self.processed}/{self.total} "
            f"rendered={self.counts['rendered']} "
            f"failed={self.counts['failed']} "
            f"skipped={self.counts['skipped']} "
            f"rows/minute={rows_per_minute:.1f}",
            file=sys.stderr,
        )


def _render_batched(
    records: list[CorpusRecord],
    renderer: PlantUMLRenderer,
    render_dir: Path,
    output: str,
    source_root: str,
    include_roots: list[Path],
    batch_size: int,
    progress_interval: int,
) -> int:
    progress = _RenderProgress(len(records), progress_interval)
    updated: list[CorpusRecord | None] = [None] * len(records)
    batch: list[_BatchRenderItem] = []
    for index, record in enumerate(records):
        try:
            puml_text = _prepare_render_text(record, source_root, include_roots)
            if record.render_status == "skipped":
                updated[index] = record
                progress.record(record)
                continue
            batch.append(_BatchRenderItem(index=index, record=record, puml_text=puml_text))
            if len(batch) >= batch_size:
                _render_batch(batch, renderer, render_dir)
                for item in batch:
                    updated[item.index] = item.record
                    progress.record(item.record)
                batch = []
        except Exception as exc:
            record.render_status = "failed"
            record.render_fail_reason = str(exc)
            updated[index] = record
            progress.record(record)
    if batch:
        _render_batch(batch, renderer, render_dir)
        for item in batch:
            updated[item.index] = item.record
            progress.record(item.record)
    if any(record is None for record in updated):
        raise RuntimeError("batched renderer did not return every input record")
    output_records = [record for record in updated if record is not None]
    write_jsonl(output_records, output)
    failed = sum(record.render_status == "failed" for record in output_records)
    rendered = sum(record.render_status == "ok" for record in output_records)
    skipped = sum(record.render_status == "skipped" for record in output_records)
    print(f"Rendered {rendered}/{len(output_records)} records; skipped {skipped}; wrote {output}")
    return 0 if failed == 0 else 1


def _render_batch(items: list[_BatchRenderItem], renderer: PlantUMLRenderer, render_dir: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="plantuml-batch-") as tmp:
        tmp_root = Path(tmp)
        puml_dir = tmp_root / "puml"
        svg_dir = tmp_root / "svg"
        png_dir = tmp_root / "png"
        puml_dir.mkdir()
        svg_dir.mkdir()
        png_dir.mkdir()
        input_paths: list[Path] = []
        for item in items:
            puml_path = puml_dir / f"{item.record.id}.puml"
            puml_path.write_text(item.puml_text, encoding="utf-8")
            input_paths.append(puml_path)

        svg_result = renderer.render_batch(input_paths, "-tsvg", svg_dir)
        png_items: list[_BatchRenderItem] = []
        for item, input_path in zip(items, input_paths):
            svg_path = svg_dir / f"{item.record.id}.svg"
            if not svg_path.exists():
                _mark_batch_render_failed(item.record, svg_result, input_path, "svg output missing")
                continue
            svg_bytes = svg_path.read_bytes()
            if _plantuml_error_svg(svg_bytes):
                _mark_batch_render_failed(item.record, svg_result, input_path, "svg contains PlantUML error output")
                continue
            final_svg_path = render_dir / f"{item.record.id}.svg"
            final_svg_path.write_bytes(svg_bytes)
            item.record.render_status = "ok"
            item.record.render_hash_svg = svg_hash(svg_bytes)
            item.record.plantuml_version = render_version_label()
            item.record.render_fail_reason = ""
            item.record.extra["rendered_svg_path"] = str(final_svg_path)
            if item.record.published_render_path.lower().endswith(".png"):
                png_items.append(item)

        if not png_items:
            return
        png_input_paths = [puml_dir / f"{item.record.id}.puml" for item in png_items]
        png_result = renderer.render_batch(png_input_paths, "-tpng", png_dir)
        for item, input_path in zip(png_items, png_input_paths):
            png_path = png_dir / f"{item.record.id}.png"
            if not png_path.exists():
                _mark_batch_render_failed(item.record, png_result, input_path, "png output missing")
                continue
            png_bytes = png_path.read_bytes()
            final_png_path = render_dir / f"{item.record.id}.png"
            final_png_path.write_bytes(png_bytes)
            item.record.render_hash_png = str(png_average_hash(png_bytes))
            item.record.extra["rendered_png_path"] = str(final_png_path)


def _prepare_render_text(record: CorpusRecord, source_root: str, include_roots: list[Path]) -> str:
    puml_path = _resolve_record_path(record, source_root)
    include_resolutions = (
        resolve_include_deps(record.include_deps, include_roots, puml_path.parent)
        if record.include_deps
        else []
    )
    include_reason = unresolved_resolution_reason(include_resolutions)
    if include_reason:
        record.render_status = "skipped"
        record.render_fail_reason = include_reason
        return ""
    mirrored = [
        resolution.target
        for resolution in include_resolutions
        if resolution.reason == "trusted_remote_mirrored"
    ]
    if mirrored:
        record.extra["include_resolution_status"] = "trusted_remote_mirrored"
        record.extra["mirrored_include_deps"] = mirrored
    puml_text = _puml_text_for_record(record, puml_path)
    if record.include_deps:
        puml_text = inline_resolved_includes(puml_text, include_resolutions)
    return puml_text


def _mark_batch_render_failed(
    record: CorpusRecord,
    result: RenderResult,
    input_path: Path,
    detail: str,
) -> None:
    record.render_status = "failed"
    stderr = result.stderr.strip()
    if stderr:
        record.render_fail_reason = f"{detail}: {stderr}"
    else:
        record.render_fail_reason = f"{detail}: returncode_{result.returncode}; file={input_path.name}"


def _plantuml_error_svg(svg_bytes: bytes) -> bool:
    text = svg_bytes.decode("utf-8", errors="replace")
    return "Syntax Error" in text or "Some diagram description contains errors" in text


@dataclass(frozen=True)
class _VerifyWorkItem:
    index: int
    record: CorpusRecord
    source_root: str


class _VerifyProgress:
    def __init__(self, total: int, interval: int) -> None:
        self.total = total
        self.interval = max(0, interval)
        self.started_at = time.monotonic()
        self.processed = 0
        self.counts: Counter[str] = Counter()

    def record(self, record: CorpusRecord) -> None:
        self.processed += 1
        status = record.verification_status
        if status.endswith("_match"):
            self.counts["match"] += 1
        elif status.endswith("_mismatch"):
            self.counts["mismatch"] += 1
        elif status in {"verify_error", "render_skipped", "render_failed"}:
            self.counts[status] += 1
        if self.interval and (self.processed % self.interval == 0 or self.processed == self.total):
            self.emit()

    def emit(self) -> None:
        elapsed = max(time.monotonic() - self.started_at, 1e-9)
        rows_per_minute = self.processed * 60 / elapsed
        print(
            "verify progress: "
            f"processed={self.processed}/{self.total} "
            f"match={self.counts['match']} "
            f"mismatch={self.counts['mismatch']} "
            f"verify_error={self.counts['verify_error']} "
            f"render_skipped={self.counts['render_skipped']} "
            f"render_failed={self.counts['render_failed']} "
            f"rows/minute={rows_per_minute:.1f}",
            file=sys.stderr,
        )


def _verify(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    workers = max(1, int(args.workers or 1))
    progress_interval = _verify_progress_interval(args.progress_interval, workers)
    if workers == 1:
        updated = _verify_serial(records, args.source_root, progress_interval)
    else:
        chunk_size = int(args.chunk_size or 0)
        if chunk_size <= 0:
            chunk_size = _default_verify_chunk_size(len(records), workers)
        updated = _verify_parallel(records, args.source_root, workers, progress_interval, chunk_size)
    write_jsonl(updated, args.output)
    failures = sum(
        record.verification_status.endswith("mismatch") or record.verification_status == "verify_error"
        for record in updated
    )
    skipped = sum(record.verification_status in {"render_skipped", "render_failed"} for record in updated)
    checked = len(updated) - skipped
    print(f"Verified {checked - failures}/{checked} rendered records; skipped {skipped}; wrote {args.output}")
    return 0 if failures == 0 else 1


def _verify_serial(records: list[CorpusRecord], source_root: str, progress_interval: int) -> list[CorpusRecord]:
    progress = _VerifyProgress(len(records), progress_interval)
    updated: list[CorpusRecord] = []
    for record in records:
        updated_record = _verify_record(record, source_root)
        updated.append(updated_record)
        progress.record(updated_record)
    return updated


def _verify_parallel(
    records: list[CorpusRecord],
    source_root: str,
    workers: int,
    progress_interval: int,
    chunk_size: int,
) -> list[CorpusRecord]:
    updated: list[CorpusRecord | None] = [None] * len(records)
    progress = _VerifyProgress(len(records), progress_interval)
    chunks = list(_verify_work_chunks(records, source_root, max(1, chunk_size)))
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_verify_chunk, chunk) for chunk in chunks]
        for future in as_completed(futures):
            for index, record in future.result():
                updated[index] = record
                progress.record(record)
    if any(record is None for record in updated):
        raise RuntimeError("parallel verifier did not return every input record")
    return [record for record in updated if record is not None]


def _verify_record(record: CorpusRecord, source_root: str) -> CorpusRecord:
    try:
        if record.render_status == "failed":
            record.verification_status = "render_failed"
        elif record.render_status == "skipped":
            record.verification_status = "render_skipped"
        elif not record.published_render_path:
            record.verification_status = "rendered_no_reference" if record.render_hash_svg else "not_verified"
        else:
            reference_path = _resolve_reference_path(record, source_root)
            if reference_path.suffix.lower() == ".svg":
                rendered_path = _rendered_output_path(record, "svg")
                record.verification_status = (
                    "svg_match"
                    if svg_matches(rendered_path.read_bytes(), reference_path.read_bytes())
                    else "svg_mismatch"
                )
            elif reference_path.suffix.lower() == ".png":
                rendered_path = _rendered_output_path(record, "png")
                rendered_bytes = rendered_path.read_bytes()
                reference_bytes = reference_path.read_bytes()
                distance = png_hash_distance(rendered_bytes, reference_bytes)
                record.extra["png_hash_distance"] = str(distance)
                record.extra["rendered_png_dimensions"] = _dimensions_label(png_dimensions(rendered_bytes))
                record.extra["published_png_dimensions"] = _dimensions_label(png_dimensions(reference_bytes))
                record.verification_status = (
                    "png_match" if distance <= PNG_PERCEPTUAL_MAX_DISTANCE else "png_mismatch"
                )
            else:
                record.verification_status = "unsupported_reference_format"
    except Exception as exc:
        record.verification_status = "verify_error"
        record.render_fail_reason = str(exc)
    return record


def _verify_chunk(chunk: list[_VerifyWorkItem]) -> list[tuple[int, CorpusRecord]]:
    return [_verify_indexed_record(item) for item in chunk]


def _verify_indexed_record(item: _VerifyWorkItem) -> tuple[int, CorpusRecord]:
    return item.index, _verify_record(item.record, item.source_root)


def _verify_work_chunks(
    records: list[CorpusRecord], source_root: str, chunk_size: int
) -> list[list[_VerifyWorkItem]]:
    chunks: list[list[_VerifyWorkItem]] = []
    chunk: list[_VerifyWorkItem] = []
    for index, record in enumerate(records):
        chunk.append(_VerifyWorkItem(index=index, record=record, source_root=source_root))
        if len(chunk) >= chunk_size:
            chunks.append(chunk)
            chunk = []
    if chunk:
        chunks.append(chunk)
    return chunks


def _default_verify_chunk_size(record_count: int, workers: int) -> int:
    if record_count <= 0:
        return 1
    return max(1, min(100, record_count // max(1, workers * 8) or 1))


def _render_progress_interval(raw_interval: int | None, batch_size: int) -> int:
    if raw_interval is None:
        return 0 if batch_size == 1 else 100
    return max(0, int(raw_interval or 0))


def _verify_progress_interval(raw_interval: int | None, workers: int) -> int:
    if raw_interval is None:
        return 0 if workers == 1 else 100
    return max(0, int(raw_interval or 0))


def _audit_licenses(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    counts: dict[str, int] = {}
    blocked_training = 0
    missing_attribution = 0
    for record in records:
        counts[record.license_family] = counts.get(record.license_family, 0) + 1
        if "training" in record.purpose and training_block_reason(record.license, record.purpose):
            blocked_training += 1
        if not record.attribution:
            missing_attribution += 1
    for family, count in sorted(counts.items()):
        print(f"{family}: {count}")
    print(f"blocked_training_records: {blocked_training}")
    print(f"missing_attribution: {missing_attribution}")
    return 0


def _license_candidates(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    blocklist = load_license_blocklist(args.blocklist)
    grouped: dict[str, Counter[str]] = {}
    for record in records:
        if record.license_family != "unknown":
            continue
        repo = record.source_ref
        stats = grouped.setdefault(repo, Counter())
        stats["count"] += 1
        stats[f"render_{record.render_status or 'unknown'}"] += 1

    rows = sorted(grouped.items(), key=lambda item: (-item[1]["count"], item[0]))
    if args.limit > 0:
        rows = rows[: args.limit]

    header = [
        "count",
        "source_ref",
        "render_ok",
        "render_failed",
        "render_skipped",
        "blocked_review",
        "license",
        "license_family",
        "license_path",
        "notes",
    ]
    print("\t".join(header))
    for repo, stats in rows:
        review = blocked_license_review_for_repo(repo, blocklist)
        print(
            "\t".join(
                _tsv_cell(value)
                for value in [
                    stats["count"],
                    repo,
                    stats["render_ok"],
                    stats["render_failed"],
                    stats["render_skipped"],
                    "yes" if review else "no",
                    review.license if review else "",
                    review.license_family if review else "",
                    review.license_path if review else "",
                    review.notes if review else "",
                ]
            )
        )
    return 0


def _build_splits(args: argparse.Namespace) -> int:
    records = _read_curated_records(args.manifest, args.curation)
    splits = build_splits(records, args.output_dir, synthetic_cap=args.synthetic_cap)
    for name, split_records in sorted(splits.items()):
        print(f"{name}: {len(split_records)}")
    return 0


def _read_curated_records(manifest_path: str, curation_path: str) -> list[CorpusRecord]:
    records = read_jsonl(manifest_path)
    return apply_curation(records, load_curation_decisions(curation_path))


def _coverage(args: argparse.Namespace) -> int:
    result = check_recommendation_coverage(load_sources_config(args.config))
    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "missing_sources": sorted(result.missing_sources),
                    "missing_features": sorted(result.missing_features),
                },
                indent=2,
            )
        )
    elif result.ok:
        print("All report recommendations are represented.")
    else:
        if result.missing_sources:
            print("Missing sources: " + ", ".join(sorted(result.missing_sources)))
        if result.missing_features:
            print("Missing features: " + ", ".join(sorted(result.missing_features)))
    return 0 if result.ok else 1


def _resolve_record_path(record: CorpusRecord, source_root: str) -> Path:
    if source_root:
        return Path(source_root) / record.puml_path
    if record.source_name == "fixtures":
        return PROJECT_ROOT / "tests" / "fixtures" / record.puml_path
    if record.source_name == SYNTHETIC_UML_DATASET_ID:
        return PROJECT_ROOT / "data" / "raw" / SYNTHETIC_UML_DATASET_ROOT_NAME / record.puml_path
    return PROJECT_ROOT / "data" / "raw" / record.source_name / record.puml_path


def _resolve_reference_path(record: CorpusRecord, source_root: str) -> Path:
    if source_root:
        return Path(source_root) / record.published_render_path
    if record.source_name == "fixtures":
        return PROJECT_ROOT / "tests" / "fixtures" / record.published_render_path
    if record.source_name == SYNTHETIC_UML_DATASET_ID:
        return PROJECT_ROOT / "data" / "raw" / SYNTHETIC_UML_DATASET_ROOT_NAME / record.published_render_path
    return PROJECT_ROOT / "data" / "raw" / record.source_name / record.published_render_path


def _rendered_output_path(record: CorpusRecord, suffix: str) -> Path:
    key = f"rendered_{suffix}_path"
    if key in record.extra:
        return Path(str(record.extra[key]))
    return PROJECT_ROOT / "data" / "rendered" / f"{record.id}.{suffix}"


def _puml_text_for_record(record: CorpusRecord, puml_path: Path) -> str:
    raw_text = puml_path.read_text(encoding="utf-8", errors="replace")
    blocks = extract_plantuml_blocks(raw_text)
    if not blocks:
        return raw_text
    block_index = int(record.extra.get("block_index", 0))
    if block_index >= len(blocks):
        raise IndexError(f"block_index {block_index} out of range for {puml_path}")
    return blocks[block_index]


def _dimensions_label(dimensions: tuple[int, int]) -> str:
    return f"{dimensions[0]}x{dimensions[1]}"


def _tsv_cell(value: object) -> str:
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ")


def _include_roots(extra_roots: list[str]) -> list[Path]:
    config = load_sources_config()
    configured = config.renderer.get("include_roots", [])
    roots: list[Path] = []
    for value in list(configured) + list(extra_roots):
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        roots.append(path)
    return roots


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
