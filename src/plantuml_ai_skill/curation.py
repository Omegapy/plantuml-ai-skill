"""Human curation decisions for generated corpus records."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .constants import PROJECT_ROOT
from .manifest import CorpusRecord


DEFAULT_CURATION_PATH = PROJECT_ROOT / "config" / "curation"

VALID_CURATION_STATUSES = {
    "renderer_version_drift",
    "published_image_drift",
    "minor_acceptable_drift",
    "suspicious_pairing",
    "true_regression",
}
VALID_CURATION_TARGETS = {"png_mismatch", "svg_mismatch", "render_failure"}
GOLD_EVAL_ALLOWED_VISUAL_CURATION_STATUSES = {"minor_acceptable_drift"}


@dataclass(frozen=True)
class CurationDecision:
    """One curator decision keyed by manifest record id."""

    record_id: str
    source_name: str
    applies_to: str
    status: str
    rationale: str
    reviewer: str = ""
    reviewed_at: str = ""

    @classmethod
    def from_mapping(
        cls,
        data: dict[str, Any],
        default_source_name: str = "",
        default_reviewer: str = "",
        default_reviewed_at: str = "",
    ) -> "CurationDecision":
        required = {"record_id", "applies_to", "status", "rationale"}
        missing = sorted(required - set(data))
        if missing:
            raise ValueError(f"curation decision missing fields: {', '.join(missing)}")
        decision = cls(
            record_id=str(data["record_id"]),
            source_name=str(data.get("source_name") or default_source_name),
            applies_to=str(data["applies_to"]),
            status=str(data["status"]),
            rationale=str(data["rationale"]),
            reviewer=str(data.get("reviewer") or default_reviewer),
            reviewed_at=str(data.get("reviewed_at") or default_reviewed_at),
        )
        if decision.status not in VALID_CURATION_STATUSES:
            raise ValueError(f"{decision.record_id}: unsupported curation status {decision.status!r}")
        if decision.applies_to not in VALID_CURATION_TARGETS:
            raise ValueError(f"{decision.record_id}: unsupported curation target {decision.applies_to!r}")
        return decision


def load_curation_decisions(path: Path | str | None = DEFAULT_CURATION_PATH) -> dict[str, CurationDecision]:
    """Load curation decisions from a JSON file or directory of JSON files."""

    if path is None or str(path) == "":
        return {}
    root = Path(path)
    if not root.exists():
        return {}
    files = sorted(root.glob("*.json")) if root.is_dir() else [root]
    decisions: dict[str, CurationDecision] = {}
    for file_path in files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        source_name = str(data.get("source_name", ""))
        reviewer = str(data.get("reviewer", ""))
        reviewed_at = str(data.get("reviewed_at", ""))
        for item in data.get("decisions", []):
            decision = CurationDecision.from_mapping(
                item,
                default_source_name=source_name,
                default_reviewer=reviewer,
                default_reviewed_at=reviewed_at,
            )
            existing = decisions.get(decision.record_id)
            if existing:
                raise ValueError(
                    f"duplicate curation decision for {decision.record_id}: "
                    f"{existing.source_name or 'unknown'} and {decision.source_name or 'unknown'}"
                )
            decisions[decision.record_id] = decision
    return decisions


def apply_curation(
    records: list[CorpusRecord],
    decisions: dict[str, CurationDecision],
) -> list[CorpusRecord]:
    """Attach matching curation metadata to manifest records."""

    for record in records:
        decision = decisions.get(record.id)
        if not decision:
            continue
        if decision.source_name and decision.source_name != record.source_name:
            continue
        record.extra["curation_status"] = decision.status
        record.extra["curation_applies_to"] = decision.applies_to
        record.extra["curation_rationale"] = decision.rationale
        if decision.reviewer:
            record.extra["curation_reviewer"] = decision.reviewer
        if decision.reviewed_at:
            record.extra["curation_reviewed_at"] = decision.reviewed_at
    return records
