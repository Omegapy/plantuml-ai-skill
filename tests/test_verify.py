from pathlib import Path
import struct
import unittest
import zlib

from plantuml_ai_skill.verify import png_perceptual_match, svg_hash, svg_matches


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


if __name__ == "__main__":
    unittest.main()
