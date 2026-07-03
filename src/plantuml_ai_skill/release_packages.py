"""Build GitHub-downloadable PlantUML skill install packages."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from .constants import PROJECT_ROOT


C4_COMMIT = "1edfb8a878baaa821e54cf423a070c792e8677c6"
C4_ARCHIVE_URL = f"https://github.com/plantuml-stdlib/C4-PlantUML/archive/{C4_COMMIT}.tar.gz"
PACKAGE_SCHEMA_VERSION = "plantuml-skill-package.v1"
SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "plantuml-diagram"
SUPPORTED_PLATFORMS = ("posix", "windows", "all")

RUNTIME_FILES = (
    "__init__.py",
    "assets.py",
    "constants.py",
    "consumer_cli.py",
    "doctor.py",
    "extraction.py",
    "includes.py",
    "renderer.py",
    "verify.py",
    "improvement/__init__.py",
    "improvement/attempts.py",
    "improvement/evaluator.py",
    "improvement/models.py",
    "improvement/palette.py",
    "improvement/scoring.py",
    "improvement/state.py",
)


@dataclass(frozen=True)
class PackageTier:
    name: str
    label: str
    include_validator: bool
    include_runtime: bool
    include_c4: bool
    capability: str

    @property
    def requires_assets(self) -> bool:
        return self.include_runtime


TIERS = (
    PackageTier(
        name="plantuml-diagram-core",
        label="Diagram skill only",
        include_validator=False,
        include_runtime=False,
        include_c4=False,
        capability="PlantUML diagram skill without installed validation or rendering tools.",
    ),
    PackageTier(
        name="plantuml-diagram-validate",
        label="Diagram skill with portable validation",
        include_validator=True,
        include_runtime=False,
        include_c4=False,
        capability="PlantUML diagram skill with lightweight no-render validation.",
    ),
    PackageTier(
        name="plantuml-diagram-render",
        label="Diagram skill with evaluator and rendering",
        include_validator=True,
        include_runtime=True,
        include_c4=False,
        capability="PlantUML diagram skill with full evaluator mode and PlantUML rendering CLI.",
    ),
    PackageTier(
        name="plantuml-diagram-c4",
        label="Diagram skill with evaluator, rendering, and C4 includes",
        include_validator=True,
        include_runtime=True,
        include_c4=True,
        capability="PlantUML diagram skill with full evaluator mode, rendering, and pinned C4-PlantUML includes.",
    ),
)


def add_package_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    package = sub.add_parser("package", help="build installable PlantUML skill packages")
    package_sub = package.add_subparsers(dest="package_command", required=True)

    build = package_sub.add_parser("build", help="build release package archives")
    build.add_argument("--version", required=True)
    build.add_argument("--output", default=str(PROJECT_ROOT / "dist" / "packages"))
    build.add_argument(
        "--c4-source",
        default="",
        help="local C4-PlantUML checkout/include tree; defaults to downloading the pinned archive",
    )
    build.add_argument(
        "--platform",
        choices=SUPPORTED_PLATFORMS,
        default="all",
        help="package platform target; defaults to building both POSIX tarballs and Windows zip files",
    )


def dispatch(args: argparse.Namespace) -> int:
    if args.package_command == "build":
        outputs = build_release_packages(
            args.version,
            Path(args.output),
            c4_source=Path(args.c4_source) if args.c4_source else None,
            platform=args.platform,
        )
        for path in outputs:
            print(path)
        return 0
    raise ValueError(f"unknown package command: {args.package_command}")


def build_release_packages(
    version: str,
    output_dir: Path,
    c4_source: Path | None = None,
    platform: str = "all",
) -> list[Path]:
    """Build all package tiers and return generated files."""

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    platforms = _selected_platforms(platform)
    with tempfile.TemporaryDirectory(prefix="plantuml-packages-") as tmp:
        workspace = Path(tmp)
        c4_root = _resolve_c4_source(c4_source, workspace)
        for tier in TIERS:
            for target_platform in platforms:
                package_dir = _stage_package(tier, version, workspace, c4_root, target_platform)
                if target_platform == "posix":
                    archive = output_dir / f"{tier.name}-{version}.tar.gz"
                    _write_deterministic_tar_gz(package_dir, archive)
                else:
                    archive = output_dir / f"{tier.name}-{version}-windows.zip"
                    _write_deterministic_zip(package_dir, archive)
                outputs.append(archive)
    sums = _write_sha256sums(outputs, output_dir / "SHA256SUMS")
    outputs.append(sums)
    return outputs


def _selected_platforms(platform: str) -> tuple[str, ...]:
    if platform == "all":
        return ("posix", "windows")
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError(f"unsupported package platform: {platform}")
    return (platform,)


def _stage_package(
    tier: PackageTier,
    version: str,
    workspace: Path,
    c4_root: Path | None,
    platform: str,
) -> Path:
    root_suffix = "" if platform == "posix" else "-windows"
    root = workspace / f"{tier.name}-{version}{root_suffix}"
    payload = root / "payload"
    root.mkdir(parents=True)
    payload.mkdir()

    _stage_skill(tier, payload, platform)
    if tier.include_validator:
        _stage_bin(payload, platform)
    if tier.include_runtime:
        _stage_runtime(payload)
    if tier.include_c4:
        if c4_root is None:
            raise FileNotFoundError("C4 package requested but no C4 source is available")
        _stage_c4(payload, c4_root)

    payload_files = _payload_files(payload)
    archive_format = "tar.gz" if platform == "posix" else "zip"
    manifest = _manifest(tier, version, payload_files, platform, archive_format)
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / "payload-files.txt").write_text("\n".join(payload_files) + "\n", encoding="utf-8")
    (root / "README.md").write_text(_readme(tier, version, platform), encoding="utf-8")
    source_commit = _git_commit()
    if platform == "posix":
        install = root / "install.sh"
        install.write_text(_install_script(tier, version, source_commit), encoding="utf-8")
        install.chmod(0o755)
    else:
        install_ps1 = root / "install.ps1"
        install_ps1.write_text(_windows_install_script(tier, version, source_commit), encoding="utf-8")
        install_cmd = root / "install.cmd"
        install_cmd.write_text(_windows_install_cmd(), encoding="utf-8")
    return root


def _stage_skill(tier: PackageTier, payload: Path, platform: str) -> None:
    target = payload / "skills" / "plantuml-diagram"
    references = target / "references"
    references.mkdir(parents=True)
    (target / "SKILL.md").write_text(_skill_text_for_tier(tier, platform), encoding="utf-8")
    agents_source = SKILL_DIR / "agents"
    if agents_source.exists():
        for source in sorted(agents_source.rglob("*")):
            if source.is_file():
                destination = target / "agents" / source.relative_to(agents_source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
    for source in sorted((SKILL_DIR / "references").iterdir()):
        if source.is_file():
            shutil.copy2(source, references / source.name)
    if tier.include_validator:
        scripts = target / "scripts"
        scripts.mkdir()
        validator = scripts / "validate_plantuml_attempt.py"
        shutil.copy2(SKILL_DIR / "scripts" / "validate_plantuml_attempt.py", validator)
        validator.chmod(0o755)


def _stage_bin(payload: Path, platform: str) -> None:
    bin_dir = payload / "bin"
    bin_dir.mkdir(parents=True)
    if platform == "posix":
        script = bin_dir / "plantuml-ai"
        script.write_text(_plantuml_ai_wrapper(), encoding="utf-8")
        script.chmod(0o755)
        return
    script = bin_dir / "plantuml-ai.ps1"
    script.write_text(_windows_plantuml_ai_wrapper(), encoding="utf-8")
    cmd = bin_dir / "plantuml-ai.cmd"
    cmd.write_text(_windows_plantuml_ai_cmd(), encoding="utf-8")


def _stage_runtime(payload: Path) -> None:
    runtime_root = payload / "tools" / "plantuml-ai-skill" / "src" / "plantuml_ai_skill"
    source_root = PROJECT_ROOT / "src" / "plantuml_ai_skill"
    for relative in RUNTIME_FILES:
        source = source_root / relative
        target = runtime_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _stage_c4(payload: Path, c4_root: Path) -> None:
    target = payload / "vendor" / "c4-plantuml"
    target.mkdir(parents=True)
    copied = False
    for source in sorted(c4_root.rglob("*")):
        if not source.is_file() or ".git" in source.parts:
            continue
        relative = source.relative_to(c4_root)
        if _is_c4_payload_file(relative):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied = True
    if not copied:
        raise FileNotFoundError(f"no C4 include files found in {c4_root}")
    if not any((target / name).exists() for name in ("LICENSE", "LICENSE.md", "LICENSE.txt")):
        raise FileNotFoundError(f"C4 source must include a LICENSE file: {c4_root}")


def _is_c4_payload_file(relative: Path) -> bool:
    if any(part.startswith(".") for part in relative.parts):
        return False
    if relative.name in {"LICENSE", "LICENSE.md", "LICENSE.txt", "README.md"}:
        return True
    return relative.suffix.lower() in {".puml", ".iuml"}


def _payload_files(payload: Path) -> list[str]:
    return sorted(path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file())


def _manifest(
    tier: PackageTier,
    version: str,
    payload_files: list[str],
    platform: str,
    archive_format: str,
) -> dict[str, object]:
    dependencies = []
    if tier.include_runtime:
        dependencies.append("Python 3.11+" if platform == "posix" else "Python 3.11+ via the Python launcher or python.exe")
    elif tier.include_validator:
        dependencies.append("python3" if platform == "posix" else "Python launcher or python.exe")
    if tier.include_runtime:
        dependencies.extend(["Java 11+", "Graphviz dot", "network access for pinned PlantUML jar unless --offline-jar or --no-assets is used"])
    entrypoints: list[str] = []
    if tier.include_validator:
        if platform == "posix":
            entrypoints.append(".agents/bin/plantuml-ai")
        else:
            entrypoints.extend([".agents/bin/plantuml-ai.cmd", ".agents/bin/plantuml-ai.ps1"])
    return {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_name": tier.name,
        "version": version,
        "platform": platform,
        "supported_platform": _supported_platform_label(platform),
        "archive_format": archive_format,
        "source_commit": _git_commit(),
        "capability": tier.capability,
        "tier_capability": tier.capability,
        "dependencies": dependencies,
        "c4_commit": C4_COMMIT if tier.include_c4 else "",
        "default_prefix": ".agents",
        "install_target": {
            "type": "project-local",
            "default_prefix": ".agents",
            "description": "Run the installer from the target project root. Files are copied into that project's .agents tree.",
            "skill_path": ".agents/skills/plantuml-diagram",
        },
        "installer": _installer_contract(tier, version, platform),
        "installed_paths": _installed_paths(tier, platform),
        "entrypoints": entrypoints,
        "post_install_verification_commands": _post_install_verification_commands(tier, platform),
        "payload_files": payload_files,
    }


def _supported_platform_label(platform: str) -> str:
    if platform == "windows":
        return "Windows 11"
    return "macOS or Linux"


def _installer_contract(tier: PackageTier, version: str, platform: str) -> dict[str, object]:
    folder_name = f"{tier.name}-{version}-windows" if platform == "windows" else f"{tier.name}-{version}"
    if platform == "windows":
        return {
            "run_from": "target project root",
            "script": "install.ps1",
            "command": f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\path\\to\\{folder_name}\\install.ps1",
            "alternate_command": f".\\{folder_name}\\install.cmd",
            "options": ["-DryRun", "-Force", "-Prefix .agents", "-NoAssets", "-OfflineJar PATH"],
        }
    return {
        "run_from": "target project root",
        "script": "install.sh",
        "command": f"bash /path/to/{folder_name}/install.sh",
        "alternate_command": f"bash {folder_name}/install.sh",
        "options": ["--dry-run", "--force", "--prefix .agents", "--no-assets", "--offline-jar PATH"],
    }


def _installed_paths(tier: PackageTier, platform: str) -> list[str]:
    paths = [
        ".agents/skills/plantuml-diagram/SKILL.md",
        ".agents/skills/plantuml-diagram/agents/openai.yaml",
        ".agents/skills/plantuml-diagram/references/",
        ".agents/plantuml-ai-skill/install-manifest.json",
    ]
    if tier.include_validator:
        paths.append(".agents/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py")
        if platform == "windows":
            paths.extend([".agents/bin/plantuml-ai.cmd", ".agents/bin/plantuml-ai.ps1"])
        else:
            paths.append(".agents/bin/plantuml-ai")
    if tier.include_runtime:
        paths.append(".agents/tools/plantuml-ai-skill/")
    if tier.include_c4:
        paths.append(".agents/vendor/c4-plantuml/")
    return paths


def _post_install_verification_commands(tier: PackageTier, platform: str) -> list[str]:
    if platform == "windows":
        commands = [
            "Test-Path .\\.agents\\skills\\plantuml-diagram\\SKILL.md",
            "Test-Path .\\.agents\\skills\\plantuml-diagram\\agents\\openai.yaml",
        ]
        if tier.include_validator:
            commands.append(".\\.agents\\bin\\plantuml-ai.cmd validate diagram.puml")
        if tier.include_runtime:
            commands.append(".\\.agents\\bin\\plantuml-ai.cmd doctor")
        if tier.include_c4:
            commands.append(".\\.agents\\bin\\plantuml-ai.cmd render c4-diagram.puml --c4 --output c4-diagram.svg")
        return commands
    commands = [
        "test -f .agents/skills/plantuml-diagram/SKILL.md",
        "test -f .agents/skills/plantuml-diagram/agents/openai.yaml",
    ]
    if tier.include_validator:
        commands.append(".agents/bin/plantuml-ai validate diagram.puml")
    if tier.include_runtime:
        commands.append(".agents/bin/plantuml-ai doctor")
    if tier.include_c4:
        commands.append(".agents/bin/plantuml-ai render c4-diagram.puml --c4 --output c4-diagram.svg")
    return commands


def _skill_text_for_tier(tier: PackageTier, platform: str) -> str:
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    if not tier.include_validator:
        text = text.replace(
            "description: Generate, validate, and repair PlantUML diagrams from natural-language requests.",
            "description: Generate and repair PlantUML diagrams from natural-language requests.",
        )
        text = text.replace(
            "Use this skill whenever the user asks for PlantUML, UML-as-code, diagram source, diagram repair, or a rendered/checkable diagram that should be expressed as PlantUML.",
            "Use this skill whenever the user asks for PlantUML, UML-as-code, diagram source, or diagram repair.",
        )
        text = text.replace("8. Validate syntax and palette shape locally before claiming success.\n", "")
        text = text.replace("7. Validate locally with the bundled script or `plantuml-skill improve evaluate` when a run exists.\n", "")
        text = text.replace(
            "9. When working in this repository, run `.agents/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py --palette-policy aether-dark-rendered --render` or `plantuml-skill improve evaluate` if an eval run exists.\n",
            "",
        )
        return text
    tooling = [
        "",
        "## Installed Tooling",
        "",
    ]
    if platform == "posix":
        tooling.append("- Run `.agents/bin/plantuml-ai validate <attempt.md|diagram.puml>` to check one generated attempt.")
    else:
        tooling.append("- Run `.agents\\bin\\plantuml-ai.cmd validate <attempt.md|diagram.puml>` to check one generated attempt on Windows.")
    if tier.include_runtime:
        if platform == "posix":
            tooling.extend(
                [
                    "- Run `.agents/bin/plantuml-ai render <diagram.puml|-> --format svg --output diagram.svg` to render.",
                    "- Run `.agents/bin/plantuml-ai doctor` to check Java, Graphviz, and the pinned PlantUML jar.",
                    "- Run `.agents/bin/plantuml-ai init-assets` to download the pinned PlantUML jar.",
                ]
            )
        else:
            tooling.extend(
                [
                    "- Run `.agents\\bin\\plantuml-ai.cmd render <diagram.puml|-> --format svg --output diagram.svg` to render on Windows.",
                    "- Run `.agents\\bin\\plantuml-ai.cmd doctor` to check Java, Graphviz, and the pinned PlantUML jar.",
                    "- Run `.agents\\bin\\plantuml-ai.cmd init-assets` to download the pinned PlantUML jar.",
                ]
            )
    if tier.include_c4:
        tooling.append("- Pass `--c4` to validation or rendering commands for the bundled C4-PlantUML include root.")
    return text.rstrip() + "\n" + "\n".join(tooling) + "\n"


def _readme(tier: PackageTier, version: str, platform: str) -> str:
    is_windows = platform == "windows"
    archive_name = f"{tier.name}-{version}-windows.zip" if is_windows else f"{tier.name}-{version}.tar.gz"
    folder_name = f"{tier.name}-{version}-windows" if is_windows else f"{tier.name}-{version}"
    platform_label = "Windows 11" if is_windows else "macOS or Linux"
    command_path = ".agents\\bin\\plantuml-ai.cmd" if is_windows else ".agents/bin/plantuml-ai"
    fence = "```powershell" if is_windows else "```bash"
    install_files = ["  install.ps1", "  install.cmd"] if is_windows else ["  install.sh"]
    verification_commands = _post_install_verification_commands(tier, platform)
    lines = [
        f"# {tier.name} {version}",
        "",
        tier.capability,
        "",
        f"This is a downloadable package for installing PlantUML Diagram into one Codex project on {platform_label}.",
        "",
        "This package is for Codex and the Codex app. It is not a Claude Code package and does not install into Claude Code.",
        "",
        "It is for creating, checking, and rendering PlantUML diagrams. It is not for training, fine-tuning, or improving the skill.",
        "",
        "## What This Folder Is",
        "",
        f"After you unzip the `{archive_name}` download, you get this unzipped installer folder.",
        "",
        "```text",
        f"{folder_name}/",
        "  README.md",
        *install_files,
        "  manifest.json",
        "  payload/",
        "```",
        "",
        "You are now inside the unzipped installer folder. The `payload/` folder is not the final installed location.",
        "",
        "The installer copies the useful files into your project's hidden `.agents` folder, where Codex can read them.",
        "",
        "## Agent Install Contract",
        "",
        "For AI agents and automation, treat `manifest.json` as the machine-readable contract for this packet.",
        "",
        "- Run the installer from the target project root.",
        "- Use the default project-local install target `.agents/` unless the user explicitly chooses another `.agents/...` prefix.",
        "- Do not install this packet into global Codex skill folders.",
        "- After install, run the listed verification commands that apply to the package tier.",
        "",
        "Post-install verification commands:",
        "",
        fence,
        *verification_commands,
        "```",
        "",
        "## Install Into Your Project",
        "",
    ]
    if is_windows:
        lines.extend(
            [
                "Open PowerShell and go to the root of the project that should receive the skill:",
                "",
                "```powershell",
                "Set-Location C:\\path\\to\\your-project",
                "```",
                "",
                "Then run this installer script. Replace the path if you unzipped the package somewhere else:",
                "",
                "```powershell",
                f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\\path\\to\\{folder_name}\\install.ps1",
                "```",
                "",
                "If you unzipped this installer folder inside your project folder, you can use:",
                "",
                "```powershell",
                f".\\{folder_name}\\install.cmd",
                "```",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Open Terminal and go to the root of the project that should receive the skill:",
                "",
                "```bash",
                "cd /path/to/your-project",
                "```",
                "",
                "Then run this installer script. Replace the path if you unzipped the package somewhere else:",
                "",
                "```bash",
                f"bash /path/to/{folder_name}/install.sh",
                "```",
                "",
                "If you unzipped this installer folder inside your project folder, you can use:",
                "",
                "```bash",
                f"bash {folder_name}/install.sh",
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "After install, your project will contain files like these:",
            "",
            "```text",
            "your-project/",
            "  .agents/",
            "    skills/",
            "      plantuml-diagram/",
        ]
    )
    if tier.include_validator:
        lines.append("    bin/")
        if is_windows:
            lines.extend(["      plantuml-ai.cmd", "      plantuml-ai.ps1"])
        else:
            lines.append("      plantuml-ai")
    if tier.include_runtime:
        lines.extend(["    tools/", "      plantuml-ai-skill/"])
    if tier.include_c4:
        lines.extend(["    vendor/", "      c4-plantuml/"])
    options = (
        "Installer options for advanced users: `-DryRun`, `-Force`, `-Prefix .agents`, `-NoAssets`, and `-OfflineJar PATH`."
        if is_windows
        else "Installer options for advanced users: `--dry-run`, `--force`, `--prefix .agents`, `--no-assets`, and `--offline-jar PATH`."
    )
    lines.extend(["```", "", options, ""])
    if tier.include_validator:
        lines.extend(
            [
                "## Use After Install",
                "",
                "Check a PlantUML file:",
                "",
                fence,
                f"{command_path} validate diagram.puml",
                "```",
                "",
            ]
        )
    if tier.include_runtime:
        lines.extend(
            [
                "Render a diagram to SVG:",
                "",
                fence,
                f"{command_path} render diagram.puml --output diagram.svg",
                "```",
                "",
                "Check Java, Graphviz, and PlantUML setup:",
                "",
                fence,
                f"{command_path} doctor",
                "```",
                "",
            ]
        )
    if tier.include_c4:
        lines.extend(
            [
                "Render a C4 diagram:",
                "",
                fence,
                f"{command_path} render c4-diagram.puml --c4 --output c4-diagram.svg",
                "```",
                "",
            ]
        )
    lines.extend(["## What Gets Installed", "", "- Skill files go into `.agents/skills/plantuml-diagram/`."])
    if tier.include_validator:
        if is_windows:
            lines.append("- The friendly command wrappers go into `.agents/bin/plantuml-ai.cmd` and `.agents/bin/plantuml-ai.ps1`.")
        else:
            lines.append("- The friendly command goes into `.agents/bin/plantuml-ai`.")
    if tier.include_runtime:
        lines.append("- Runtime files go into `.agents/tools/plantuml-ai-skill/`.")
    if tier.include_c4:
        lines.append("- Bundled C4 diagram support goes into `.agents/vendor/c4-plantuml/`.")
    lines.append("")
    lines.append("The `.agents` folder is hidden because its name starts with a dot. Codex uses this folder for project-local skills and tools.")
    lines.append("")
    if not tier.include_validator:
        lines.extend(
            [
                "## Package Contents",
                "",
                f"This package installs skill instructions only. It does not install the `{command_path}` command.",
                "",
            ]
        )
    if tier.include_runtime:
        requirements_heading = "## Windows 11 Requirements For Rendering" if is_windows else "## macOS And Linux Requirements For Rendering"
        lines.extend(
            [
                requirements_heading,
                "",
                "- Python 3.11 or newer",
                "- Java 11 or newer",
                "- Graphviz",
                "- Network access to download the pinned PlantUML jar unless the offline jar or no-assets option is used",
                "",
            ]
        )
        if is_windows:
            lines.extend(
                [
                    "On Windows 11, install Python from python.org or the Microsoft Store, install Java 11 or newer, and install Graphviz with `dot.exe` on `PATH`.",
                    "",
                    "Then run:",
                    "",
                    "```powershell",
                    ".agents\\bin\\plantuml-ai.cmd init-assets",
                    ".agents\\bin\\plantuml-ai.cmd doctor",
                    "```",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "On macOS with Homebrew:",
                    "",
                    "```bash",
                    "brew install python@3.12 openjdk graphviz",
                    "```",
                    "",
                    "On Ubuntu or Debian Linux:",
                    "",
                    "```bash",
                    "sudo apt update",
                    "sudo apt install python3 openjdk-17-jre graphviz curl",
                    "```",
                    "",
                    "Then run:",
                    "",
                    "```bash",
                    ".agents/bin/plantuml-ai init-assets",
                    ".agents/bin/plantuml-ai doctor",
                    "```",
                    "",
                ]
            )
    elif tier.include_validator:
        requirement = "- Python for `.agents\\bin\\plantuml-ai.cmd validate`" if is_windows else "- `python3` for `.agents/bin/plantuml-ai validate`"
        lines.extend(["## Requirement", "", requirement, ""])
    if tier.include_c4:
        lines.extend(
            [
                "## C4 Includes",
                "",
                "This package includes bundled C4 diagram support.",
                "",
                f"It vendors C4-PlantUML from commit `{C4_COMMIT}` under `.agents/vendor/c4-plantuml`.",
                "",
            ]
        )
    return "\n".join(lines)


def _install_script(tier: PackageTier, version: str, source_commit: str) -> str:
    needs_assets = "1" if tier.requires_assets else "0"
    dependency_note = (
        'echo "Dependencies: Python 3.11+, Java 11+, Graphviz dot, and network access unless --offline-jar or --no-assets is used."'
        if tier.include_runtime
        else ":"
    )
    return f"""#!/bin/sh
