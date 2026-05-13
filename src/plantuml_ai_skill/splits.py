"""Build training/evaluation splits with leakage and license controls."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .license_policy import may_enter_training_split
from .manifest import CorpusRecord, write_jsonl


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
    synthetic_count = 0
    for _, group in sorted(by_repo.items()):
        for record in sorted(group, key=lambda item: item.id):
            if "source_conditioned_eval" in record.purpose:
                splits["source_conditioned_eval"].append(record)
            if "gold_eval" in record.purpose:
                splits["gold_eval"].append(record)
            if "renderer_regression" in record.purpose:
                splits["renderer_regression"].append(record)
            if "augmentation" in record.purpose:
                if record.source_name == "synthetic-uml-diagram-dataset":
                    if synthetic_count >= synthetic_cap:
                        continue
                    synthetic_count += 1
                splits["augmentation"].append(record)
            elif may_enter_training_split(record.license, record.purpose):
                splits["train"].append(record)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for split_name, split_records in splits.items():
        write_jsonl(split_records, out / f"{split_name}.jsonl")
    return splits
