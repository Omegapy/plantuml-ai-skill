"""Pinned PlantUML asset initialization."""

from __future__ import annotations

import json
from pathlib import Path
import urllib.request

from .constants import (
    DEFAULT_ASSET_DIR,
    PLANTUML_JAR_NAME,
    PLANTUML_JAR_SHA256,
    PLANTUML_JAR_URL,
    PLANTUML_VERSION,
)
from .renderer import sha256_file


def init_assets(asset_dir: Path | str = DEFAULT_ASSET_DIR, force: bool = False) -> Path:
    """Download and verify the pinned PlantUML jar."""

    target_dir = Path(asset_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    jar_path = target_dir / PLANTUML_JAR_NAME
    if jar_path.exists() and not force:
        verify_asset(jar_path)
        write_asset_metadata(target_dir, jar_path)
        return jar_path

    temp_path = jar_path.with_suffix(".jar.tmp")
    with urllib.request.urlopen(PLANTUML_JAR_URL, timeout=60) as response:
        temp_path.write_bytes(response.read())
    temp_path.replace(jar_path)
    verify_asset(jar_path)
    write_asset_metadata(target_dir, jar_path)
    return jar_path


def verify_asset(jar_path: Path | str) -> None:
    digest = sha256_file(jar_path)
    if digest != PLANTUML_JAR_SHA256:
        raise ValueError(
            f"PlantUML jar checksum mismatch: expected {PLANTUML_JAR_SHA256}, got {digest}"
        )


def write_asset_metadata(asset_dir: Path, jar_path: Path) -> Path:
    metadata_path = asset_dir / "plantuml-asset.json"
    payload = {
        "plantuml_version": PLANTUML_VERSION,
        "jar_name": jar_path.name,
        "jar_url": PLANTUML_JAR_URL,
        "sha256": PLANTUML_JAR_SHA256,
    }
    metadata_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return metadata_path
