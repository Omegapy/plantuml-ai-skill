from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import (
    SYNTHETIC_UML_DATASET_ID,
    SYNTHETIC_UML_DATASET_ROOT_NAME,
    acquire_source,
    acquire_synthetic_uml_diagram_dataset,
)
from plantuml_ai_skill.cli import _resolve_record_path, _resolve_reference_path
from plantuml_ai_skill.config import SourceDefinition
from plantuml_ai_skill.constants import PLANTUML_VERSION, PROJECT_ROOT
from plantuml_ai_skill.manifest import CorpusRecord, read_jsonl
from plantuml_ai_skill.splits import build_splits


def _synthetic_source() -> SourceDefinition:
    return SourceDefinition(
        id=SYNTHETIC_UML_DATASET_ID,
        name="Synthetic UML Diagram Dataset (PlantUML)",
        url="https://zenodo.org/records/15103682",
        kind="synthetic_dataset",
        priority=6,
        default_purpose=["augmentation"],
        license_policy="verify-before-training; license not visible in report snippet",
        acquisition_mode="huggingface_dataset",
        pin_strategy="dataset_revision",
        expected_diagram_families=["activity", "sequence"],
        allowed_split_targets=["augmentation"],
    )


def _write_pair(root: Path, subset: str, partition: str, name: str, text: str) -> None:
    target = root / subset / partition
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{name}.txt").write_text(text, encoding="utf-8")
    (target / f"{name}.png").write_bytes(b"synthetic png placeholder")


def _sequence_text(label: str) -> str:
    return "\n".join(["@startuml", "Alice -> Bob: " + label, "@enduml"])


def _activity_text(label: str) -> str:
    return "\n".join(["@startuml", "start", f":{label};", "stop", "@enduml"])


def _synthetic_record(record_id: str, diagram_type: str) -> CorpusRecord:
    return CorpusRecord(
        id=record_id,
        source_name=SYNTHETIC_UML_DATASET_ID,
        source_url="https://zenodo.org/records/15103682",
        source_kind="synthetic_dataset",
        source_ref=f"{diagram_type}-subset",
        license="verify-on-clone",
        license_family="unknown",
        diagram_type=diagram_type,
        puml_path=f"{diagram_type}/{record_id}.txt",
        published_render_path=f"{diagram_type}/{record_id}.png",
        python_source_paths=[],
        include_deps=[],
        is_self_contained=True,
        uses_include=False,
        uses_icon_library=False,
        plantuml_version=PLANTUML_VERSION,
        graphviz_version="",
        render_status="not_rendered",
        render_hash_svg="",
        render_hash_png="",
        verification_status="not_verified",
        render_fail_reason="",
        purpose=["augmentation"],
        attribution="Synthetic UML Diagram Dataset (PlantUML)",
        license_path="",
        source_commit="",
        source_repo_url="https://zenodo.org/records/15103682",
    )


