#!/usr/bin/env python3
"""Validate one PlantUML attempt with the repository evaluator."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys


START_END_RE = re.compile(r"(?is)^\s*@start(?P<kind>[A-Za-z0-9_ -]*)\b.*?@end(?P=kind)\b\s*$")
PLANTUML_DOCUMENT_RE = re.compile(r"(?is)(@start(?P<kind>[A-Za-z0-9_ -]*)\b.*?@end(?P=kind)\b)")
FENCED_PLANTUML_RE = re.compile(r"(?is)```(?:plantuml|puml)?\s*(?P<body>@start.*?@end[A-Za-z0-9_ -]*\b)\s*```")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", help="Path to a raw Codex response or PlantUML file")
    parser.add_argument("--case-id", default="manual")
    parser.add_argument("--expected-type", default="uml")
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--required-edge", action="append", default=[])
    parser.add_argument("--forbidden", action="append", default=["!includeurl", "TODO", "placeholder"])
    parser.add_argument("--include-root", action="append", default=[])
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--render-dir", default="")
    parser.add_argument("--c4", action="store_true")
    parser.add_argument("--jar", default="")
    parser.add_argument("--java", default="")
    args = parser.parse_args()

    path = Path(args.attempt)
    puml_text = path.read_text(encoding="utf-8")
    try:
        return _validate_with_repo_evaluator(args, puml_text, path)
    except (ImportError, ModuleNotFoundError):
        if args.render:
            print("validator=portable")
            print("error=Render validation requires the plantuml-diagram-render or plantuml-diagram-c4 package.")
            return 2
        return _validate_portable(args, puml_text)


def _validate_with_repo_evaluator(args: argparse.Namespace, puml_text: str, path: Path) -> int:
    for src_root in _candidate_src_roots():
        if (src_root / "plantuml_ai_skill" / "improvement" / "evaluator.py").exists():
            sys.path.insert(0, str(src_root))
            break

    from plantuml_ai_skill.improvement.evaluator import evaluate_attempt
    from plantuml_ai_skill.improvement.models import SkillAttempt, SkillEvalCase
    from plantuml_ai_skill.constants import DEFAULT_JAR_PATH
    from plantuml_ai_skill.renderer import PlantUMLRenderer

    include_roots = _include_roots(args)
    renderer = (
        PlantUMLRenderer(
            jar_path=args.jar or DEFAULT_JAR_PATH,
            java_bin=args.java or None,
            include_roots=include_roots,
        )
        if args.render
        else None
    )
    include_policy = "local_includes_allowed" if include_roots else "self_contained_only"

    case = SkillEvalCase(
        id=args.case_id,
        suite="manual",
        prompt="Manual validation",
        expected_diagram_type=args.expected_type,
        required_patterns=list(args.required),
        forbidden_patterns=list(args.forbidden),
        required_edges=_required_edges(args.required_edge),
        include_policy=include_policy,
        purpose=["manual"],
        difficulty="manual",
        tags=["manual"],
    )
    attempt = SkillAttempt(
        id=f"manual-{args.case_id}",
        run_id="manual",
        skill_version_id="manual",
        case_id=args.case_id,
        model_or_agent="manual",
        created_at="manual",
        raw_response_path=str(path),
        puml_text=puml_text,
    )
    result = evaluate_attempt(
        case,
        attempt,
        renderer=renderer,
        render_dir=Path(args.render_dir) if args.render_dir else None,
        include_roots=include_roots,
    )
    print(f"score={result.score:.3f}")
    print(f"render_status={result.render_status}")
    for failure in result.failures:
        print(f"{failure.code}: {failure.message}")
    if result.render_status == "skipped":
        print("note=Render validation was skipped by this lightweight helper.")
    return 0 if not result.failures else 1


def _validate_portable(args: argparse.Namespace, text: str) -> int:
    failures = _portable_failures(args, text)
    score = 1.0 if not failures else 0.0
    print("validator=portable")
    print("note=Install the plantuml_ai_skill package for full repo evaluator checks.")
    print(f"score={score:.3f}")
    for code, message in failures:
        print(f"{code}: {message}")
    return 0 if not failures else 1


def _portable_failures(args: argparse.Namespace, text: str) -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    blocks = _portable_blocks(text)
    if len(blocks) > 1:
        failures.append(("multiple_plantuml_blocks", f"Expected one PlantUML block, found {len(blocks)}."))
    puml = blocks[0] if blocks else text.strip()
    if not puml:
        failures.append(("empty_attempt", "No PlantUML text was found."))
        return failures
    if not START_END_RE.match(puml):
        failures.append(("invalid_start_end_pair", "PlantUML does not have a valid matching @start/@end pair."))
    for pattern in args.forbidden:
        if pattern and pattern.lower() in text.lower():
            failures.append(("forbidden_output_pattern", f"Forbidden pattern was present: {pattern!r}."))
    for pattern in args.required:
        if pattern and pattern.lower() not in puml.lower():
            failures.append(("missing_required_pattern", f"Required pattern is missing: {pattern!r}."))
    for left, right in _required_edges(args.required_edge):
        if not _portable_has_edge(puml, left, right):
            failures.append(("missing_required_edge", f"Required relationship is missing: {left!r} -> {right!r}."))
    expected_type = args.expected_type.lower()
    if expected_type not in {"", "uml"}:
        actual_type = _portable_diagram_type(puml)
        if actual_type != expected_type:
            failures.append(("wrong_diagram_family", f"Expected diagram type {expected_type!r}, got {actual_type!r}."))
    return failures


def _portable_blocks(text: str) -> list[str]:
    fenced = [match.group("body").strip() for match in FENCED_PLANTUML_RE.finditer(text)]
    if fenced:
        return fenced
    return [match.group(1).strip() for match in PLANTUML_DOCUMENT_RE.finditer(text)]


def _portable_diagram_type(puml: str) -> str:
    lowered = puml.lower()
    if any(token in lowered for token in ("person(", "container(", "system_boundary(", "rel(")):
        return "c4"
    if re.search(r"(?m)^\s*(actor|usecase)\b", lowered):
        return "usecase"
    if re.search(r"(?m)^\s*(component|node|cloud|database|queue)\b", lowered):
        return "component"
    if re.search(r"(?m)^\s*(class|interface|enum)\b", lowered):
        return "class"
    if "state " in lowered or "[*]" in lowered:
        return "state"
    if re.search(r"(?m)^\s*(start|stop|if |switch |repeat|while |fork|split)\b", lowered):
        return "activity"
    if re.search(r"[-.]+[->]+|<[-.]+", lowered):
        return "sequence"
    return "uml"


def _portable_has_edge(puml: str, left: str, right: str) -> bool:
    left = left.lower()
    right = right.lower()
    for line in puml.splitlines():
        lowered = line.lower()
        if left in lowered and right in lowered:
            between = lowered[min(lowered.find(left), lowered.find(right)) : max(lowered.find(left), lowered.find(right))]
            if "->" in between or "-->" in between or "--" in between or ".." in between:
                return True
    return False


def _required_edges(values: list[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for value in values:
        if "->" not in value:
            raise ValueError(f"--required-edge must use A->B syntax: {value!r}")
        left, right = value.split("->", 1)
        edges.append((left.strip(), right.strip()))
    return edges


def _include_roots(args: argparse.Namespace) -> list[Path]:
    roots = [Path(value) for value in args.include_root]
    if args.c4:
        agents_root = _agents_root()
        if agents_root is not None:
            roots.append(agents_root / "vendor" / "c4-plantuml")
    return roots


def _candidate_src_roots() -> list[Path]:
    roots: list[Path] = []
    script = Path(__file__).resolve()
    if "PLANTUML_AI_SKILL_SRC" in os.environ:
        roots.append(Path(os.environ["PLANTUML_AI_SKILL_SRC"]))
    if len(script.parents) > 4:
        roots.append(script.parents[4] / "src")
    agents_root = _agents_root()
    if agents_root is not None:
        roots.append(agents_root / "tools" / "plantuml-ai-skill" / "src")
    return roots


def _agents_root() -> Path | None:
    script = Path(__file__).resolve()
    for parent in script.parents:
        if parent.name == ".agents":
            return parent
    return None


if __name__ == "__main__":
    raise SystemExit(main())
