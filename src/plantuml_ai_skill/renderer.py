"""PlantUML rendering through the pinned Java jar."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

from .constants import DEFAULT_JAR_PATH, PLANTUML_VERSION


def default_java_bin() -> str:
    """Prefer explicit/Homebrew Java over macOS's missing-runtime wrapper."""

    env_java = os.environ.get("PLANTUML_JAVA")
    if env_java:
        return env_java
    for candidate in (
        "/opt/homebrew/opt/openjdk/bin/java",
        "/usr/local/opt/openjdk/bin/java",
    ):
        if Path(candidate).exists():
            return candidate
    return shutil.which("java") or "java"


@dataclass(frozen=True)
class RenderResult:
    ok: bool
    output: bytes
    stderr: str
    command: list[str]
    returncode: int


class PlantUMLRenderer:
    """Renderer that shells out to ``java -jar plantuml.jar``."""

    def __init__(
        self,
        jar_path: Path | str = DEFAULT_JAR_PATH,
        java_bin: str | None = None,
        graphviz_dot: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.jar_path = Path(jar_path)
        self.java_bin = java_bin or default_java_bin()
        self.graphviz_dot = graphviz_dot or shutil.which("dot") or "dot"
        self.timeout = timeout

    def render_svg(self, puml_text: str) -> RenderResult:
        return self._render(puml_text, "-tsvg")

    def render_png(self, puml_text: str) -> RenderResult:
        return self._render(puml_text, "-tpng")

    def testdot(self) -> RenderResult:
        command = [self.java_bin, "-jar", str(self.jar_path), "-testdot"]
        return self._run(command, input_text="")

    def command_for(self, output_format: str) -> list[str]:
        return [
            self.java_bin,
            "-Djava.awt.headless=true",
            "-DPLANTUML_SECURITY_PROFILE=SANDBOX",
            "-jar",
            str(self.jar_path),
            output_format,
            "-pipe",
            "-charset",
            "UTF-8",
        ]

    def _render(self, puml_text: str, output_format: str) -> RenderResult:
        command = self.command_for(output_format)
        return self._run(command, input_text=puml_text)

    def _run(self, command: list[str], input_text: str) -> RenderResult:
        env = os.environ.copy()
        env.setdefault("GRAPHVIZ_DOT", self.graphviz_dot)
        try:
            proc = subprocess.run(
                command,
                input=input_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return RenderResult(False, b"", str(exc), command, 127)
        except subprocess.TimeoutExpired as exc:
            return RenderResult(False, exc.stdout or b"", "render_timeout", command, 124)
        return RenderResult(
            ok=proc.returncode == 0,
            output=proc.stdout,
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            command=command,
            returncode=proc.returncode,
        )


class NativePlantUMLRenderer:
    """Optional fallback for environments that provide a native PlantUML binary."""

    def __init__(self, plantuml_bin: str = "plantuml", timeout: int = 30) -> None:
        self.plantuml_bin = plantuml_bin
        self.timeout = timeout

    def render_svg(self, puml_text: str) -> RenderResult:
        return self._render(puml_text, "-tsvg")

    def _render(self, puml_text: str, output_format: str) -> RenderResult:
        command = [self.plantuml_bin, output_format, "-pipe", "-charset", "UTF-8"]
        try:
            proc = subprocess.run(
                command,
                input=puml_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            return RenderResult(False, b"", str(exc), command, 127)
        return RenderResult(
            ok=proc.returncode == 0,
            output=proc.stdout,
            stderr=proc.stderr.decode("utf-8", errors="replace"),
            command=command,
            returncode=proc.returncode,
        )


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_version_label() -> str:
    return f"plantuml-java-jar-{PLANTUML_VERSION}"
