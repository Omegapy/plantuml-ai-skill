"""Markdown reporting for corpus manifests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .license_policy import training_block_reason
from .manifest import CorpusRecord


def summarize_records(records: list[CorpusRecord]) -> dict[str, Counter[str]]:
    return {
        "sources": Counter(record.source_name for record in records),
        "licenses": Counter(record.license_family for record in records),
        "diagram_types": Counter(record.diagram_type for record in records),
        "render_status": Counter(record.render_status for record in records),
        "verification_status": Counter(record.verification_status for record in records),
        "curation_status": Counter(
            str(record.extra["curation_status"]) for record in records if record.extra.get("curation_status")
        ),
        "purposes": Counter(purpose for record in records for purpose in record.purpose),
    }


def markdown_report(records: list[CorpusRecord], title: str = "PlantUML Corpus Report") -> str:
    summary = summarize_records(records)
    lines = [f"# {title}", "", f"Total records: **{len(records)}**", ""]
    for section, counter in summary.items():
        lines.append(f"## {section.replace('_', ' ').title()}")
        if not counter:
            lines.append("- none")
        else:
            for key, value in sorted(counter.items()):
                lines.append(f"- `{key}`: {value}")
        lines.append("")
    lines.extend(_diagnostics_section(records))
    lines.extend(_source_conditioned_section(records))
    return "\n".join(lines)


def write_report(
    records: list[CorpusRecord],
    output_path: Path | str,
    title: str = "PlantUML Corpus Report",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_report(records, title=title), encoding="utf-8")
    return path


def render_failure_report(records: list[CorpusRecord]) -> str:
    """Return a compact TSV report for failed or skipped renders."""

    rows = [
        [
            record.source_ref,
            record.puml_path,
            record.render_status,
            " ".join(record.render_fail_reason.split()),
        ]
        for record in records
        if record.render_status in {"failed", "skipped"}
    ]
    lines = ["source_ref\tpuml_path\trender_status\trender_fail_reason"]
    lines.extend("\t".join(_tsv_cell(value) for value in row) for row in rows)
    return "\n".join(lines) + "\n"


def write_render_failure_report(records: list[CorpusRecord], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_failure_report(records), encoding="utf-8")
    return path


def render_failure_triage_report(records: list[CorpusRecord]) -> str:
    """Return a conservative TSV triage report for failed or skipped renders."""

    header = [
        "source_ref",
        "puml_path",
        "license_family",
        "render_status",
        "failure_class",
        "actionability",
        "recommended_action",
        "render_fail_reason",
    ]
    rows = []
    for record in records:
        if record.render_status not in {"failed", "skipped"}:
            continue
        failure_class, actionability, recommended_action = classify_render_failure(record)
        rows.append(
            [
                record.source_ref,
                record.puml_path,
                record.license_family,
                record.render_status,
                failure_class,
                actionability,
                recommended_action,
                _normalized_reason(record.render_fail_reason),
            ]
        )
    lines = ["\t".join(header)]
    lines.extend("\t".join(_tsv_cell(value) for value in row) for row in rows)
    return "\n".join(lines) + "\n"


def write_render_failure_triage_report(records: list[CorpusRecord], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_failure_triage_report(records), encoding="utf-8")
    return path


def render_failure_summary_report(records: list[CorpusRecord]) -> str:
    """Return grouped TSV counts for failed or skipped renders."""

    groups: Counter[tuple[str, str, str, str, str]] = Counter()
    statuses: dict[tuple[str, str, str, str, str], Counter[str]] = {}
    for record in records:
        if record.render_status not in {"failed", "skipped"}:
            continue
        failure_class, actionability, recommended_action = classify_render_failure(record)
        key = (
            record.license_family,
            record.source_ref,
            failure_class,
            actionability,
            recommended_action,
        )
        groups[key] += 1
        statuses.setdefault(key, Counter())[record.render_status] += 1

    header = [
        "count",
        "license_family",
        "source_ref",
        "render_failed",
        "render_skipped",
        "failure_class",
        "actionability",
        "recommended_action",
    ]
    lines = ["\t".join(header)]
    rows = sorted(groups.items(), key=lambda item: (-item[1], item[0]))
    for key, count in rows:
        license_family, source_ref, failure_class, actionability, recommended_action = key
        status_counts = statuses[key]
        lines.append(
            "\t".join(
                _tsv_cell(value)
                for value in [
                    count,
                    license_family,
                    source_ref,
                    status_counts["failed"],
                    status_counts["skipped"],
                    failure_class,
                    actionability,
                    recommended_action,
                ]
            )
        )
    return "\n".join(lines) + "\n"


def write_render_failure_summary_report(records: list[CorpusRecord], output_path: Path | str) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_failure_summary_report(records), encoding="utf-8")
    return path


def classify_render_failure(record: CorpusRecord) -> tuple[str, str, str]:
    """Classify a render failure without changing corpus eligibility."""

    failure_class = _failure_class(record)
    if record.license_family != "permissive":
        return (
            failure_class,
            "blocked_by_license",
            "leave excluded unless the upstream license is directly reviewed as permissive",
        )
    if failure_class == "dot_inside_startuml":
        return (
            failure_class,
            "not_recoverable_as_plantuml",
            "leave failed or mark invalid upstream; do not rewrite DOT into train",
        )
    if failure_class == "unsupported_remote_include":
        return (
            failure_class,
            "potentially_recoverable_with_audited_vendor_includes",
            "vendor exact remote dependencies only after license review; do not fetch dynamically",
        )
    if failure_class == "missing_local_include":
        return (
            failure_class,
            "potentially_recoverable_with_local_include_root",
            "add an auditable local include root only if the dependency is already acquired",
        )
    if failure_class == "empty_diagram":
        return (
            failure_class,
            "not_recoverable_empty_upstream",
            "leave excluded as an empty upstream diagram",
        )
    return (
        failure_class,
        "needs_manual_syntax_review",
        "leave failed unless upstream syntax renders under the pinned renderer without repair",
    )


def _diagnostics_section(records: list[CorpusRecord]) -> list[str]:
    groups: list[tuple[str, str, str, list[tuple[CorpusRecord, str]]]] = [
        (
            "trusted_remote_includes_mirrored",
            "trusted C4 remote include mapped to the pinned local vendor snapshot",
            "eligible for normal render triage; keep the mirror rule auditable",
            [
                (record, ", ".join(record.extra.get("mirrored_include_deps", [])))
                for record in records
                if record.extra.get("include_resolution_status") == "trusted_remote_mirrored"
            ],
        ),
        (
            "remote_include_blocked",
            "valid PlantUML but unsupported remote include dependency",
            "exclude until the include is vendored or explicitly mapped",
            [
                (record, ", ".join(record.include_deps) or record.render_fail_reason)
                for record in records
                if record.render_fail_reason == "remote_include_blocked"
            ],
        ),
        (
            "include_resolution_required",
            "valid PlantUML with a local include that was not resolved",
            "exclude until an include root or vendored file is added",
            [
                (record, ", ".join(record.include_deps) or record.render_fail_reason)
                for record in records
                if record.render_fail_reason in {"include_resolution_required", "include_roots_not_configured"}
            ],
        ),
        (
            "renderer_failures",
            "syntax incompatibility or renderer failure under the pinned renderer",
            "exclude pending manual syntax triage",
            [
                (record, _diagnostic_detail(record, record.render_fail_reason))
                for record in records
                if record.render_status == "failed"
            ],
        ),
        (
            "png_svg_mismatches",
            "published image differs from the pinned renderer output",
            "use explicit curation; only minor acceptable drift enters gold evaluation",
            [
                (record, _visual_mismatch_detail(record))
                for record in records
                if record.verification_status in {"png_mismatch", "svg_mismatch"}
            ],
        ),
        (
            "ambiguous_image_references",
            "Markdown image reference could not be paired unambiguously",
            "leave reference empty or pair manually before promotion",
            [
                (record, str(record.extra.get("published_render_pairing_status", "")))
                for record in records
                if str(record.extra.get("published_render_pairing_status", "")).startswith("ambiguous")
            ],
        ),
        (
            "license_policy_exclusions",
            "record is marked for training but blocked by license policy",
            "exclude from training unless row-level licensing is resolved",
            [
                (record, training_block_reason(record.license, record.purpose))
                for record in records
                if "training" in record.purpose and training_block_reason(record.license, record.purpose)
            ],
        ),
    ]

    lines = ["## Diagnostics", ""]
    for title, root_cause, disposition, rows in groups:
        lines.append(f"### {title}")
        if not rows:
            lines.append("- none")
            lines.append("")
            continue
        lines.extend(
            _markdown_table(
                ["Record", "Path", "Status", "Root Cause", "Recommended Disposition", "Detail"],
                [
                    [
                        f"`{record.id}`",
                        f"`{record.puml_path}`",
                        _status_label(record),
                        root_cause,
                        disposition,
                        detail,
                    ]
                    for record, detail in rows
                ],
            )
        )
        lines.append("")
    return lines


def _source_conditioned_section(records: list[CorpusRecord]) -> list[str]:
    paired = [record for record in records if record.python_source_paths]
    lines = ["## Source-Conditioned Pairings", ""]
    if not paired:
        lines.append("- none")
        lines.append("")
        return lines
    lines.extend(
        _markdown_table(
            ["Record", "Expected PUML", "Python Sources", "Render", "Confidence"],
            [
                [
                    f"`{record.id}`",
                    f"`{record.puml_path}`",
                    _source_paths_cell(record.python_source_paths),
                    record.render_status,
                    str(record.extra.get("source_pairing_confidence", "unspecified")),
                ]
                for record in paired
            ],
        )
    )
    lines.append("")
    return lines


def _status_label(record: CorpusRecord) -> str:
    return f"{record.render_status}/{record.verification_status}"


def _source_paths_cell(paths: list[str]) -> str:
    if len(paths) <= 3:
        return ", ".join(f"`{path}`" for path in paths)
    shown = ", ".join(f"`{path}`" for path in paths[:3])
    return f"{shown}, +{len(paths) - 3} more"


def _visual_mismatch_detail(record: CorpusRecord) -> str:
    parts = [record.published_render_path]
    if record.extra.get("png_hash_distance"):
        parts.append(f"hash_distance={record.extra['png_hash_distance']}")
    if record.extra.get("published_png_dimensions") and record.extra.get("rendered_png_dimensions"):
        parts.append(
            "dimensions="
            f"{record.extra['published_png_dimensions']} published/"
            f"{record.extra['rendered_png_dimensions']} rendered"
        )
    parts.extend(_curation_parts(record))
    return "; ".join(parts)


def _diagnostic_detail(record: CorpusRecord, detail: str) -> str:
    clean_detail = " ".join(detail.split()) if detail else ""
    parts = [clean_detail] if clean_detail else []
    parts.extend(_curation_parts(record))
    return "; ".join(parts)


def _failure_class(record: CorpusRecord) -> str:
    reason = _normalized_reason(record.render_fail_reason).lower()
    if "remote_include_blocked" in reason:
        return "unsupported_remote_include"
    if "include_resolution_required" in reason or "include_roots_not_configured" in reason:
        return "missing_local_include"
    if "this looks like a dot diagram" in reason or "use @startdot" in reason:
        return "dot_inside_startuml"
    if "empty description" in reason:
        return "empty_diagram"
    if "cannot find group" in reason or "cannot find if" in reason or "(assumed diagram type: activity)" in reason:
        return "activity_syntax"
    if "map definition should contains key" in reason:
        return "map_syntax"
    if "(assumed diagram type: state)" in reason:
        return "state_syntax"
    if "(assumed diagram type: class)" in reason:
        return "class_syntax"
    if "syntax error" in reason and record.uses_include:
        return "include_macro_or_syntax"
    if "syntax error" in reason:
        return "syntax_error"
    return "unknown_renderer_failure"


def _normalized_reason(reason: str) -> str:
    return " ".join(reason.split())


def _curation_parts(record: CorpusRecord) -> list[str]:
    if not record.extra.get("curation_status"):
        return []
    parts = [f"reviewed={record.extra['curation_status']}"]
    if record.extra.get("curation_rationale"):
        parts.append(f"rationale={record.extra['curation_rationale']}")
    if record.extra.get("curation_reviewer") and record.extra.get("curation_reviewed_at"):
        parts.append(f"by={record.extra['curation_reviewer']}@{record.extra['curation_reviewed_at']}")
    elif record.extra.get("curation_reviewer"):
        parts.append(f"by={record.extra['curation_reviewer']}")
    elif record.extra.get("curation_reviewed_at"):
        parts.append(f"reviewed_at={record.extra['curation_reviewed_at']}")
    return parts


def _markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    table = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        table.append("| " + " | ".join(_escape_table_cell(value) for value in row) + " |")
    return table


def _escape_table_cell(value: str) -> str:
    clean = " ".join(str(value).split())
    if len(clean) > 160:
        clean = clean[:157] + "..."
    return clean.replace("|", "\\|")


def _tsv_cell(value: str) -> str:
    return " ".join(str(value).split()).replace("\t", " ")
