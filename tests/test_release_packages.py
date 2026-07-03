from __future__ import annotations

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
import zipfile

from plantuml_ai_skill.release_packages import build_release_packages
from plantuml_ai_skill.improvement.palette import AETHER_DARK_STYLE_BLOCK


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
                    "plantuml-diagram-c4-test-windows.zip",
                    "plantuml-diagram-c4-test.tar.gz",
                    "plantuml-diagram-core-test-windows.zip",
                    "plantuml-diagram-core-test.tar.gz",
                    "plantuml-diagram-render-test-windows.zip",
                    "plantuml-diagram-render-test.tar.gz",
                    "plantuml-diagram-validate-test-windows.zip",
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
            windows_core_members = _zip_members(Path(left) / "plantuml-diagram-core-test-windows.zip")
            windows_validate_members = _zip_members(Path(left) / "plantuml-diagram-validate-test-windows.zip")
            windows_render_members = _zip_members(Path(left) / "plantuml-diagram-render-test-windows.zip")
            windows_c4_members = _zip_members(Path(left) / "plantuml-diagram-c4-test-windows.zip")
            members_by_archive = {
                "plantuml-diagram-core-test.tar.gz": core_members,
                "plantuml-diagram-validate-test.tar.gz": validate_members,
                "plantuml-diagram-render-test.tar.gz": render_members,
                "plantuml-diagram-c4-test.tar.gz": c4_members,
            }
            readmes = {
                name: _tar_text(Path(left) / name, f"{name.removesuffix('.tar.gz')}/README.md")
                for name in members_by_archive
            }
            manifests = {
                name: _tar_json(Path(left) / name, f"{name.removesuffix('.tar.gz')}/manifest.json")
                for name in members_by_archive
            }
            windows_members_by_archive = {
                "plantuml-diagram-core-test-windows.zip": windows_core_members,
                "plantuml-diagram-validate-test-windows.zip": windows_validate_members,
                "plantuml-diagram-render-test-windows.zip": windows_render_members,
                "plantuml-diagram-c4-test-windows.zip": windows_c4_members,
            }
            windows_readmes = {
                name: _zip_text(Path(left) / name, f"{name.removesuffix('.zip')}/README.md")
                for name in windows_members_by_archive
            }
            windows_manifests = {
                name: _zip_json(Path(left) / name, f"{name.removesuffix('.zip')}/manifest.json")
                for name in windows_members_by_archive
            }
            windows_install = _zip_text(
                Path(left) / "plantuml-diagram-render-test-windows.zip",
                "plantuml-diagram-render-test-windows/install.ps1",
            )
            core_openai = _tar_text(
                Path(left) / "plantuml-diagram-core-test.tar.gz",
                "plantuml-diagram-core-test/payload/skills/plantuml-diagram/agents/openai.yaml",
            )
            sums = (Path(left) / "SHA256SUMS").read_text(encoding="utf-8")

        self.assertIn("plantuml-diagram-core-test/payload/skills/plantuml-diagram/SKILL.md", core_members)
        self.assertIn(
            "plantuml-diagram-core-test/payload/skills/plantuml-diagram/agents/openai.yaml",
            core_members,
        )
        self.assertIn('display_name: "PlantUML Diagram"', core_openai)
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
            self.assertTrue(any(member.endswith("/payload/skills/plantuml-diagram/agents/openai.yaml") for member in members))
            self.assertFalse(any("/payload/data/" in member for member in members))
            self.assertFalse(any(member.endswith(".jar") for member in members))
        for archive_name, members in members_by_archive.items():
            package_root = archive_name.removesuffix(".tar.gz")
            self.assertIn(f"{package_root}/README.md", members)
            self.assertIn(f"{package_root}/install.sh", members)
            self.assertIn(f"{package_root}/manifest.json", members)
            self.assertIn(f"{package_root}/payload", members)
            self.assertIn("unzipped installer folder", readmes[archive_name])
            self.assertIn("hidden `.agents` folder", readmes[archive_name])
            self.assertIn("for Codex and the Codex app", readmes[archive_name])
            self.assertIn("not a Claude Code package", readmes[archive_name])
            self.assertIn("creating, checking, and rendering PlantUML diagrams", readmes[archive_name])
            self.assertIn("not for training, fine-tuning, or improving the skill", readmes[archive_name])
            self.assertIn("Agent Install Contract", readmes[archive_name])
            self.assertIn("machine-readable contract", readmes[archive_name])
            self.assertIn("Do not install this packet into global Codex skill folders", readmes[archive_name])
            _assert_manifest_contract(self, manifests[archive_name], package_root, members, "macOS or Linux")
        for archive_name in ("plantuml-diagram-render-test.tar.gz", "plantuml-diagram-c4-test.tar.gz"):
            self.assertIn("macOS And Linux Requirements For Rendering", readmes[archive_name])
            self.assertIn("Python 3.11 or newer", readmes[archive_name])
            self.assertIn("Java 11 or newer", readmes[archive_name])
            self.assertIn("Graphviz", readmes[archive_name])
            self.assertIn("sudo apt install python3 openjdk-17-jre graphviz curl", readmes[archive_name])
        self.assertIn("bundled C4 diagram support", readmes["plantuml-diagram-c4-test.tar.gz"])
        self.assertIn("plantuml-diagram-core-test-windows/payload/skills/plantuml-diagram/SKILL.md", windows_core_members)
        self.assertIn(
            "plantuml-diagram-core-test-windows/payload/skills/plantuml-diagram/agents/openai.yaml",
            windows_core_members,
        )
        self.assertFalse(any("/scripts/" in member for member in windows_core_members))
        self.assertFalse(any(member.endswith("/payload/bin/plantuml-ai.cmd") for member in windows_core_members))
        self.assertIn(
            "plantuml-diagram-validate-test-windows/payload/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py",
            windows_validate_members,
        )
        self.assertIn("plantuml-diagram-validate-test-windows/payload/bin/plantuml-ai.cmd", windows_validate_members)
        self.assertIn("plantuml-diagram-validate-test-windows/payload/bin/plantuml-ai.ps1", windows_validate_members)
        self.assertIn(
            "plantuml-diagram-render-test-windows/payload/tools/plantuml-ai-skill/src/plantuml_ai_skill/consumer_cli.py",
            windows_render_members,
        )
        self.assertIn("plantuml-diagram-c4-test-windows/payload/vendor/c4-plantuml/C4_Container.puml", windows_c4_members)
        for members in (windows_core_members, windows_validate_members, windows_render_members, windows_c4_members):
            self.assertTrue(any(member.endswith("/payload/skills/plantuml-diagram/agents/openai.yaml") for member in members))
            self.assertFalse(any("/payload/data/" in member for member in members))
            self.assertFalse(any(member.endswith(".jar") for member in members))
        for archive_name, members in windows_members_by_archive.items():
            package_root = archive_name.removesuffix(".zip")
            self.assertIn(f"{package_root}/README.md", members)
            self.assertIn(f"{package_root}/install.ps1", members)
            self.assertIn(f"{package_root}/install.cmd", members)
            self.assertIn(f"{package_root}/manifest.json", members)
            self.assertIn(f"{package_root}/payload/", members)
            self.assertIn("Windows 11", windows_readmes[archive_name])
            self.assertIn("hidden `.agents` folder", windows_readmes[archive_name])
            self.assertIn("for Codex and the Codex app", windows_readmes[archive_name])
            self.assertIn("not a Claude Code package", windows_readmes[archive_name])
            self.assertIn("Agent Install Contract", windows_readmes[archive_name])
            self.assertIn("machine-readable contract", windows_readmes[archive_name])
            self.assertIn("Do not install this packet into global Codex skill folders", windows_readmes[archive_name])
            _assert_manifest_contract(self, windows_manifests[archive_name], package_root, members, "Windows 11")
        for archive_name in ("plantuml-diagram-render-test-windows.zip", "plantuml-diagram-c4-test-windows.zip"):
            self.assertIn("Requirements For Rendering", windows_readmes[archive_name])
            self.assertIn("Python 3.11 or newer", windows_readmes[archive_name])
            self.assertIn("Java 11 or newer", windows_readmes[archive_name])
            self.assertIn("Graphviz", windows_readmes[archive_name])
            self.assertIn(".agents\\bin\\plantuml-ai.cmd doctor", windows_readmes[archive_name])
        self.assertIn("Refusing path traversal", windows_install)
        self.assertIn("IsPathRooted", windows_install)
        self.assertIn("plantuml-diagram-render-test-windows.zip", sums)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "POSIX installer tests require bash on a POSIX host")
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
            openai_metadata_exists = (
                project / ".agents" / "skills" / "plantuml-diagram" / "agents" / "openai.yaml"
            ).exists()

            skill.write_text("custom user file\n", encoding="utf-8")
            protected = _install(package_dir, project)
            forced = _install(package_dir, project, "--force")
            traversal = _install(package_dir, project, "--prefix", ".agents/..")

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual("plantuml-diagram-core", installed["package_name"])
        self.assertFalse(bin_exists)
        self.assertFalse(scripts_exists)
        self.assertTrue(openai_metadata_exists)
        self.assertNotIn("validate_plantuml_attempt.py", text)
        self.assertEqual(1, protected.returncode)
        self.assertIn("Refusing to overwrite", protected.stderr)
        self.assertEqual(0, forced.returncode, forced.stderr)
        self.assertEqual(2, traversal.returncode)
        self.assertIn("path traversal", traversal.stderr)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "POSIX installer tests require bash on a POSIX host")
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
            styled = project / "styled.md"
            styled.write_text(
                f"```plantuml\n@startuml\n{AETHER_DARK_STYLE_BLOCK}\nAlice -> Bob: hi\n@enduml\n```\n",
                encoding="utf-8",
            )
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
            palette_ok = subprocess.run(
                [str(cli), "validate", str(styled), "--expected-type", "sequence", "--palette-policy", "aether-dark"],
                cwd=project,
                env=ambient_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            palette_bad = subprocess.run(
                [str(cli), "validate", str(valid), "--expected-type", "sequence", "--palette-policy", "aether-dark"],
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
        self.assertEqual(0, palette_ok.returncode, palette_ok.stdout + palette_ok.stderr)
        self.assertEqual(1, palette_bad.returncode)
        self.assertIn("palette_policy_violation", palette_bad.stdout)
        self.assertEqual(1, bad.returncode)
        self.assertIn("multiple_plantuml_blocks", bad.stdout)

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "POSIX installer tests require bash on a POSIX host")
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

    @unittest.skipUnless(os.name != "nt" and shutil.which("bash"), "POSIX installer tests require bash on a POSIX host")
    def test_c4_package_resolves_bundled_include_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            outputs = build_release_packages("test", tmp_path / "packages", c4_source=C4_FIXTURE)
            archives = {path.name: path for path in outputs if path.suffix == ".gz"}
            fake_java, fake_jar = _fake_renderer(tmp_path)
            c4_text = textwrap.dedent(
                """\
                @startuml
                !include <C4/C4_Container.puml>
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

    def test_windows_validate_package_installs_with_powershell_when_available(self) -> None:
        powershell = _powershell()
        if powershell is None:
            self.skipTest("PowerShell is required for Windows installer execution tests")
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            archive = _build_one(tmp_path, "plantuml-diagram-validate-test-windows.zip")
            package_dir = _extract_zip(archive, tmp_path / "extract")
            project = tmp_path / "project"
            project.mkdir()

            first = _install_windows(package_dir, project, powershell)
            second = _install_windows(package_dir, project, powershell)
            traversal = _install_windows(package_dir, project, powershell, "-Prefix", ".agents\\..")
            manifest = project / ".agents" / "plantuml-ai-skill" / "install-manifest.json"
            installed = json.loads(manifest.read_text(encoding="utf-8-sig"))
            valid = project / "valid.md"
            valid.write_text("```plantuml\n@startuml\nAlice -> Bob: hi\n@enduml\n```\n", encoding="utf-8")
            ok = _run_windows_cli(project, powershell, "validate", str(valid), "--expected-type", "sequence")
            cmd_exists = (project / ".agents" / "bin" / "plantuml-ai.cmd").exists()
            ps1_exists = (project / ".agents" / "bin" / "plantuml-ai.ps1").exists()

        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(0, second.returncode, second.stdout + second.stderr)
        self.assertEqual("plantuml-diagram-validate", installed["package_name"])
        self.assertTrue(cmd_exists)
        self.assertTrue(ps1_exists)
        self.assertEqual(2, traversal.returncode)
        self.assertIn("path traversal", traversal.stderr)
        self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
        self.assertIn("validator=portable", ok.stdout)


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


def _extract_zip(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True)
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(destination)
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


def _install_windows(package_dir: Path, project: Path, powershell: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _powershell_command(powershell, str(package_dir / "install.ps1"), *args),
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _run_windows_cli(project: Path, powershell: str, *args: str) -> subprocess.CompletedProcess[str]:
    if os.name == "nt":
        command = ["cmd.exe", "/c", str(project / ".agents" / "bin" / "plantuml-ai.cmd"), *args]
    else:
        command = _powershell_command(powershell, str(project / ".agents" / "bin" / "plantuml-ai.ps1"), *args)
    return subprocess.run(
        command,
        cwd=project,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def _powershell_command(powershell: str, script: str, *args: str) -> list[str]:
    command = [powershell, "-NoProfile"]
    if Path(powershell).name.lower().startswith("powershell"):
        command.extend(["-ExecutionPolicy", "Bypass"])
    command.extend(["-File", script, *args])
    return command


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell.exe") or shutil.which("powershell")


def _tar_members(archive: Path) -> list[str]:
    with tarfile.open(archive, "r:gz") as tar:
        return sorted(tar.getnames())


def _tar_text(archive: Path, member: str) -> str:
    with tarfile.open(archive, "r:gz") as tar:
        extracted = tar.extractfile(member)
        assert extracted is not None
        return extracted.read().decode("utf-8")


def _zip_members(archive: Path) -> list[str]:
    with zipfile.ZipFile(archive) as zf:
        return sorted(zf.namelist())


def _zip_text(archive: Path, member: str) -> str:
    with zipfile.ZipFile(archive) as zf:
        return zf.read(member).decode("utf-8")


def _tar_json(archive: Path, member: str) -> dict[str, object]:
    return json.loads(_tar_text(archive, member))


def _zip_json(archive: Path, member: str) -> dict[str, object]:
    return json.loads(_zip_text(archive, member))


def _assert_manifest_contract(
    test: unittest.TestCase,
    manifest: dict[str, object],
    package_root: str,
    members: list[str],
    supported_platform: str,
) -> None:
    test.assertEqual("plantuml-skill-package.v1", manifest["schema_version"])
    test.assertEqual(supported_platform, manifest["supported_platform"])
    test.assertEqual("project-local", manifest["install_target"]["type"])
    test.assertEqual(".agents", manifest["install_target"]["default_prefix"])
    test.assertIn("Run the installer from the target project root", manifest["install_target"]["description"])
    test.assertEqual("target project root", manifest["installer"]["run_from"])
    test.assertIn("command", manifest["installer"])
    test.assertIn("options", manifest["installer"])
    test.assertEqual(manifest["capability"], manifest["tier_capability"])
    test.assertIn(".agents/skills/plantuml-diagram/agents/openai.yaml", manifest["installed_paths"])
    test.assertIn("post_install_verification_commands", manifest)
    test.assertTrue(manifest["post_install_verification_commands"])
    for entrypoint in manifest["entrypoints"]:
        test.assertIn(f"{package_root}/payload/{entrypoint.removeprefix('.agents/')}", members)


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