set -eu

package_name="{tier.name}"
package_version="{version}"
source_commit="{source_commit}"
needs_assets="{needs_assets}"
prefix=".agents"
force=0
dry_run=0
no_assets=0
offline_jar=""

usage() {{
  echo "Usage: bash install.sh [--dry-run] [--force] [--no-assets] [--offline-jar PATH] [--prefix .agents]" >&2
}}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --force) force=1; shift ;;
    --no-assets) no_assets=1; shift ;;
    --offline-jar)
      [ "$#" -ge 2 ] || {{ usage; exit 2; }}
      offline_jar="$2"; shift 2 ;;
    --prefix)
      [ "$#" -ge 2 ] || {{ usage; exit 2; }}
      prefix="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

case "$prefix" in
  .agents|.agents/*) ;;
  *) echo "Refusing to install outside the target project's .agents tree: $prefix" >&2; exit 2 ;;
esac
case "$prefix" in
  ../*|*/../*|*/..) echo "Refusing path traversal in install prefix: $prefix" >&2; exit 2 ;;
esac

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
payload="$script_dir/payload"
files="$script_dir/payload-files.txt"

if [ ! -d "$payload" ] || [ ! -f "$files" ]; then
  echo "Package payload is incomplete." >&2
  exit 1
fi

{dependency_note}

