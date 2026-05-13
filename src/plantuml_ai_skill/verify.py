"""SVG and PNG verification helpers."""

from __future__ import annotations

import hashlib
import re
import struct
import xml.etree.ElementTree as ET
import zlib


def _strip_unstable_svg_text(svg: str) -> str:
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r'id="[^"]+"', 'id=""', svg)
    svg = re.sub(r'clip-path="url\(#.*?\)"', 'clip-path="url(#)"', svg)
    svg = re.sub(r'url\(#.*?\)', 'url(#)', svg)
    svg = re.sub(r'\s+xmlns:xlink="[^"]*"', "", svg)
    return svg.strip()


def normalize_svg(svg: str | bytes) -> bytes:
    """Normalize SVG while preserving document order."""

    text = svg.decode("utf-8", errors="replace") if isinstance(svg, bytes) else svg
    root = ET.fromstring(_strip_unstable_svg_text(text))

    def normalize_element(element: ET.Element) -> None:
        element.attrib = dict(sorted(element.attrib.items()))
        if element.text:
            element.text = " ".join(element.text.split())
        if element.tail:
            element.tail = " ".join(element.tail.split())
        for child in list(element):
            normalize_element(child)

    normalize_element(root)
    return ET.tostring(root, encoding="utf-8")


def svg_hash(svg: str | bytes) -> str:
    return hashlib.sha256(normalize_svg(svg)).hexdigest()


def svg_matches(left: str | bytes, right: str | bytes) -> bool:
    return svg_hash(left) == svg_hash(right)


def png_average_hash(png_bytes: bytes, hash_size: int = 8) -> int:
    """Compute a small average hash for simple 8-bit PNG files.

    This stdlib implementation supports the PNG variants emitted by PlantUML in
    normal operation: 8-bit grayscale, RGB, or RGBA. It is intentionally small
    and used only as a fallback when SVG references are unavailable.
    """

    width, height, pixels = _decode_png_grayscale(png_bytes)
    if width == 0 or height == 0:
        raise ValueError("empty PNG")
    samples: list[int] = []
    for y in range(hash_size):
        source_y = min(height - 1, int((y + 0.5) * height / hash_size))
        for x in range(hash_size):
            source_x = min(width - 1, int((x + 0.5) * width / hash_size))
            samples.append(pixels[source_y * width + source_x])
    average = sum(samples) / len(samples)
    bits = 0
    for value in samples:
        bits = (bits << 1) | int(value >= average)
    return bits


def png_hash_distance(left: bytes, right: bytes) -> int:
    return (png_average_hash(left) ^ png_average_hash(right)).bit_count()


def png_perceptual_match(left: bytes, right: bytes, max_distance: int = 5) -> bool:
    return png_hash_distance(left, right) <= max_distance


def _decode_png_grayscale(png_bytes: bytes) -> tuple[int, int, list[int]]:
    if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG file")
    offset = 8
    width = height = 0
    color_type = -1
    bit_depth = -1
    palette: list[tuple[int, int, int]] = []
    idat = bytearray()
    while offset < len(png_bytes):
        length = struct.unpack(">I", png_bytes[offset : offset + 4])[0]
        chunk_type = png_bytes[offset + 4 : offset + 8]
        chunk_data = png_bytes[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"PLTE":
            palette = [
                (chunk_data[index], chunk_data[index + 1], chunk_data[index + 2])
                for index in range(0, len(chunk_data), 3)
            ]
        elif chunk_type == b"IEND":
            break
    if bit_depth != 8 or color_type not in {0, 2, 3, 6}:
        raise ValueError(f"unsupported PNG bit depth/color type: {bit_depth}/{color_type}")
    if color_type == 3 and not palette:
        raise ValueError("indexed PNG is missing PLTE palette")
    bytes_per_pixel = {0: 1, 2: 3, 3: 1, 6: 4}[color_type]
    raw = zlib.decompress(bytes(idat))
    row_size = width * bytes_per_pixel
    rows: list[bytes] = []
    cursor = 0
    previous = bytes(row_size)
    for _ in range(height):
        filter_type = raw[cursor]
        cursor += 1
        scanline = bytearray(raw[cursor : cursor + row_size])
        cursor += row_size
        _unfilter(scanline, previous, bytes_per_pixel, filter_type)
        rows.append(bytes(scanline))
        previous = bytes(scanline)
    grayscale: list[int] = []
    for row in rows:
        for x in range(width):
            base = x * bytes_per_pixel
            if color_type == 0:
                grayscale.append(row[base])
            elif color_type == 3:
                index = row[base]
                if index >= len(palette):
                    raise ValueError(f"indexed PNG palette index out of range: {index}")
                r, g, b = palette[index]
                grayscale.append(int(0.299 * r + 0.587 * g + 0.114 * b))
            else:
                r, g, b = row[base], row[base + 1], row[base + 2]
                grayscale.append(int(0.299 * r + 0.587 * g + 0.114 * b))
    return width, height, grayscale


def _unfilter(scanline: bytearray, previous: bytes, bpp: int, filter_type: int) -> None:
    for index in range(len(scanline)):
        left = scanline[index - bpp] if index >= bpp else 0
        up = previous[index]
        up_left = previous[index - bpp] if index >= bpp else 0
        if filter_type == 0:
            prediction = 0
        elif filter_type == 1:
            prediction = left
        elif filter_type == 2:
            prediction = up
        elif filter_type == 3:
            prediction = (left + up) // 2
        elif filter_type == 4:
            prediction = _paeth(left, up, up_left)
        else:
            raise ValueError(f"unsupported PNG filter type: {filter_type}")
        scanline[index] = (scanline[index] + prediction) & 0xFF


def _paeth(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left
