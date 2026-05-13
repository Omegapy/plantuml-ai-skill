"""Environment checks for the PlantUML pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
import shutil
import subprocess

from .constants import DEFAULT_JAR_PATH, MIN_JAVA_MAJOR, PLANTUML_JAR_SHA256
from .renderer import PlantUMLRenderer, default_java_bin, sha256_file


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str
    details: str = ""


def _run(command: list[str], timeout: int = 10) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def parse_java_major(version_output: str) -> int | None:
    match = re.search(r'version "([0-9]+)(?:\.([0-9]+))?', version_output)
    if not match:
        return None
    major = int(match.group(1))
    if major == 1 and match.group(2):
        return int(match.group(2))
    return major


def check_java(java_bin: str | None = None) -> Check:
    java_bin = java_bin or default_java_bin()
    proc = _run([java_bin, "-version"])
    if proc is None:
        return Check(
            "java",
            False,
            "Java runtime not found. Install Java 11 or newer before rendering.",
        )
    output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    if proc.returncode != 0 and "unable to locate a java runtime" in output.lower():
        return Check(
            "java",
            False,
            "Java runtime not found. Install Java 11 or newer before rendering.",
            output.strip(),
        )
    major = parse_java_major(output)
    if major is None:
        return Check("java", False, "Could not parse Java version.", output.strip())
    if major < MIN_JAVA_MAJOR:
        return Check(
            "java",
            False,
            f"Java {major} detected; Java {MIN_JAVA_MAJOR}+ is required.",
            output.strip(),
        )
    return Check("java", True, f"Java {major} detected.", output.strip())


def check_graphviz(dot_bin: str = "dot") -> Check:
    dot_path = shutil.which(dot_bin)
    if not dot_path:
        return Check("graphviz", False, "Graphviz 'dot' executable not found.")
    proc = _run([dot_path, "-V"])
    if proc is None:
        return Check("graphviz", False, "Could not execute Graphviz 'dot'.")
    output = (proc.stdout + proc.stderr).decode("utf-8", errors="replace").strip()
    return Check("graphviz", proc.returncode == 0, output or "Graphviz detected.", dot_path)


def check_jar(jar_path: Path | str = DEFAULT_JAR_PATH) -> Check:
    path = Path(jar_path)
    if not path.exists():
        return Check(
            "plantuml_jar",
            False,
            f"Pinned PlantUML jar is missing at {path}. Run 'plantuml-skill init-assets'.",
        )
    digest = sha256_file(path)
    if digest != PLANTUML_JAR_SHA256:
        return Check(
            "plantuml_jar",
            False,
            "Pinned PlantUML jar checksum mismatch.",
            f"expected {PLANTUML_JAR_SHA256}, got {digest}",
        )
    return Check("plantuml_jar", True, "Pinned PlantUML jar checksum verified.", digest)


def check_testdot(jar_path: Path | str = DEFAULT_JAR_PATH, java_bin: str | None = None) -> Check:
    java_bin = java_bin or default_java_bin()
    if not Path(jar_path).exists():
        return Check("plantuml_testdot", False, "Skipped -testdot because the jar is missing.")
    result = PlantUMLRenderer(jar_path=jar_path, java_bin=java_bin).testdot()
    details = (result.output.decode("utf-8", errors="replace") + "\n" + result.stderr).strip()
    if not result.ok:
        if result.returncode < 0 and not details:
            details = "PlantUML process was terminated before producing output."
        return Check("plantuml_testdot", False, "PlantUML -testdot failed.", details)
    return Check("plantuml_testdot", True, "PlantUML can reach Graphviz through -testdot.", details)


def run_doctor(jar_path: Path | str = DEFAULT_JAR_PATH, java_bin: str | None = None) -> list[Check]:
    java_bin = java_bin or default_java_bin()
    return [
        check_java(java_bin),
        check_graphviz(),
        check_jar(jar_path),
        check_testdot(jar_path, java_bin),
    ]
