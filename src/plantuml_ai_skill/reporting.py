"""Markdown reporting for corpus manifests."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

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
    unresolved = [record for record in records if record.render_fail_reason]
    lines.append("## Render Failures")
    if unresolved:
        for record in unresolved:
            lines.append(f"- `{record.id}`: {record.render_fail_reason}")
    else:
        lines.append("- none")
    lines.append("")
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
