from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from plantuml_ai_skill.contact_sheet import write_png_mismatch_contact_sheet
from plantuml_ai_skill.manifest import CorpusRecord


def tiny_png(gray: int) -> bytes:
    width = height = 1
    raw = bytes([0, gray, gray, gray])
    compressed = zlib.compress(raw)

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


class ContactSheetTests(unittest.TestCase):
    def test_contact_sheet_copies_png_mismatch_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            rendered = root / "rendered"
            source.mkdir()
            rendered.mkdir()
            (source / "published.png").write_bytes(tiny_png(200))
            rendered_path = rendered / "record-1.png"
            rendered_path.write_bytes(tiny_png(100))
            record = CorpusRecord(
                id="record-1",
                source_name="local",
                source_url=str(source),
                source_kind="local",
                source_ref="local",
                license="MIT",
                license_family="permissive",
                diagram_type="class",
                puml_path="diagram.puml",
                published_render_path="published.png",
                python_source_paths=[],
                include_deps=[],
                is_self_contained=True,
                uses_include=False,
                uses_icon_library=False,
                plantuml_version="test",
                graphviz_version="",
                render_status="ok",
                render_hash_svg="hash",
                render_hash_png="hash",
                verification_status="png_mismatch",
                render_fail_reason="",
                purpose=["gold_eval"],
                attribution="local",
                license_path="",
                source_commit="local",
                source_repo_url=str(source),
                extra={
                    "rendered_png_path": str(rendered_path),
                    "png_hash_distance": "10",
                    "published_png_dimensions": "1x1",
                    "rendered_png_dimensions": "1x1",
                },
            )
            output, count = write_png_mismatch_contact_sheet(
                [record],
                root / "report" / "contact.html",
                source,
            )
            html = output.read_text(encoding="utf-8")
            assets = output.parent / "contact_assets"
            self.assertEqual(1, count)
            self.assertIn("record-1", html)
            self.assertTrue((assets / "record-1-reference.png").exists())
            self.assertTrue((assets / "record-1-rendered.png").exists())


if __name__ == "__main__":
    unittest.main()
