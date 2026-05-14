from pathlib import Path
import json
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.license_policy import (
    blocked_license_review_for_repo,
    license_family,
    load_license_blocklist,
    may_enter_training_split,
    training_block_reason,
)
from plantuml_ai_skill.splits import build_splits, promotion_block_reason


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
        self.assertEqual("blocked_copyleft_license", training_block_reason("GPL-3.0", ["training"]))

    def test_license_blocklist_records_reviewed_non_permissive_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-blocklist.yml"
            path.write_text(
                json.dumps(
                    {
                        "repositories": {
                            "Owner/Repo": {
                                "license": "GPL-3.0",
                                "license_family": "copyleft",
                                "license_path": "LICENSE",
                                "notes": "Reviewed upstream license",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            reviews = load_license_blocklist(path)

        review = blocked_license_review_for_repo("owner/repo", reviews)
        self.assertIsNotNone(review)
        assert review is not None
        self.assertEqual("GPL-3.0", review.license)
        self.assertEqual("copyleft", review.license_family)
        self.assertEqual("LICENSE", review.license_path)
        self.assertEqual("Reviewed upstream license", review.notes)

    def test_build_splits_outputs_expected_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, manifest)
            for record in records:
                record.render_status = "ok"
                record.verification_status = "rendered_no_reference"
            splits = build_splits(records, Path(tmp) / "splits", synthetic_cap=1)
        self.assertGreater(len(splits["train"]), 0)
        self.assertGreater(len(splits["gold_eval"]), 0)
        self.assertGreater(len(splits["source_conditioned_eval"]), 0)

    def test_promotion_gates_block_untrusted_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, manifest)
        record = records[0]
        record.render_status = "ok"
        record.verification_status = "rendered_no_reference"
        self.assertEqual("", promotion_block_reason(record, "gold_eval"))

        record.license = "verify-on-clone"
        record.license_family = "unknown"
        self.assertEqual("blocked_unknown_license", promotion_block_reason(record, "gold_eval"))

        record.license = "MIT"
        record.license_family = "permissive"
        record.render_status = "failed"
        self.assertEqual("render_failed", promotion_block_reason(record, "gold_eval"))

        record.render_status = "skipped"
        record.render_fail_reason = "remote_include_blocked"
        self.assertEqual("remote_include_blocked", promotion_block_reason(record, "gold_eval"))

        record.render_status = "ok"
        record.render_fail_reason = ""
        record.extra["published_render_pairing_status"] = "ambiguous_markdown_reference"
        self.assertEqual("ambiguous_markdown_reference", promotion_block_reason(record, "gold_eval"))

    def test_reviewed_minor_png_mismatch_can_enter_gold_eval_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, manifest)
        record = records[0]
        record.render_status = "ok"
        record.verification_status = "png_mismatch"
        self.assertEqual("png_mismatch_unreviewed", promotion_block_reason(record, "gold_eval"))

        record.extra["curation_status"] = "renderer_version_drift"
        record.extra["curation_applies_to"] = "png_mismatch"
        self.assertEqual("png_mismatch_renderer_version_drift", promotion_block_reason(record, "gold_eval"))

        record.extra["curation_status"] = "minor_acceptable_drift"
        self.assertEqual("", promotion_block_reason(record, "gold_eval"))
        self.assertEqual("png_mismatch_minor_acceptable_drift", promotion_block_reason(record, "renderer_regression"))


if __name__ == "__main__":
    unittest.main()