while IFS= read -r rel || [ -n "$rel" ]; do
  [ -n "$rel" ] || continue
  src="$payload/$rel"
  dst="$prefix/$rel"
  if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
    if [ "$force" -ne 1 ]; then
      echo "Refusing to overwrite existing file without --force: $dst" >&2
      exit 1
    fi
  fi
done < "$files"

while IFS= read -r rel || [ -n "$rel" ]; do
  [ -n "$rel" ] || continue
  src="$payload/$rel"
  dst="$prefix/$rel"
  if [ "$dry_run" -eq 1 ]; then
    echo "would install $dst"
    continue
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
done < "$files"

if [ "$dry_run" -eq 0 ]; then
  [ ! -f "$prefix/bin/plantuml-ai" ] || chmod +x "$prefix/bin/plantuml-ai"
  [ ! -f "$prefix/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py" ] || chmod +x "$prefix/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py"
  mkdir -p "$prefix/plantuml-ai-skill"
  manifest="$prefix/plantuml-ai-skill/install-manifest.json"
  {{
    printf '{{\\n'
    printf '  "package_name": "%s",\\n' "$package_name"
    printf '  "version": "%s",\\n' "$package_version"
    printf '  "source_commit": "%s",\\n' "$source_commit"
    printf '  "prefix": "%s",\\n' "$prefix"
    printf '  "files": [\\n'
    total=$(grep -c . "$files" || true)
    index=0
    while IFS= read -r rel || [ -n "$rel" ]; do
      [ -n "$rel" ] || continue
      index=$((index + 1))
      comma=","
      [ "$index" -lt "$total" ] || comma=""
      printf '    "%s"%s\\n' "$rel" "$comma"
    done < "$files"
    printf '  ]\\n'
    printf '}}\\n'
  }} > "$manifest"
