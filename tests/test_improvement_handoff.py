from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.improvement.handoff import write_codex_generation_prompt, write_codex_next_prompt
from plantuml_ai_skill.improvement.models import FailureCluster, ImprovementRun, SkillEvalCase, write_jsonl


class ImprovementHandoffTests(unittest.TestCase):
    def test_next_prompt_contains_resume_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = ImprovementRun(
                id="run-001",
                created_at="2026-05-13T12:00:00Z",
                status="diagnosed",
                baseline_skill_version_id="skill-000",
                candidate_skill_version_id="skill-001",
                suite_path="data/improvement/runs/run-001/eval_cases.jsonl",
                attempts_path="data/improvement/runs/run-001/attempts.jsonl",
                results_path="data/improvement/runs/run-001/results.jsonl",
                report_path="data/improvement/runs/run-001/evaluation-report.md",
                next_handoff_path=str(root / "codex-next-prompt.md"),
                metrics={"cases": 1, "remote_include_violations": 0},
            )
            path = write_codex_next_prompt(
                run,
                [
                    FailureCluster(
                        id="missing_required_relationship",
                        count=2,
                        severity="error",
                        evidence_case_ids=["case-a"],
                    )
                ],
            )
            text = path.read_text(encoding="utf-8")
        self.assertIn("Allowed Edits", text)
        self.assertIn("Do Not Edit", text)
        self.assertIn("plantuml-skill improve evaluate --run latest", text)
        self.assertIn("missing_required_relationship", text)

    def test_generation_prompt_guides_c4_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "eval_cases.jsonl"
            write_jsonl(
                [
                    SkillEvalCase(
                        id="c4-case",
                        suite="core",
                        prompt="Create a C4 container diagram.",
                        expected_diagram_type="c4",
                        required_patterns=[],
                        forbidden_patterns=["!includeurl"],
                        required_edges=[],
                        include_policy="local_includes_allowed",
                        purpose=["skill_eval"],
                        difficulty="medium",
                        tags=["c4"],
                    )
                ],
                suite,
            )
            run = ImprovementRun(
                id="run-001",
                created_at="2026-05-13T12:00:00Z",
                status="initialized",
                baseline_skill_version_id="skill-000",
                candidate_skill_version_id="skill-001",
                suite_path=str(suite),
                attempts_path=str(root / "attempts.jsonl"),
                results_path=str(root / "results.jsonl"),
                report_path=str(root / "evaluation-report.md"),
                next_handoff_path=str(root / "codex-next-prompt.md"),
            )
            path = write_codex_generation_prompt(run)
            text = path.read_text(encoding="utf-8")
        self.assertIn("!include C4_Container.puml", text)
        self.assertIn("do not reimplement C4 macros inline", text)


if __name__ == "__main__":
    unittest.main()
