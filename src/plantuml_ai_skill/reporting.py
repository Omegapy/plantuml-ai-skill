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


def _diagnostics_section(records: list[CorpusRecord]) -> list[str]:
    groups: list[tuple[str, str, str, list[tuple[CorpusRecord, str]]]] = [
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
                (record, record.render_fail_reason)
                for record in records
                if record.render_status == "failed"
            ],
        ),
        (
            "png_svg_mismatches",
            "published image differs from the pinned renderer output",
            "exclude from trusted visual regression until reviewed or rebaselined",
            [
                (record, record.published_render_path)
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
