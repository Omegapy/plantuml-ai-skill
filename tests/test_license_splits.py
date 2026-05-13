from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.license_policy import license_family, may_enter_training_split
from plantuml_ai_skill.splits import build_splits


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class LicenseSplitTests(unittest.TestCase):
    def test_license_family_classification(self) -> None:
        self.assertEqual("permissive", license_family("MIT"))
        self.assertEqual("permissive", license_family("Apache-2.0"))
        self.assertEqual("mixed", license_family("Original repo licenses retained"))
        self.assertEqual("unknown", license_family("verify-on-clone"))

    def test_only_permissive_training_records_enter_train(self) -> None:
        self.assertTrue(may_enter_training_split("MIT", ["training"]))
        self.assertFalse(may_enter_training_split("GPL-3.0", ["training"]))
        self.assertFalse(may_enter_training_split("MIT", ["gold_eval"]))

    def test_build_splits_outputs_expected_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, manifest)
            splits = build_splits(records, Path(tmp) / "splits", synthetic_cap=1)
        self.assertGreater(len(splits["train"]), 0)
        self.assertGreater(len(splits["gold_eval"]), 0)
        self.assertGreater(len(splits["source_conditioned_eval"]), 0)


if __name__ == "__main__":
    unittest.main()
