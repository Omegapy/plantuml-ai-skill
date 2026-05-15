import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import unittest

from plantuml_ai_skill.release_packages import build_release_packages


ROOT = Path(__file__).resolve().parents[1]
C4_FIXTURE = ROOT / "tests" / "fixtures" / "vendor" / "c4-package"


class ReleasePackageTests(unittest.TestCase):
    def test_builds_expected_archives_and_deterministic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            left_outputs = build_release_packages("test", Path(left), c4_source=C4_FIXTURE)
            right_outputs = build_release_packages("test", Path(right), c4_source=C4_FIXTURE)

            left_names = sorted(path.name for path in left_outputs)
            self.assertEqual(
                [
                    "SHA256SUMS",
                    "plantuml-diagram-c4-test.tar.gz",
                    "plantuml-diagram-core-test.tar.gz",
                    "plantuml-diagram-render-test.tar.gz",
                    "plantuml-diagram-validate-test.tar.gz",
                ],
                left_names,
            )
            for name in left_names:
                self.assertEqual((Path(left) / name).read_bytes(), (Path(right) / name).read_bytes())

            core_members = _tar_members(Path(left) / "plantuml-diagram-core-test.tar.gz")
            validate_members = _tar_members(Path(left) / "plantuml-diagram-validate-test.tar.gz")
            render_members = _tar_members(Path(left) / "plantuml-diagram-render-test.tar.gz")
            c4_members = _tar_members(Path(left) / "plantuml-diagram-c4-test.tar.gz")

        self.assertIn("plantuml-diagram-core-test/payload/skills/plantuml-diagram/SKILL.md", core_members)
        self.assertFalse(any("/scripts/" in member for member in core_members))
        self.assertFalse(any(member.endswith("/payload/bin/plantuml-ai") for member in core_members))
        self.assertIn(
            "plantuml-diagram-validate-test/payload/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py",
            validate_members,
        )
        self.assertIn("plantuml-diagram-validate-test/payload/bin/plantuml-ai", validate_members)
        self.assertIn(
            "plantuml-diagram-render-test/payload/tools/plantuml-ai-skill/src/plantuml_ai_skill/consumer_cli.py",
            render_members,
        )
        self.assertIn("plantuml-diagram-c4-test/payload/vendor/c4-plantuml/C4_Container.puml", c4_members)
        for members in (core_members, validate_members, render_members, c4_members):
            self.assertFalse(any("/payload/data/" in member for member in members))
            self.assertFalse(any(member.endswith(".jar") for member in members))

    def test_core_installer_is_idempotent_and_protects_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = _build_one(tmp_path, "plantuml-diagram-core-test.tar.gz")
            package_dir = _extract(archive, tmp_path / "extract")
            project = tmp_path / "project"
            project.mkdir()

            first = _install(package_dir, project)
            second = _install(package_dir, project)
            skill = project / ".agents" / "skills" / "plantuml-diagram" / "SKILL.md"
            manifest = project / ".agents" / "plantuml-ai-skill" / "install-manifest.json"
            installed = json.loads(manifest.read_text(encoding="utf-8"))
            text = skill.read_text(encoding="utf-8")
            bin_exists = (project / ".agents" / "bin" / "plantuml-ai").exists()
            scripts_exists = (project / ".agents" / "skills" / "plantuml-diagram" / "scripts").exists()

            skill.write_text("custom user file\n", encoding="utf-8")
            protected = _install(package_dir, project)
            forced = _install(package_dir, project, "--force")
            traversal = _install(package_dir, project, "--prefix", ".agents/..")

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual("plantuml-diagram-core", installed["package_name"])
        self.assertFalse(bin_exists)
        self.assertFalse(scripts_exists)
        self.assertNotIn("validate_plantuml_attempt.py", text)
        self.assertEqual(1, protected.returncode)
        self.assertIn("Refusing to overwrite", protected.stderr)
        self.assertEqual(0, forced.returncode, forced.stderr)
        self.assertEqual(2, traversal.returncode)
        self.assertIn("path traversal", traversal.stderr)

    def test_validate_package_runs_portable_validator_without_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = _build_one(tmp_path, "plantuml-diagram-validate-test.tar.gz")
            package_dir = _extract(archive, tmp_path / "extract")
            project = tmp_path / "project"
            project.mkdir()
            self.assertEqual(0, _install(package_dir, project).returncode)

            valid = project / "valid.md"
            valid.write_text("```plantuml\n@startuml\nAlice -> Bob: hi\n@enduml\n```\n", encoding="utf-8")
            invalid = project / "invalid.puml"
            invalid.write_text("@startuml\nAlice -> Bob: hi\n@enduml\n@startuml\nBob -> Alice: ok\n@enduml\n", encoding="utf-8")
            cli = project / ".agents" / "bin" / "plantuml-ai"
            ambient_env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
            ok = subprocess.run(
                [str(cli), "validate", str(valid), "--expected-type", "sequence", "--required", "Alice"],
                cwd=project,
                env=ambient_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            bad = subprocess.run(
                [str(cli), "validate", str(invalid)],
                cwd=project,
                env=ambient_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
        self.assertIn("validator=portable", ok.stdout)
        self.assertEqual(1, bad.returncode)
        self.assertIn("multiple_plantuml_blocks", bad.stdout)

    def test_render_package_runtime_cli_with_fake_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = _build_one(tmp_path, "plantuml-diagram-render-test.tar.gz")
            package_dir = _extract(archive, tmp_path / "extract")
            project = tmp_path / "project"
            project.mkdir()
            self.assertEqual(0, _install(package_dir, project, "--no-assets").returncode)
            fake_java, fake_jar = _fake_renderer(tmp_path)
            puml = project / "diagram.puml"
            puml.write_text("@startuml\nAlice -> Bob: hi\n@enduml\n", encoding="utf-8")
            output = project / "diagram.svg"
            cli = project / ".agents" / "bin" / "plantuml-ai"

            render = subprocess.run(
                [str(cli), "render", str(puml), "--output", str(output), "--java", str(fake_java), "--jar", str(fake_jar)],
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            validate = subprocess.run(
                [str(cli), "validate", str(puml), "--render", "--java", str(fake_java), "--jar", str(fake_jar)],
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            doctor = subprocess.run(
                [str(cli), "doctor", "--json", "--java", str(fake_java), "--jar", str(fake_jar)],
                cwd=project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            rendered_text = output.read_text(encoding="utf-8") if output.exists() else ""

        self.assertEqual(0, render.returncode, render.stdout + render.stderr)
        self.assertTrue(rendered_text.startswith("<svg"))
        self.assertEqual(0, validate.returncode, validate.stdout + validate.stderr)
        self.assertIn("render_status=ok", validate.stdout)
        self.assertIn("plantuml_jar", doctor.stdout)

    def test_c4_package_resolves_bundled_include_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outputs = build_release_packages("test", tmp_path / "packages", c4_source=C4_FIXTURE)
            archives = {path.name: path for path in outputs if path.suffix == ".gz"}
            fake_java, fake_jar = _fake_renderer(tmp_path)
            c4_text = textwrap.dedent(
                """\
                @startuml
                !include C4_Container.puml
                Person(user, "User")
                Container(api, "API", "Python")
                Rel(user, api, "Uses")
                @enduml
                """
            )

            render_project = tmp_path / "render-project"
            render_project.mkdir()
            render_package = _extract(archives["plantuml-diagram-render-test.tar.gz"], tmp_path / "render-extract")
            self.assertEqual(0, _install(render_package, render_project, "--no-assets").returncode)
            render_puml = render_project / "c4.puml"
            render_puml.write_text(c4_text, encoding="utf-8")
            render_cli = render_project / ".agents" / "bin" / "plantuml-ai"
            render_result = subprocess.run(
                [str(render_cli), "validate", str(render_puml), "--render", "--c4", "--java", str(fake_java), "--jar", str(fake_jar)],
                cwd=render_project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

            c4_project = tmp_path / "c4-project"
            c4_project.mkdir()
            c4_package = _extract(archives["plantuml-diagram-c4-test.tar.gz"], tmp_path / "c4-extract")
            self.assertEqual(0, _install(c4_package, c4_project, "--no-assets").returncode)
            c4_puml = c4_project / "c4.puml"
            c4_puml.write_text(c4_text, encoding="utf-8")
            c4_cli = c4_project / ".agents" / "bin" / "plantuml-ai"
            c4_result = subprocess.run(
                [str(c4_cli), "validate", str(c4_puml), "--render", "--c4", "--java", str(fake_java), "--jar", str(fake_jar)],
                cwd=c4_project,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertEqual(1, render_result.returncode)
        self.assertIn("include_resolution_failed", render_result.stdout)
        self.assertEqual(0, c4_result.returncode, c4_result.stdout + c4_result.stderr)
        self.assertIn("render_status=ok", c4_result.stdout)


def _build_one(root: Path, name: str) -> Path:
    outputs = build_release_packages("test", root / "packages", c4_source=C4_FIXTURE)
    archives = {path.name: path for path in outputs}
    return archives[name]


def _extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True)
    with tarfile.open(archive, "r:gz") as tar:
        if sys.version_info >= (3, 12):
            tar.extractall(destination, filter="data")
        else:
            tar.extractall(destination)
    children = [path for path in destination.iterdir() if path.is_dir()]
    assert len(children) == 1
    return children[0]


def _install(package_dir: Path, project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(package_dir / "install.sh"), *args],
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _tar_members(archive: Path) -> list[str]:
    with tarfile.open(archive, "r:gz") as tar:
        return sorted(tar.getnames())


def _fake_renderer(root: Path) -> tuple[Path, Path]:
    fake_java = root / "java"
    fake_jar = root / "plantuml.jar"
    fake_jar.write_text("fake", encoding="utf-8")
    fake_java.write_text(
        textwrap.dedent(
            """\
            #!/bin/sh
            case "$*" in
              *-version*) echo 'openjdk version "17.0.12"' >&2; exit 0 ;;
              *-testdot*) echo "dot ok"; exit 0 ;;
              *-tpng*) printf '\\211PNG\\r\\n\\032\\nrest'; exit 0 ;;
              *-tsvg*) echo '<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>'; exit 0 ;;
              *) echo "unexpected args: $*" >&2; exit 2 ;;
            esac
            """
        ),
        encoding="utf-8",
    )
    os.chmod(fake_java, 0o755)
    return fake_java, fake_jar


if __name__ == "__main__":
    unittest.main()
