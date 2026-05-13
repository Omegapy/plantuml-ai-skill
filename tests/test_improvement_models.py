from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.improvement.models import (
    ImprovementRun,
    SkillAttempt,
    SkillEvalCase,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
)
from plantuml_ai_skill.improvement.promotion import promotion_decision


class ImprovementModelsTests(unittest.TestCase):
    def test_valid_eval_case_loads(self) -> None:
        case = SkillEvalCase.from_mapping(
            {
                "id": "sequence-basic-api-timeout",
                "suite": "core",
                "prompt": "Create a sequence diagram.",
                "expected_diagram_type": "sequence",
                "required_patterns": ["Client"],
                "forbidden_patterns": ["!includeurl"],
                "required_edges": [["Client", "API"]],
                "include_policy": "self_contained_only",
            }
        )
        self.assertEqual([("Client", "API")], case.required_edges)

    def test_invalid_eval_case_rejects_unknown_fields(self) -> None:
        with self.assertRaises(ValueError):
            SkillEvalCase.from_mapping(
                {
                    "id": "bad",
                    "suite": "core",
                    "prompt": "Prompt",
                    "expected_diagram_type": "sequence",
                    "include_policy": "self_contained_only",
                    "unexpected": "nope",
                }
            )

    def test_attempt_round_trips_and_preserves_extra_fields(self) -> None:
        attempt = SkillAttempt.from_mapping(
            {
                "id": "attempt-001",
                "run_id": "run-001",
                "skill_version_id": "skill-001",
                "case_id": "case-001",
                "model_or_agent": "codex-app",
                "created_at": "2026-05-13T12:00:00Z",
                "raw_response_path": "attempt.md",
                "puml_text": "@startuml\n@enduml",
                "trace_id": "extra",
            }
        )
        self.assertEqual({"trace_id": "extra"}, attempt.extra)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attempts.jsonl"
            write_jsonl([attempt], path)
            loaded = read_jsonl(path, SkillAttempt)
        self.assertEqual("extra", loaded[0].extra["trace_id"])

    def test_run_state_round_trips(self) -> None:
        run = ImprovementRun(
            id="run-001",
            created_at="2026-05-13T12:00:00Z",
            status="initialized",
            baseline_skill_version_id="skill-000",
            candidate_skill_version_id="skill-001",
            suite_path="suite.jsonl",
            attempts_path="attempts.jsonl",
            results_path="results.jsonl",
            report_path="report.md",
            next_handoff_path="codex-next-prompt.md",
            metrics={"cases": 1},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            write_json(run, path)
            loaded = read_json(path, ImprovementRun)
        self.assertEqual(run.to_mapping(), loaded.to_mapping())

    def test_promotion_requires_tests_metrics_and_human_approval(self) -> None:
        run = ImprovementRun(
            id="run-001",
            created_at="2026-05-13T12:00:00Z",
            status="evaluated",
            baseline_skill_version_id="skill-000",
            candidate_skill_version_id="skill-001",
            suite_path="suite.jsonl",
            attempts_path="attempts.jsonl",
            results_path="results.jsonl",
            report_path="report.md",
            next_handoff_path="codex-next-prompt.md",
            metrics={
                "render_ok_rate": 1.0,
                "semantic_pass_rate": 0.92,
                "remote_include_violations": 0,
                "protected_regressions": 0,
            },
        )
        blocked = promotion_decision(
            run,
            baseline_metrics={"render_ok_rate": 1.0, "semantic_pass_rate": 0.9},
            unit_tests_passed=False,
            human_approval_recorded=False,
        )
        self.assertFalse(blocked.promote)
        self.assertIn("unit_tests_not_recorded", blocked.reasons)
        self.assertIn("human_approval_missing", blocked.reasons)

        allowed = promotion_decision(
            run,
            baseline_metrics={"render_ok_rate": 1.0, "semantic_pass_rate": 0.9},
            unit_tests_passed=True,
            human_approval_recorded=True,
        )
        self.assertTrue(allowed.promote)


if __name__ == "__main__":
    unittest.main()
