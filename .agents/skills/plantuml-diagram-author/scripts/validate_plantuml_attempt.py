#!/usr/bin/env python3
"""Validate one PlantUML attempt with the repository evaluator."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


def _repo_src() -> Path:
    return Path(__file__).resolve().parents[4] / "src"


START_END_RE = re.compile(r"(?is)^\s*@start(?P<kind>[A-Za-z0-9_ -]*)\b.*@end(?P=kind)\b\s*$")
FENCED_PLANTUML_RE = re.compile(r"(?is)```(?:plantuml|puml)?\s*(?P<body>@start.*?@end[A-Za-z0-9_ -]*\b)\s*```")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", help="Path to a raw Codex response or PlantUML file")
    parser.add_argument("--case-id", default="manual")
    parser.add_argument("--expected-type", default="uml")
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--forbidden", action="append", default=["!includeurl", "TODO", "placeholder"])
    args = parser.parse_args()

    path = Path(args.attempt)
    puml_text = path.read_text(encoding="utf-8")
    try:
        return _validate_with_repo_evaluator(args, puml_text, path)
    except (ImportError, ModuleNotFoundError):
        return _validate_portable(args, puml_text)


def _validate_with_repo_evaluator(args: argparse.Namespace, puml_text: str, path: Path) -> int:
    repo_src = _repo_src()
    if repo_src.exists():
        sys.path.insert(0, str(repo_src))

    from plantuml_ai_skill.improvement.evaluator import evaluate_attempt
    from plantuml_ai_skill.improvement.models import SkillAttempt, SkillEvalCase

    case = SkillEvalCase(
        id=args.case_id,
        suite="manual",
        prompt="Manual validation",
        expected_diagram_type=args.expected_type,
        required_patterns=list(args.required),
        forbidden_patterns=list(args.forbidden),
        required_edges=[],
        include_policy="self_contained_only",
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
    result = evaluate_attempt(case, attempt, renderer=None)
    print(f"score={result.score:.3f}")
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
    blocks = [match.group("body").strip() for match in FENCED_PLANTUML_RE.finditer(text)]
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
    expected_type = args.expected_type.lower()
    if expected_type not in {"", "uml"}:
        actual_type = _portable_diagram_type(puml)
        if actual_type != expected_type:
            failures.append(("wrong_diagram_family", f"Expected diagram type {expected_type!r}, got {actual_type!r}."))
    return failures


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


if __name__ == "__main__":
    raise SystemExit(main())
