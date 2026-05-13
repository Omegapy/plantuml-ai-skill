"""Curator contact sheets for visual verification failures."""

from __future__ import annotations

from html import escape
from pathlib import Path
import shutil

from .constants import PROJECT_ROOT
from .manifest import CorpusRecord


def write_png_mismatch_contact_sheet(
    records: list[CorpusRecord],
    output_path: Path | str,
    source_root: Path | str | None = None,
) -> tuple[Path, int]:
    """Write an HTML side-by-side sheet for PNG mismatches."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = output.with_suffix("").parent / f"{output.with_suffix('').name}_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    rows: list[str] = []
    count = 0
    for record in records:
        if record.verification_status != "png_mismatch":
            continue
        reference_path = _reference_path(record, source_root)
        rendered_path = _rendered_path(record)
        if not reference_path.exists() or not rendered_path.exists():
            continue
        count += 1
        reference_asset = asset_dir / f"{record.id}-reference.png"
        rendered_asset = asset_dir / f"{record.id}-rendered.png"
        shutil.copy2(reference_path, reference_asset)
        shutil.copy2(rendered_path, rendered_asset)
        rows.append(_row_html(record, reference_asset.relative_to(output.parent), rendered_asset.relative_to(output.parent)))

    output.write_text(_page_html(rows), encoding="utf-8")
    return output, count


def _row_html(record: CorpusRecord, reference_src: Path, rendered_src: Path) -> str:
    detail = " | ".join(
        item
        for item in (
            f"distance {record.extra.get('png_hash_distance')}" if record.extra.get("png_hash_distance") else "",
            f"published {record.extra.get('published_png_dimensions')}"
            if record.extra.get("published_png_dimensions")
            else "",
            f"rendered {record.extra.get('rendered_png_dimensions')}" if record.extra.get("rendered_png_dimensions") else "",
        )
        if item
    )
    return (
        "<tr>"
        f"<td><code>{escape(record.id)}</code><br><code>{escape(record.puml_path)}</code><br>{escape(detail)}</td>"
        f'<td><img src="{escape(reference_src.as_posix())}" alt="published reference"></td>'
        f'<td><img src="{escape(rendered_src.as_posix())}" alt="rendered output"></td>'
        "</tr>"
    )


def _page_html(rows: list[str]) -> str:
    body = "\n".join(rows) if rows else '<tr><td colspan="3">No PNG mismatches.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PlantUML PNG Mismatch Contact Sheet</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; vertical-align: top; }}
    th {{ background: #f6f8fa; text-align: left; }}
    img {{ max-width: 520px; height: auto; background: white; }}
    code {{ font-size: 12px; }}
  </style>
</head>
<body>
  <h1>PlantUML PNG Mismatch Contact Sheet</h1>
  <table>
    <thead><tr><th>Record</th><th>Published Reference</th><th>Rendered Output</th></tr></thead>
    <tbody>
{body}
    </tbody>
  </table>
</body>
</html>
"""


def _reference_path(record: CorpusRecord, source_root: Path | str | None) -> Path:
    if source_root:
        return Path(source_root) / record.published_render_path
    if record.source_name == "fixtures":
        return PROJECT_ROOT / "tests" / "fixtures" / record.published_render_path
    return PROJECT_ROOT / "data" / "raw" / record.source_name / record.published_render_path


def _rendered_path(record: CorpusRecord) -> Path:
    if "rendered_png_path" in record.extra:
        return Path(str(record.extra["rendered_png_path"]))
    return PROJECT_ROOT / "data" / "rendered" / f"{record.id}.png"