fi

if [ "$dry_run" -eq 0 ] && [ "$needs_assets" -eq 1 ] && [ "$no_assets" -eq 0 ]; then
  if [ -n "$offline_jar" ]; then
    "$prefix/bin/plantuml-ai" init-assets --offline-jar "$offline_jar"
  else
    "$prefix/bin/plantuml-ai" init-assets
  fi
fi

if [ "$dry_run" -eq 0 ]; then
  echo "Installed $package_name $package_version into $prefix"
else
  echo "Dry run completed for $package_name $package_version"
fi
"""


def _windows_install_script(tier: PackageTier, version: str, source_commit: str) -> str:
    needs_assets = "1" if tier.requires_assets else "0"
    dependency_note = (
        'Write-Host "Dependencies: Python 3.11+, Java 11+, Graphviz dot, and network access unless -OfflineJar or -NoAssets is used."'
        if tier.include_runtime
        else ""
    )
    template = r"""param(
  [switch]$DryRun,
  [switch]$Force,
  [switch]$NoAssets,
  [string]$OfflineJar = "",
  [string]$Prefix = ".agents"
)

$ErrorActionPreference = "Stop"

$PackageName = "__PACKAGE_NAME__"
$PackageVersion = "__PACKAGE_VERSION__"
$SourceCommit = "__SOURCE_COMMIT__"
$NeedsAssets = "__NEEDS_ASSETS__"

