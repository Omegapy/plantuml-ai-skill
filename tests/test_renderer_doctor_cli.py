from pathlib import Path
import os
import tempfile
import textwrap
import unittest

from plantuml_ai_skill.cli import main
from plantuml_ai_skill.doctor import parse_java_major
from plantuml_ai_skill.renderer import PlantUMLRenderer


ROOT = Path(__file__).resolve().parents[1]


class RendererDoctorCliTests(unittest.TestCase):
    def test_parse_java_major(self) -> None:
        self.assertEqual(17, parse_java_major('openjdk version "17.0.12" 2024-07-16'))
        self.assertEqual(8, parse_java_major('java version "1.8.0_401"'))

    def test_renderer_invokes_java_jar_pipe_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            fake_jar.write_text("fake", encoding="utf-8")
            fake_java.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    case "$*" in
                      *-testdot*) echo "dot ok"; exit 0 ;;
                      *-tsvg*) echo '<svg xmlns="http://www.w3.org/2000/svg"><text>Alice</text></svg>'; exit 0 ;;
                      *) echo "unexpected args: $*" >&2; exit 2 ;;
                    esac
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_java, 0o755)
            renderer = PlantUMLRenderer(jar_path=fake_jar, java_bin=str(fake_java))
            result = renderer.render_svg("@startuml\nAlice -> Bob: hi\n@enduml")
            self.assertTrue(result.ok, result.stderr)
            self.assertIn("-pipe", result.command)
            self.assertIn("-DPLANTUML_SECURITY_PROFILE=SANDBOX", result.command)
            self.assertTrue(renderer.testdot().ok)

    def test_renderer_includes_vendored_include_path_property(self) -> None:
        renderer = PlantUMLRenderer(
            jar_path=Path("plantuml.jar"),
            java_bin="/tmp/java",
            include_roots=[Path("/tmp/vendor/c4"), Path("/tmp/vendor/stdlib")],
        )
        command = renderer.command_for("-tsvg")
        self.assertIn("-Dplantuml.include.path=/tmp/vendor/c4:/tmp/vendor/stdlib", command)

    def test_cli_coverage_and_fixture_acquire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fixtures.jsonl"
            self.assertEqual(0, main(["coverage"]))
            self.assertEqual(0, main(["acquire", "--source", "fixtures", "--output", str(output)]))
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
