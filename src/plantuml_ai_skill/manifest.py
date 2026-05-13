"""Manifest data model and JSONL helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable


REQUIRED_RECORD_FIELDS = [
    "id",
    "source_name",
    "source_url",
    "source_kind",
    "source_ref",
    "license",
    "license_family",
    "diagram_type",
    "puml_path",
    "published_render_path",
    "python_source_paths",
    "include_deps",
    "is_self_contained",
    "uses_include",
    "uses_icon_library",
    "plantuml_version",
    "graphviz_version",
    "render_status",
    "render_hash_svg",
    "render_hash_png",
    "verification_status",
    "render_fail_reason",
    "purpose",
]


@dataclass
class CorpusRecord:
    """One row in the PlantUML corpus manifest."""

    id: str
    source_name: str
    source_url: str
    source_kind: str
    source_ref: str
    license: str
    license_family: str
    diagram_type: str
    puml_path: str
    published_render_path: str
    python_source_paths: list[str]
    include_deps: list[str]
    is_self_contained: bool
    uses_include: bool
    uses_icon_library: bool
    plantuml_version: str
    graphviz_version: str
    render_status: str
    render_hash_svg: str
    render_hash_png: str
    verification_status: str
    render_fail_reason: str
    purpose: list[str]
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "CorpusRecord":
        validate_record_mapping(data)
        known = {field.name for field in cls.__dataclass_fields__.values()}
        payload = {key: value for key, value in data.items() if key in known}
        payload["python_source_paths"] = list(payload["python_source_paths"])
        payload["include_deps"] = list(payload["include_deps"])
        payload["purpose"] = list(payload["purpose"])
        payload["is_self_contained"] = bool(payload["is_self_contained"])
        payload["uses_include"] = bool(payload["uses_include"])
        payload["uses_icon_library"] = bool(payload["uses_icon_library"])
        payload.setdefault("extra", {})
        return cls(**payload)

    def to_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.update(payload.pop("extra", {}))
        return payload


def validate_record_mapping(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_RECORD_FIELDS if field not in data]
    if missing:
        raise ValueError(f"manifest record is missing fields: {', '.join(missing)}")
    list_fields = {"python_source_paths", "include_deps", "purpose"}
    bool_fields = {"is_self_contained", "uses_include", "uses_icon_library"}
    for field_name in list_fields:
        if not isinstance(data[field_name], list):
            raise TypeError(f"{field_name} must be a list")
    for field_name in bool_fields:
        if not isinstance(data[field_name], bool):
            raise TypeError(f"{field_name} must be a boolean")
    for field_name in set(REQUIRED_RECORD_FIELDS) - list_fields - bool_fields:
        if not isinstance(data[field_name], str):
            raise TypeError(f"{field_name} must be a string")


def read_jsonl(path: Path | str) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        return records
    for line_number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(CorpusRecord.from_mapping(json.loads(line)))
        except Exception as exc:  # pragma: no cover - message context is the point
            raise ValueError(f"{jsonl_path}:{line_number}: invalid manifest row: {exc}") from exc
    return records


def write_jsonl(records: Iterable[CorpusRecord], path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(record.to_mapping(), sort_keys=True) for record in records]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output_path
