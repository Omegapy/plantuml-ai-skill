#!/usr/bin/env python3
"""Validate one PlantUML attempt with the repository evaluator."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _repo_src() -> Path:
    return Path(__file__).resolve().parents[4] / "src"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", help="Path to a raw Codex response or PlantUML file")
    parser.add_argument("--case-id", default="manual")
    parser.add_argument("--expected-type", default="uml")
    parser.add_argument("--required", action="append", default=[])
    parser.add_argument("--forbidden", action="append", default=["!includeurl", "TODO", "placeholder"])
    args = parser.parse_args()

    sys.path.insert(0, str(_repo_src()))
    from plantuml_ai_skill.improvement.evaluator import evaluate_attempt
    from plantuml_ai_skill.improvement.models import SkillAttempt, SkillEvalCase

    path = Path(args.attempt)
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
        puml_text=path.read_text(encoding="utf-8"),
    )
    result = evaluate_attempt(case, attempt, renderer=None)
    print(f"score={result.score:.3f}")
    for failure in result.failures:
        print(f"{failure.code}: {failure.message}")
    return 0 if result.score >= 0.9 and not result.failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