class SyntheticDatasetTests(unittest.TestCase):
    def test_acquire_synthetic_dataset_pairs_txt_and_png_with_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pair(
                root,
                "Small_English_Seq_Data_Total",
                "Train/1",
                "Seq1",
                _sequence_text("hello"),
            )
            _write_pair(
                root,
                "Small_English_Act_Data_Total",
                "Test",
                "Act1",
                _activity_text("work"),
            )
            missing_png = root / "Small_English_Act_Data_Total" / "Test" / "ActMissing.txt"
            missing_png.write_text(_activity_text("missing"), encoding="utf-8")
            (root / "Small_English_Act_Data_Total" / "Test" / "ActPngOnly.png").write_bytes(b"png only")
            output = root / "manifest.jsonl"
            stats: dict[str, int] = {}

            records = acquire_synthetic_uml_diagram_dataset(
                _synthetic_source(),
                root,
                output,
                acquisition_stats=stats,
            )
            persisted = read_jsonl(output)

        self.assertEqual(2, len(records))
        self.assertEqual([record.id for record in records], [record.id for record in persisted])
        self.assertEqual(2, stats["paired_records"])
        self.assertEqual(1, stats["txt_without_png"])
        self.assertEqual(1, stats["png_without_txt"])
        record = next(item for item in records if item.diagram_type == "sequence")
        self.assertEqual(SYNTHETIC_UML_DATASET_ID, record.source_name)
        self.assertEqual("synthetic_dataset", record.source_kind)
        self.assertEqual(["augmentation"], record.purpose)
        self.assertEqual("verify-on-clone", record.license)
        self.assertEqual("unknown", record.license_family)
        self.assertEqual("Small_English_Seq_Data_Total/Train/1/Seq1.txt", record.puml_path)
        self.assertEqual("Small_English_Seq_Data_Total/Train/1/Seq1.png", record.published_render_path)
        self.assertEqual("Small_English_Seq_Data_Total", record.extra["dataset_subset"])
        self.assertEqual("Train", record.extra["dataset_split"])
        self.assertEqual("1", record.extra["dataset_shard"])
        self.assertEqual("Train/1", record.extra["dataset_partition"])
        self.assertEqual("same_basename", record.extra["published_render_pairing_status"])
        self.assertIn("content_sha1", record.extra)
        activity = next(item for item in records if item.extra["dataset_subset"] == "Small_English_Act_Data_Total")
        self.assertEqual("activity", activity.diagram_type)

    def test_synthetic_filters_and_caps_are_applied_per_subset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_pair(root, "Small_English_Seq_Data_Total", "Train/1", "Seq1", _sequence_text("one"))
            _write_pair(root, "Small_English_Seq_Data_Total", "Train/1", "Seq2", _sequence_text("two"))
            _write_pair(root, "Small_English_Seq_Data_Total", "Train/2", "Seq3", _sequence_text("three"))
            _write_pair(root, "Small_English_Act_Data_Total", "Train/1", "Act1", _activity_text("act"))
            stats: dict[str, int] = {}

            records = acquire_synthetic_uml_diagram_dataset(
                _synthetic_source(),
                root,
                root / "manifest.jsonl",
                subsets=["Small_English_Seq_Data_Total"],
                partitions=["Train/1"],
                max_records_per_subset=1,
                acquisition_stats=stats,
            )

        self.assertEqual(1, len(records))
        self.assertEqual("Small_English_Seq_Data_Total", records[0].extra["dataset_subset"])
        self.assertEqual("Train/1", records[0].extra["dataset_partition"])
        self.assertEqual(1, stats["paired_records"])
        self.assertEqual(1, stats["skipped_by_cap"])
        self.assertEqual(0, stats["png_without_txt"])

    def test_acquire_source_uses_staged_plantuml_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            raw_dir = Path(tmp) / "raw"
            dataset_root = raw_dir / SYNTHETIC_UML_DATASET_ROOT_NAME
            _write_pair(dataset_root, "Small_English_Seq_Data_Total", "Train/1", "Seq1", _sequence_text("hello"))

            records = acquire_source(
                SYNTHETIC_UML_DATASET_ID,
                Path(tmp) / "manifest.jsonl",
                raw_dir=raw_dir,
                subsets=["Small_English_Seq_Data_Total"],
                max_records_per_subset=1,
            )

        self.assertEqual(1, len(records))
        self.assertEqual("Small_English_Seq_Data_Total/Train/1/Seq1.txt", records[0].puml_path)

    def test_synthetic_filters_are_rejected_for_other_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "only supported"):
                acquire_source("fixtures", Path(tmp) / "fixtures.jsonl", subsets=["Small_English_Seq_Data_Total"])

    def test_synthetic_default_paths_resolve_to_plantuml_data_root(self) -> None:
        record = _synthetic_record("sample", "sequence")
        record.puml_path = "Small_English_Seq_Data_Total/Train/1/sample.txt"
        record.published_render_path = "Small_English_Seq_Data_Total/Train/1/sample.png"

        self.assertEqual(
            PROJECT_ROOT
            / "data"
            / "raw"
            / SYNTHETIC_UML_DATASET_ROOT_NAME
            / "Small_English_Seq_Data_Total"
            / "Train"
            / "1"
            / "sample.txt",
            _resolve_record_path(record, ""),
        )
        self.assertEqual(
            PROJECT_ROOT
            / "data"
            / "raw"
            / SYNTHETIC_UML_DATASET_ROOT_NAME
            / "Small_English_Seq_Data_Total"
            / "Train"
            / "1"
            / "sample.png",
            _resolve_reference_path(record, ""),
        )

    def test_synthetic_cap_is_balanced_by_diagram_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            records = [
                _synthetic_record("activity-1", "activity"),
                _synthetic_record("activity-2", "activity"),
                _synthetic_record("activity-3", "activity"),
                _synthetic_record("sequence-1", "sequence"),
                _synthetic_record("sequence-2", "sequence"),
                _synthetic_record("sequence-3", "sequence"),
            ]

            splits = build_splits(records, Path(tmp) / "splits", synthetic_cap=4)

        selected_types = [record.diagram_type for record in splits["augmentation"]]
        self.assertEqual(["activity", "sequence", "activity", "sequence"], selected_types)


if __name__ == "__main__":
    unittest.main()
