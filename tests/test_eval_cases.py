from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.improvement.eval_cases import (
    hand_authored_core_cases,
    load_eval_cases,
    make_eval_suite_from_manifest,
    write_eval_cases,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class EvalCasesTests(unittest.TestCase):
    def test_hand_authored_suite_covers_core_families(self) -> None:
        cases = hand_authored_core_cases()
        families = {case.expected_diagram_type for case in cases}
        self.assertTrue({"sequence", "class", "activity", "component", "state", "usecase"} <= families)
        self.assertTrue(any("include-policy" in case.tags for case in cases))

    def test_manifest_suite_is_deterministic_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, manifest)
            first = make_eval_suite_from_manifest(records, max_cases=20)
            second = make_eval_suite_from_manifest(records, max_cases=20)
            output = Path(tmp) / "suite.jsonl"
            write_eval_cases(first, output)
            loaded = load_eval_cases(output)
        self.assertEqual([case.id for case in first], [case.id for case in second])
        self.assertEqual([case.id for case in first], [case.id for case in loaded])
        self.assertTrue(any(case.suite == "source_conditioned" for case in first))


if __name__ == "__main__":
    unittest.main()
