"""Source registry loading.

The project keeps ``config/sources.yml`` as JSON-valid YAML so it can be read
with the Python standard library. This avoids making a YAML parser a hard
runtime dependency for the core skill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

from .constants import DEFAULT_SOURCES_CONFIG, REPORT_RECOMMENDED_FEATURES


@dataclass(frozen=True)
class SourceDefinition:
    """A single training-data source from the registry."""

    id: str
    name: str
    url: str
    kind: str
    priority: int
    default_purpose: list[str]
    license_policy: str
    acquisition_mode: str
    pin_strategy: str
    expected_diagram_families: list[str]
    allowed_split_targets: list[str]
    ref: str = ""
    notes: str = ""
    seed_urls: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "SourceDefinition":
        required = {
            "id",
            "name",
            "url",
            "kind",
            "priority",
            "default_purpose",
            "license_policy",
            "acquisition_mode",
            "pin_strategy",
            "expected_diagram_families",
            "allowed_split_targets",
        }
        missing = sorted(required - data.keys())
        if missing:
            raise ValueError(f"source definition is missing keys: {', '.join(missing)}")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            url=str(data["url"]),
            kind=str(data["kind"]),
            priority=int(data["priority"]),
            default_purpose=list(data["default_purpose"]),
            license_policy=str(data["license_policy"]),
            acquisition_mode=str(data["acquisition_mode"]),
            pin_strategy=str(data["pin_strategy"]),
            expected_diagram_families=list(data["expected_diagram_families"]),
            allowed_split_targets=list(data["allowed_split_targets"]),
            ref=str(data.get("ref", "")),
            notes=str(data.get("notes", "")),
            seed_urls=list(data.get("seed_urls", [])),
        )


@dataclass(frozen=True)
class SourcesConfig:
    """The complete source registry and coverage declarations."""

    plantuml_version: str
    renderer: dict[str, Any]
    sources: list[SourceDefinition]
    recommendation_features: set[str]

    def source_ids(self) -> set[str]:
        return {source.id for source in self.sources}


def load_sources_config(path: Path | str = DEFAULT_SOURCES_CONFIG) -> SourcesConfig:
    """Load the source registry from JSON-valid YAML."""

    registry_path = Path(path)
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    if "sources" not in payload:
        raise ValueError(f"{registry_path} does not contain a 'sources' list")
    features = set(payload.get("recommendation_features", []))
    unknown_features = features - REPORT_RECOMMENDED_FEATURES
    if unknown_features:
        raise ValueError(
            "source registry declares unknown recommendation features: "
            + ", ".join(sorted(unknown_features))
        )
    return SourcesConfig(
        plantuml_version=str(payload.get("plantuml_version", "")),
        renderer=dict(payload.get("renderer", {})),
        sources=[SourceDefinition.from_mapping(item) for item in payload["sources"]],
        recommendation_features=features,
    )
