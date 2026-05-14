"""Build training/evaluation splits with leakage and license controls."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .acquisition import SYNTHETIC_UML_DATASET_ID
from .curation import GOLD_EVAL_ALLOWED_VISUAL_CURATION_STATUSES
from .license_policy import training_block_reason
from .manifest import CorpusRecord, write_jsonl


HIGH_TRUST_SPLITS = {"train", "gold_eval", "renderer_regression", "source_conditioned_eval"}
UNRESOLVED_INCLUDE_REASONS = {
    "remote_include_blocked",
    "include_resolution_required",
    "include_roots_not_configured",
}
MISMATCH_VERIFICATION_STATUSES = {"png_mismatch", "svg_mismatch", "verify_error", "unsupported_reference_format"}
VISUAL_MISMATCH_VERIFICATION_STATUSES = {"png_mismatch", "svg_mismatch"}


def build_splits(
    records: list[CorpusRecord],
    output_dir: Path | str,
    synthetic_cap: int = 5000,
) -> dict[str, list[CorpusRecord]]:
    """Build deterministic splits from manifest records."""

    by_repo: dict[str, list[CorpusRecord]] = defaultdict(list)
    for record in records:
        by_repo[record.source_ref or record.source_name].append(record)

    splits: dict[str, list[CorpusRecord]] = {
        "train": [],
        "gold_eval": [],
        "renderer_regression": [],
        "source_conditioned_eval": [],
        "augmentation": [],
    }
    synthetic_augmentation: list[CorpusRecord] = []
    for _, group in sorted(by_repo.items()):
        for record in sorted(group, key=lambda item: item.id):
            if "source_conditioned_eval" in record.purpose and not promotion_block_reason(
                record, "source_conditioned_eval"
            ):
                splits["source_conditioned_eval"].append(record)
            if "gold_eval" in record.purpose and not promotion_block_reason(record, "gold_eval"):
                splits["gold_eval"].append(record)
            if "renderer_regression" in record.purpose and not promotion_block_reason(record, "renderer_regression"):
                splits["renderer_regression"].append(record)
            if "augmentation" in record.purpose:
                if record.source_name == SYNTHETIC_UML_DATASET_ID:
                    synthetic_augmentation.append(record)
                else:
                    splits["augmentation"].append(record)
            elif "training" in record.purpose and not promotion_block_reason(record, "train"):
                splits["train"].append(record)

    splits["augmentation"].extend(_balanced_synthetic_augmentation(synthetic_augmentation, synthetic_cap))

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for split_name, split_records in splits.items():
        write_jsonl(split_records, out / f"{split_name}.jsonl")
    return splits


def _balanced_synthetic_augmentation(records: list[CorpusRecord], synthetic_cap: int) -> list[CorpusRecord]:
    if synthetic_cap <= 0 or not records:
        return []
    buckets: dict[str, list[CorpusRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda item: (item.diagram_type, item.source_ref, item.id)):
        buckets[record.diagram_type or "unknown"].append(record)
    selected: list[CorpusRecord] = []
    bucket_names = sorted(buckets)
    cursor = 0
    while len(selected) < synthetic_cap and any(buckets.values()):
        name = bucket_names[cursor % len(bucket_names)]
        cursor += 1
        if not buckets[name]:
            continue
        selected.append(buckets[name].pop(0))
    return selected


def promotion_block_reason(record: CorpusRecord, split_name: str) -> str:
    """Return the reason a record cannot enter a high-trust split."""

    if split_name not in HIGH_TRUST_SPLITS:
        return ""
    if split_name == "train":
        reason = training_block_reason(record.license, record.purpose)
        if reason:
            return reason
    elif record.license_family in {"unknown", "mixed"}:
        return f"blocked_{record.license_family}_license"

    pairing_status = str(record.extra.get("published_render_pairing_status", ""))
    if pairing_status.startswith("ambiguous"):
        return pairing_status
    if record.render_fail_reason in UNRESOLVED_INCLUDE_REASONS:
        return record.render_fail_reason
    if record.render_status == "not_rendered":
        return "not_rendered"
    if record.render_status == "failed":
        return "render_failed"
    if record.render_status == "skipped":
        return record.render_fail_reason or "render_skipped"
    if record.verification_status in VISUAL_MISMATCH_VERIFICATION_STATUSES:
        status = str(record.extra.get("curation_status", ""))
        applies_to = str(record.extra.get("curation_applies_to", ""))
        if (
            split_name == "gold_eval"
            and applies_to == record.verification_status
            and status in GOLD_EVAL_ALLOWED_VISUAL_CURATION_STATUSES
        ):
            return ""
        return f"{record.verification_status}_{status or 'unreviewed'}"
    if record.verification_status in MISMATCH_VERIFICATION_STATUSES:
        return record.verification_status
    return ""
