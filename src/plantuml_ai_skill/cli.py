"""Command-line interface for the PlantUML training-data pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .acquisition import acquire_source, ensure_generated_dirs, vendor_include_source
from .assets import init_assets
from .config import load_sources_config
from .constants import DEFAULT_JAR_PATH, PROJECT_ROOT
from .contact_sheet import write_png_mismatch_contact_sheet
from .doctor import run_doctor
from .extraction import extract_from_tree, extract_plantuml_blocks
from .includes import inline_resolved_includes, resolve_include_deps, unresolved_resolution_reason
from .license_policy import training_block_reason
from .manifest import CorpusRecord, read_jsonl, write_jsonl
from .recommendation_coverage import check_recommendation_coverage
from .renderer import PlantUMLRenderer, render_version_label
from .reporting import write_report
from .splits import build_splits
from .verify import png_average_hash, png_dimensions, png_hash_distance, png_perceptual_match, svg_hash, svg_matches


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
        "--include-root",
        action="append",
        default=[],
        help="local vendored include root; may be passed multiple times",
    )

    verify = sub.add_parser("verify", help="verify rendered SVG/PNG against published references")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--source-root", default="")
    verify.add_argument("--output", default=str(PROJECT_ROOT / "data" / "manifests" / "verified.jsonl"))

    audit = sub.add_parser("audit-licenses", help="summarize license families in a manifest")
    audit.add_argument("--manifest", required=True)

    splits = sub.add_parser("build-splits", help="build deterministic train/eval split manifests")
    splits.add_argument("--manifest", required=True)
    splits.add_argument("--output-dir", default=str(PROJECT_ROOT / "data" / "manifests" / "splits"))
    splits.add_argument("--synthetic-cap", type=int, default=5000)

    report = sub.add_parser("report", help="write a Markdown corpus report")
    report.add_argument("--manifest", required=True)
    report.add_argument("--output", default=str(PROJECT_ROOT / "data" / "reports" / "corpus-report.md"))

    contact = sub.add_parser("png-contact-sheet", help="write an HTML contact sheet for PNG mismatches")
    contact.add_argument("--manifest", required=True)
    contact.add_argument("--source-root", default="")
    contact.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "data" / "reports" / "png-mismatch-contact-sheet.html"),
    )

    coverage = sub.add_parser("coverage", help="check report recommendation coverage")
    coverage.add_argument("--config", default=str(PROJECT_ROOT / "config" / "sources.yml"))
    coverage.add_argument("--json", action="store_true")

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
            records = acquire_source(args.source, args.output, dry_run=args.dry_run)
            print(f"Wrote {len(records)} records to {args.output}")
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
        if args.command == "build-splits":
            return _build_splits(args)
        if args.command == "report":
            records = read_jsonl(args.manifest)
            path = write_report(records, args.output)
            print(f"Wrote report: {path}")
            return 0
        if args.command == "png-contact-sheet":
            records = read_jsonl(args.manifest)
            path, count = write_png_mismatch_contact_sheet(records, args.output, args.source_root or None)
            print(f"Wrote {count} PNG mismatch rows to {path}")
            return 0
        if args.command == "coverage":
            return _coverage(args)
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
    updated: list[CorpusRecord] = []
    for record in records:
        try:
            puml_path = _resolve_record_path(record, args.source_root)
            include_resolutions = (
                resolve_include_deps(record.include_deps, include_roots, puml_path.parent)
                if record.include_deps
                else []
            )
            include_reason = unresolved_resolution_reason(include_resolutions)
            if include_reason:
                record.render_status = "skipped"
                record.render_fail_reason = include_reason
                updated.append(record)
                continue
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
    write_jsonl(updated, args.output)
    failed = sum(record.render_status == "failed" for record in updated)
    rendered = sum(record.render_status == "ok" for record in updated)
    skipped = sum(record.render_status == "skipped" for record in updated)
    print(f"Rendered {rendered}/{len(updated)} records; skipped {skipped}; wrote {args.output}")
    return 0 if failed == 0 else 1


def _verify(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    updated: list[CorpusRecord] = []
    for record in records:
        try:
            if record.render_status == "failed":
                record.verification_status = "render_failed"
            elif record.render_status == "skipped":
                record.verification_status = "render_skipped"
            elif not record.published_render_path:
                record.verification_status = "rendered_no_reference" if record.render_hash_svg else "not_verified"
            else:
                reference_path = _resolve_reference_path(record, args.source_root)
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
                        "png_match"
                        if png_perceptual_match(rendered_bytes, reference_bytes)
                        else "png_mismatch"
                    )
                else:
                    record.verification_status = "unsupported_reference_format"
        except Exception as exc:
            record.verification_status = "verify_error"
            record.render_fail_reason = str(exc)
        updated.append(record)
    write_jsonl(updated, args.output)
    failures = sum(
        record.verification_status.endswith("mismatch") or record.verification_status == "verify_error"
        for record in updated
    )
    skipped = sum(record.verification_status in {"render_skipped", "render_failed"} for record in updated)
    checked = len(updated) - skipped
    print(f"Verified {checked - failures}/{checked} rendered records; skipped {skipped}; wrote {args.output}")
    return 0 if failures == 0 else 1


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


def _build_splits(args: argparse.Namespace) -> int:
    records = read_jsonl(args.manifest)
    splits = build_splits(records, args.output_dir, synthetic_cap=args.synthetic_cap)
    for name, split_records in sorted(splits.items()):
        print(f"{name}: {len(split_records)}")
    return 0


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
    return PROJECT_ROOT / "data" / "raw" / record.source_name / record.puml_path


def _resolve_reference_path(record: CorpusRecord, source_root: str) -> Path:
    if source_root:
        return Path(source_root) / record.published_render_path
    if record.source_name == "fixtures":
        return PROJECT_ROOT / "tests" / "fixtures" / record.published_render_path
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