function Exit-WithError {
  param([string]$Message, [int]$Code = 1)
  [Console]::Error.WriteLine($Message)
  exit $Code
}

function Resolve-InstallPrefix {
  param([string]$Value)
  if ([string]::IsNullOrWhiteSpace($Value)) {
    Exit-WithError "Install prefix is required." 2
  }
  $Normalized = $Value.Replace('/', '\')
  if ([System.IO.Path]::IsPathRooted($Normalized) -or $Normalized -match '^[A-Za-z]:') {
    Exit-WithError "Refusing to install outside the target project's .agents tree: $Value" 2
  }
  if ($Normalized.StartsWith("\\") -or $Normalized.StartsWith("//")) {
    Exit-WithError "Refusing to install outside the target project's .agents tree: $Value" 2
  }
  if ($Normalized -ne ".agents" -and -not $Normalized.StartsWith(".agents\")) {
    Exit-WithError "Refusing to install outside the target project's .agents tree: $Value" 2
  }
  if ($Normalized -match '(^|[\\/])\.\.($|[\\/])') {
    Exit-WithError "Refusing path traversal in install prefix: $Value" 2
  }
  return $Normalized
}

$Prefix = Resolve-InstallPrefix $Prefix
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Payload = Join-Path $ScriptDir "payload"
$FilesPath = Join-Path $ScriptDir "payload-files.txt"

if (-not (Test-Path -LiteralPath $Payload -PathType Container) -or -not (Test-Path -LiteralPath $FilesPath -PathType Leaf)) {
  Exit-WithError "Package payload is incomplete." 1
}

__DEPENDENCY_NOTE__

$Files = Get-Content -LiteralPath $FilesPath | Where-Object { $_ -ne "" }

foreach ($Rel in $Files) {
  $RelPath = $Rel.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
  $Src = Join-Path $Payload $RelPath
  $Dst = Join-Path $Prefix $RelPath
  if ((Test-Path -LiteralPath $Dst -PathType Leaf) -and -not $Force) {
    $SrcHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Src).Hash
    $DstHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Dst).Hash
    if ($SrcHash -ne $DstHash) {
      Exit-WithError "Refusing to overwrite existing file without -Force: $Dst" 1
    }
  }
}

