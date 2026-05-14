from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from plantuml_ai_skill.cli import main
from plantuml_ai_skill.manifest import CorpusRecord, read_jsonl, write_jsonl
from plantuml_ai_skill.verify import png_dimensions, png_perceptual_match, svg_hash, svg_matches


ROOT = Path(__file__).resolve().parents[1]


def tiny_png(gray: int) -> bytes:
    width = height = 2
    raw = bytearray()
    for _ in range(height):
        raw.append(0)
        raw.extend([gray, gray, gray] * width)
    compressed = zlib.compress(bytes(raw))

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


class VerifyTests(unittest.TestCase):
    def test_svg_normalization_ignores_ids_comments_and_attribute_order(self) -> None:
        left = (ROOT / "tests" / "fixtures" / "svg" / "reference.svg").read_text()
        right = (ROOT / "tests" / "fixtures" / "svg" / "reference_same.svg").read_text()
        self.assertEqual(svg_hash(left), svg_hash(right))
        self.assertTrue(svg_matches(left, right))

    def test_svg_normalization_preserves_xlink_namespace(self) -> None:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:xlink="http://www.w3.org/1999/xlink">'
            '<image xlink:href="data:image/png;base64,AAAA"/></svg>'
        )
        self.assertTrue(svg_hash(svg))

    def test_png_average_hash_fallback_matches_similar_simple_pngs(self) -> None:
        self.assertTrue(png_perceptual_match(tiny_png(200), tiny_png(201)))
        self.assertEqual((2, 2), png_dimensions(tiny_png(200)))

    def test_parallel_cli_verify_matches_serial_and_preserves_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest, source = _write_verify_fixture_manifest(tmp_path)
            serial_output = tmp_path / "serial.jsonl"
            parallel_output = tmp_path / "parallel.jsonl"

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                serial_status = main(
                    [
                        "verify",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(source),
                        "--output",
                        str(serial_output),
                        "--workers",
                        "1",
                    ]
                )
                parallel_status = main(
                    [
                        "verify",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(source),
                        "--output",
                        str(parallel_output),
                        "--workers",
                        "2",
                        "--chunk-size",
                        "1",
                    ]
                )

            serial_records = read_jsonl(serial_output)
            parallel_records = read_jsonl(parallel_output)

        self.assertEqual(serial_status, parallel_status)
        self.assertEqual(
            [record.to_mapping() for record in serial_records],
            [record.to_mapping() for record in parallel_records],
        )
        self.assertEqual(
            ["order-c-png", "order-a-svg", "order-b-failed", "order-d-skipped"],
            [record.id for record in parallel_records],
        )
        self.assertEqual(
            ["png_match", "svg_mismatch", "render_failed", "render_skipped"],
            [record.verification_status for record in parallel_records],
        )

    def test_workers_one_cli_verify_remains_serial_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source"
            rendered = tmp_path / "rendered"
            source.mkdir()
            rendered.mkdir()
            (source / "reference.svg").write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>',
                encoding="utf-8",
            )
            rendered_svg = rendered / "rendered.svg"
            rendered_svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>',
                encoding="utf-8",
            )
            manifest = tmp_path / "manifest.jsonl"
            output = tmp_path / "output.jsonl"
            write_jsonl([_fixture_record("serial-one", source, "reference.svg", rendered_svg)], manifest)

            stdout = StringIO()
            stderr = StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = main(
                    [
                        "verify",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(source),
                        "--output",
                        str(output),
                        "--workers",
                        "1",
                    ]
                )
            records = read_jsonl(output)

        self.assertEqual(0, status)
        self.assertEqual("svg_match", records[0].verification_status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("Verified 1/1 rendered records", stdout.getvalue())

    def test_progress_output_goes_to_stderr_and_jsonl_stays_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest, source = _write_verify_fixture_manifest(tmp_path)
            output = tmp_path / "parallel.jsonl"
            stdout = StringIO()
            stderr = StringIO()

            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = main(
                    [
                        "verify",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(source),
                        "--output",
                        str(output),
                        "--workers",
                        "2",
                        "--chunk-size",
                        "1",
                    ]
                )
            jsonl_lines = output.read_text(encoding="utf-8").splitlines()

        self.assertEqual(1, status)
        self.assertIn("verify progress:", stderr.getvalue())
        self.assertNotIn("verify progress:", stdout.getvalue())
        self.assertEqual(4, len(jsonl_lines))
        for line in jsonl_lines:
            json.loads(line)

    def test_parallel_verify_errors_become_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source"
            rendered = tmp_path / "rendered"
            source.mkdir()
            rendered.mkdir()
            (source / "reference.png").write_bytes(tiny_png(200))
            rendered_png = rendered / "bad.png"
            rendered_png.write_bytes(b"not-png")
            manifest = tmp_path / "manifest.jsonl"
            output = tmp_path / "output.jsonl"
            write_jsonl([_fixture_record("bad-png", source, "reference.png", rendered_png)], manifest)

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                status = main(
                    [
                        "verify",
                        "--manifest",
                        str(manifest),
                        "--source-root",
                        str(source),
                        "--output",
                        str(output),
                        "--workers",
                        "2",
                        "--chunk-size",
                        "1",
                    ]
                )
            records = read_jsonl(output)

        self.assertEqual(1, status)
        self.assertEqual("verify_error", records[0].verification_status)
        self.assertIn("not a PNG file", records[0].render_fail_reason)


def _write_verify_fixture_manifest(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    rendered = tmp_path / "rendered"
    source.mkdir()
    rendered.mkdir()
    (source / "reference.png").write_bytes(tiny_png(200))
    (source / "reference.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>A</text></svg>',
        encoding="utf-8",
    )
    rendered_png = rendered / "rendered.png"
    rendered_png.write_bytes(tiny_png(200))
    rendered_svg = rendered / "rendered.svg"
    rendered_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"><text>B</text></svg>',
        encoding="utf-8",
    )
    records = [
        _fixture_record("order-c-png", source, "reference.png", rendered_png),
        _fixture_record("order-a-svg", source, "reference.svg", rendered_svg),
        _fixture_record("order-b-failed", source, "reference.svg", rendered_svg, render_status="failed"),
        _fixture_record("order-d-skipped", source, "reference.svg", rendered_svg, render_status="skipped"),
    ]
    manifest = tmp_path / "manifest.jsonl"
    write_jsonl(records, manifest)
    return manifest, source


def _fixture_record(
    record_id: str,
    source: Path,
    published_render_path: str,
    rendered_path: Path,
    render_status: str = "ok",
) -> CorpusRecord:
    suffix = rendered_path.suffix.lower().lstrip(".")
    return CorpusRecord(
        id=record_id,
        source_name="local",
        source_url=str(source),
        source_kind="local",
        source_ref="local",
        license="MIT",
        license_family="permissive",
        diagram_type="sequence",
        puml_path=f"{record_id}.puml",
        published_render_path=published_render_path,
        python_source_paths=[],
        include_deps=[],
        is_self_contained=True,
        uses_include=False,
        uses_icon_library=False,
        plantuml_version="",
        graphviz_version="",
        render_status=render_status,
        render_hash_svg="rendered" if render_status == "ok" else "",
        render_hash_png="",
        verification_status="not_verified",
        render_fail_reason="already failed" if render_status == "failed" else "",
        purpose=["gold_eval"],
        attribution="local",
        license_path="",
        source_commit="local",
        source_repo_url=str(source),
        extra={f"rendered_{suffix}_path": str(rendered_path)},
    )


if __name__ == "__main__":
    unittest.main()
