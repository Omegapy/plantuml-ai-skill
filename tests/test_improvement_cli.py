from pathlib import Path
import os
import shutil
import tempfile
import textwrap
import unittest

from plantuml_ai_skill.cli import main
from plantuml_ai_skill.constants import PROJECT_ROOT


class ImprovementCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = f"test-cli-{os.getpid()}"
        self.run_dir = PROJECT_ROOT / "data" / "improvement" / "runs" / self.run_id

    def tearDown(self) -> None:
        if self.run_dir.exists():
            shutil.rmtree(self.run_dir)

    def test_improvement_cli_smoke_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            suite = tmp_path / "suite.jsonl"
            self.assertEqual(0, main(["improve", "lint-skill"]))
            self.assertEqual(0, main(["improve", "init", "--no-overwrite"]))
            self.assertEqual(
                0,
                main(["improve", "make-suite", "--output", str(suite), "--max-cases", "1"]),
            )
            self.assertEqual(
                0,
                main(["improve", "begin-run", "--suite", str(suite), "--run-id", self.run_id]),
            )

            response = tmp_path / "activity-order-approval.md"
            response.write_text(
                textwrap.dedent(
                    """\
                    ```plantuml
                    @startuml
                    start
                    :Receive order;
                    :Validate inventory;
                    if (Valid?) then (yes)
                      :Approve;
                    else (no)
                      :Reject;
                    endif
                    :Notify customer;
                    stop
                    @enduml
                    ```
                    """
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                0,
                main(
                    [
                        "improve",
                        "record-attempt",
                        "--run",
                        self.run_id,
                        "--case",
                        "activity-order-approval",
                        "--response-file",
                        str(response),
                    ]
                ),
            )

            fake_java, fake_jar = _fake_renderer(tmp_path)
            self.assertEqual(
                0,
                main(
                    [
                        "improve",
                        "evaluate",
                        "--run",
                        self.run_id,
                        "--java",
                        str(fake_java),
                        "--jar",
                        str(fake_jar),
                    ]
                ),
            )
            self.assertEqual(0, main(["improve", "diagnose", "--run", self.run_id]))
            self.assertEqual(0, main(["improve", "next-prompt", "--run", self.run_id]))
            self.assertTrue((self.run_dir / "codex-next-prompt.md").exists())

    def test_evaluate_allows_missing_attempts_for_ci_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            suite = Path(tmp) / "suite.jsonl"
            self.assertEqual(0, main(["improve", "make-suite", "--output", str(suite), "--max-cases", "1"]))
            self.assertEqual(0, main(["improve", "begin-run", "--suite", str(suite), "--run-id", self.run_id]))
            self.assertEqual(0, main(["improve", "evaluate", "--run", self.run_id, "--allow-missing-attempts", "--no-render"]))


def _fake_renderer(root: Path) -> tuple[Path, Path]:
    fake_java = root / "java"
    fake_jar = root / "plantuml.jar"
    fake_jar.write_text("fake", encoding="utf-8")
    fake_java.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            echo '<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>'
            """
        ),
        encoding="utf-8",
    )
    os.chmod(fake_java, 0o755)
    return fake_java, fake_jar


if __name__ == "__main__":
    unittest.main()