foreach ($Rel in $Files) {
  $RelPath = $Rel.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
  $Src = Join-Path $Payload $RelPath
  $Dst = Join-Path $Prefix $RelPath
  if ($DryRun) {
    Write-Host "would install $Dst"
    continue
  }
  $DstDir = Split-Path -Parent $Dst
  New-Item -ItemType Directory -Force -Path $DstDir | Out-Null
  Copy-Item -LiteralPath $Src -Destination $Dst -Force
}

if (-not $DryRun) {
  $ManifestDir = Join-Path $Prefix "plantuml-ai-skill"
  New-Item -ItemType Directory -Force -Path $ManifestDir | Out-Null
  $ManifestPath = Join-Path $ManifestDir "install-manifest.json"
  $Manifest = [ordered]@{
    package_name = $PackageName
    version = $PackageVersion
    source_commit = $SourceCommit
    prefix = $Prefix
    files = @($Files)
  }
  $Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $ManifestPath -Encoding UTF8
}

if ((-not $DryRun) -and $NeedsAssets -eq "1" -and (-not $NoAssets)) {
  $Cli = Join-Path $Prefix "bin\plantuml-ai.cmd"
  if ($OfflineJar) {
    & $Cli init-assets --offline-jar $OfflineJar
  } else {
    & $Cli init-assets
  }
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

if ($DryRun) {
  Write-Host "Dry run completed for $PackageName $PackageVersion"
} else {
  Write-Host "Installed $PackageName $PackageVersion into $Prefix"
}
"""
    return (
        template.replace("__PACKAGE_NAME__", tier.name)
        .replace("__PACKAGE_VERSION__", version)
        .replace("__SOURCE_COMMIT__", source_commit)
        .replace("__NEEDS_ASSETS__", needs_assets)
        .replace("__DEPENDENCY_NOTE__", dependency_note)
    )


def _windows_install_cmd() -> str:
    return """@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
exit /b %ERRORLEVEL%
"""


def _plantuml_ai_wrapper() -> str:
    return """#!/bin/sh
set -eu

self_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
agents_root=$(CDPATH= cd -- "$self_dir/.." && pwd)
runtime_src="$agents_root/tools/plantuml-ai-skill/src"

find_runtime_python() {
  for candidate in python3.12 python3.11 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 &&
      "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' >/dev/null 2>&1; then
      printf '%s\\n' "$candidate"
      return 0
    fi
  done
  return 1
}

if [ -d "$runtime_src/plantuml_ai_skill" ]; then
  runtime_python=$(find_runtime_python) || {
    echo "plantuml-ai runtime packages require Python 3.11 or newer on PATH." >&2
    exit 2
  }
  if [ -n "${PYTHONPATH:-}" ]; then
    export PYTHONPATH="$runtime_src:$PYTHONPATH"
  else
    export PYTHONPATH="$runtime_src"
  fi
  exec "$runtime_python" -m plantuml_ai_skill.consumer_cli --agents-root "$agents_root" "$@"
fi

case "${1:-}" in
  validate)
    shift
    exec python3 "$agents_root/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py" "$@"
    ;;
  ""|-h|--help)
    echo "Usage: plantuml-ai validate <attempt.md|diagram.puml> [options]" >&2
    exit 0
    ;;
  *)
    echo "This package only installs 'plantuml-ai validate'. Install plantuml-diagram-render or plantuml-diagram-c4 for '$1'." >&2
    exit 2
    ;;
esac
"""


def _windows_plantuml_ai_wrapper() -> str:
    return r"""$ErrorActionPreference = "Stop"

$SelfDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentsRoot = Resolve-Path -LiteralPath (Join-Path $SelfDir "..")
$RuntimeSrc = Join-Path $AgentsRoot "tools\plantuml-ai-skill\src"

function New-PythonCandidate {
  param([string]$Exe, [string[]]$Args = @())
  [pscustomobject]@{ Exe = $Exe; Args = $Args }
}

function Test-PythonCandidate {
  param([object]$Candidate, [bool]$Require311)
  if ($null -eq $Candidate -or [string]::IsNullOrWhiteSpace($Candidate.Exe)) {
    return $false
  }
  $Code = if ($Require311) {
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
  } else {
    "import sys"
  }
  try {
    & $Candidate.Exe @($Candidate.Args) -c $Code > $null 2>&1
    return $LASTEXITCODE -eq 0
  } catch {
    return $false
  }
}

function Find-RuntimePython {
  $Candidates = @(
    (New-PythonCandidate -Exe $env:PLANTUML_PYTHON),
    (New-PythonCandidate -Exe "py" -Args @("-3.12")),
    (New-PythonCandidate -Exe "py" -Args @("-3.11")),
    (New-PythonCandidate -Exe "python"),
    (New-PythonCandidate -Exe "python3")
  )
  foreach ($Candidate in $Candidates) {
    if (Test-PythonCandidate -Candidate $Candidate -Require311 $true) {
      return $Candidate
    }
  }
  return $null
}

function Find-PortablePython {
  $Candidates = @(
    (New-PythonCandidate -Exe $env:PLANTUML_PYTHON),
    (New-PythonCandidate -Exe "py" -Args @("-3")),
    (New-PythonCandidate -Exe "python"),
    (New-PythonCandidate -Exe "python3")
  )
  foreach ($Candidate in $Candidates) {
    if (Test-PythonCandidate -Candidate $Candidate -Require311 $false) {
      return $Candidate
    }
  }
  return $null
}

if (Test-Path -LiteralPath (Join-Path $RuntimeSrc "plantuml_ai_skill") -PathType Container) {
  $RuntimePython = Find-RuntimePython
  if ($null -eq $RuntimePython) {
    [Console]::Error.WriteLine("plantuml-ai runtime packages require Python 3.11 or newer on PATH or through the Python launcher.")
    exit 2
  }
  if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$RuntimeSrc;$env:PYTHONPATH"
  } else {
    $env:PYTHONPATH = $RuntimeSrc
  }
  & $RuntimePython.Exe @($RuntimePython.Args) -m plantuml_ai_skill.consumer_cli --agents-root $AgentsRoot @args
  exit $LASTEXITCODE
}

if ($args.Count -eq 0 -or $args[0] -eq "-h" -or $args[0] -eq "--help") {
  [Console]::Error.WriteLine("Usage: plantuml-ai validate <attempt.md|diagram.puml> [options]")
  exit 0
}

if ($args[0] -ne "validate") {
  [Console]::Error.WriteLine("This package only installs 'plantuml-ai validate'. Install plantuml-diagram-render or plantuml-diagram-c4 for '$($args[0])'.")
  exit 2
}

$PortablePython = Find-PortablePython
if ($null -eq $PortablePython) {
  [Console]::Error.WriteLine("plantuml-ai validate requires Python on PATH or through the Python launcher.")
  exit 2
}

$Validator = Join-Path $AgentsRoot "skills\plantuml-diagram\scripts\validate_plantuml_attempt.py"
$Remaining = @()
if ($args.Count -gt 1) {
  $Remaining = $args[1..($args.Count - 1)]
}
& $PortablePython.Exe @($PortablePython.Args) $Validator @Remaining
exit $LASTEXITCODE
"""


def _windows_plantuml_ai_cmd() -> str:
    return """@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0plantuml-ai.ps1" %*
exit /b %ERRORLEVEL%
"""


def _resolve_c4_source(c4_source: Path | None, workspace: Path) -> Path | None:
    if c4_source is not None:
        if not c4_source.exists():
            raise FileNotFoundError(f"C4 source not found: {c4_source}")
        return c4_source
    local = PROJECT_ROOT / "data" / "vendor" / "c4-plantuml"
    if local.exists():
        return local
    return _download_c4(workspace)


def _download_c4(workspace: Path) -> Path:
    archive = workspace / "c4-plantuml.tar.gz"
    with urllib.request.urlopen(C4_ARCHIVE_URL, timeout=60) as response:
        archive.write_bytes(response.read())
    extract_dir = workspace / "c4-plantuml"
    extract_dir.mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        _safe_extract(tar, extract_dir)
    children = [path for path in extract_dir.iterdir() if path.is_dir()]
    if len(children) != 1:
        raise RuntimeError("unexpected C4-PlantUML archive layout")
    return children[0]


def _safe_extract(tar: tarfile.TarFile, destination: Path) -> None:
    root = destination.resolve()
    for member in tar.getmembers():
        target = (destination / member.name).resolve()
        if root not in [target, *target.parents]:
            raise RuntimeError(f"unsafe path in C4 archive: {member.name}")
    if sys.version_info >= (3, 12):
        tar.extractall(destination, filter="data")
    else:
        tar.extractall(destination)


def _write_deterministic_tar_gz(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for path in sorted(source_dir.rglob("*")):
                    arcname = path.relative_to(source_dir.parent).as_posix()
                    info = tar.gettarinfo(str(path), arcname)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    if path.is_file():
                        with path.open("rb") as handle:
                            tar.addfile(info, handle)
                    else:
                        tar.addfile(info)


def _write_deterministic_zip(source_dir: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(source_dir.rglob("*")):
            arcname = path.relative_to(source_dir.parent).as_posix()
            if path.is_dir() and not arcname.endswith("/"):
                arcname += "/"
            info = zipfile.ZipInfo(arcname, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            if path.is_dir():
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (0o40755 << 16) | 0x10
                zf.writestr(info, b"")
            else:
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o100755 if path.name.endswith((".sh", ".cmd", ".ps1")) or path.name == "plantuml-ai" else 0o100644
                info.external_attr = mode << 16
                zf.writestr(info, path.read_bytes())


def _write_sha256sums(outputs: list[Path], path: Path) -> Path:
    lines = []
    for output in sorted(outputs, key=lambda item: item.name):
        digest = hashlib.sha256(output.read_bytes()).hexdigest()
        lines.append(f"{digest}  {output.name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unknown"
    return proc.stdout.strip() or "unknown"
