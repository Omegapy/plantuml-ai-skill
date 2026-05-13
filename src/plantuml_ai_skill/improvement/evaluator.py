"""Deterministic evaluator for Codex PlantUML attempts."""

from __future__ import annotations

from pathlib import Path
import re

from plantuml_ai_skill.extraction import classify_diagram_type, extract_plantuml_blocks
from plantuml_ai_skill.includes import (
    inline_resolved_includes,
    is_remote_include,
    parse_include_deps,
    resolve_include_deps,
    unresolved_resolution_reason,
)
from plantuml_ai_skill.renderer import PlantUMLRenderer
from plantuml_ai_skill.verify import svg_hash

from .attempts import attempt_text
from .models import Failure, SkillAttempt, SkillEvalCase, SkillEvaluationResult
from .scoring import metrics_from_results, score_statuses


START_END_RE = re.compile(r"(?is)^\s*@start(?P<kind>[A-Za-z0-9_ -]*)\b.*@end(?P=kind)\b\s*$")
RELATION_RE = re.compile(r"[-.]+[->ox*]+|<[-.]+|[*o]--|--[*o]?|\\.\\.|-->|->")


def evaluate_attempt(
    case: SkillEvalCase,
    attempt: SkillAttempt,
    renderer: PlantUMLRenderer | None,
    render_dir: Path | str | None = None,
    include_roots: list[Path] | None = None,
) -> SkillEvaluationResult:
    raw_text = attempt_text(attempt)
    blocks = extract_plantuml_blocks(raw_text)
    failures: list[Failure] = []

    if len(blocks) == 1:
        puml = blocks[0]
        extract_status = "ok"
    elif len(blocks) > 1 and case.allow_multiple_blocks:
        puml = blocks[0]
        extract_status = "ok"
    elif len(blocks) > 1:
        puml = blocks[0]
        extract_status = "failed"
        failures.append(
            Failure(
                "multiple_plantuml_blocks",
                f"Expected one PlantUML block, found {len(blocks)}.",
                details={"block_count": len(blocks)},
            )
        )
    else:
        puml = raw_text.strip()
        extract_status = "failed"
        failures.append(Failure("no_plantuml_block", "No complete PlantUML block was found."))

    syntax_status = _syntax_status(puml, failures)
    diagram_type_status = _diagram_type_status(case, puml, failures) if syntax_status == "ok" else "failed"
    include_policy_status, render_text = _include_policy_status(case, puml, failures, include_roots or [])
    semantic_status = _semantic_status(case, puml, failures) if extract_status == "ok" else "failed"
    output_contract_status = _output_contract_status(case, raw_text, puml, failures, len(blocks))
    render_status, render_hash, rendered_path = _render_status(
        case,
        render_text,
        renderer,
        failures,
        Path(render_dir) if render_dir else None,
    )

    statuses = {
        "extract_status": extract_status,
        "syntax_status": syntax_status,
        "diagram_type_status": diagram_type_status,
        "include_policy_status": include_policy_status,
        "render_status": render_status,
        "semantic_status": semantic_status,
        "output_contract_status": output_contract_status,
    }
    return SkillEvaluationResult(
        attempt_id=attempt.id,
        case_id=case.id,
        extract_status=extract_status,
        syntax_status=syntax_status,
        diagram_type_status=diagram_type_status,
        include_policy_status=include_policy_status,
        render_status=render_status,
        semantic_status=semantic_status,
        output_contract_status=output_contract_status,
        score=score_statuses(statuses),
        failures=failures,
        render_hash_svg=render_hash,
        rendered_svg_path=str(rendered_path or ""),
    )


def evaluate_attempts(
    cases: list[SkillEvalCase],
    attempts: list[SkillAttempt],
    renderer: PlantUMLRenderer | None,
    render_dir: Path | str | None = None,
    include_roots: list[Path] | None = None,
    allow_missing_attempts: bool = False,
) -> list[SkillEvaluationResult]:
    attempts_by_case = {attempt.case_id: attempt for attempt in attempts}
    results: list[SkillEvaluationResult] = []
    for case in cases:
        attempt = attempts_by_case.get(case.id)
        if attempt is None:
            if allow_missing_attempts:
                results.append(missing_attempt_result(case))
                continue
            raise ValueError(f"missing attempt for case: {case.id}")
        results.append(evaluate_attempt(case, attempt, renderer, render_dir, include_roots))
    return results


def missing_attempt_result(case: SkillEvalCase) -> SkillEvaluationResult:
    return SkillEvaluationResult(
        attempt_id=f"missing-{case.id}",
        case_id=case.id,
        extract_status="missing",
        syntax_status="missing",
        diagram_type_status="missing",
        include_policy_status="missing",
        render_status="missing",
        semantic_status="missing",
        output_contract_status="missing",
        score=0.0,
        failures=[Failure("missing_attempt", "No attempt was recorded for this case.")],
    )


def write_evaluation_report(
    results: list[SkillEvaluationResult],
    path: Path | str,
    title: str = "PlantUML Skill Evaluation Report",
) -> Path:
    metrics = metrics_from_results(results)
    lines = [
        f"# {title}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in metrics.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Failures", ""])
    failed = [result for result in results if result.failures]
    if not failed:
        lines.append("No failures recorded.")
    for result in failed:
        lines.append(f"### {result.case_id}")
        lines.append("")
        lines.append(f"- score: `{result.score}`")
        for failure in result.failures:
            lines.append(f"- `{failure.code}`: {failure.message}")
        lines.append("")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def _syntax_status(puml: str, failures: list[Failure]) -> str:
    if START_END_RE.match(puml):
        return "ok"
    failures.append(Failure("invalid_start_end_pair", "PlantUML does not have a valid matching @start/@end pair."))
    return "failed"


def _diagram_type_status(case: SkillEvalCase, puml: str, failures: list[Failure]) -> str:
    expected = case.expected_diagram_type.lower()
    actual = classify_diagram_type(puml).lower()
    if expected in {"", "uml", actual}:
        return "ok"
    failures.append(
        Failure(
            "wrong_diagram_family",
            f"Expected diagram type {case.expected_diagram_type!r}, got {actual!r}.",
            details={"expected": case.expected_diagram_type, "actual": actual},
        )
    )
    return "failed"


def _include_policy_status(
    case: SkillEvalCase,
    puml: str,
    failures: list[Failure],
    include_roots: list[Path],
) -> tuple[str, str]:
    includes = parse_include_deps(puml)
    remote = [target for target in includes if is_remote_include(target)]
    if remote and case.include_policy != "remote_includes_allowed":
        failures.append(
            Failure(
                "remote_include_policy_violation",
                "Remote includes are forbidden for this case.",
                details={"includes": remote},
            )
        )
        return "failed", puml
    if case.include_policy == "self_contained_only" and includes:
        failures.append(
            Failure(
                "include_policy_violation",
                "This case requires self-contained PlantUML, but includes were used.",
                details={"includes": includes},
            )
        )
        return "failed", puml
    if includes and include_roots:
        resolutions = resolve_include_deps(includes, include_roots)
        reason = unresolved_resolution_reason(resolutions)
        if reason:
            failures.append(
                Failure(
                    "include_resolution_failed",
                    f"Include resolution failed: {reason}.",
                    details={"includes": includes},
                )
            )
            return "failed", puml
        return "ok", inline_resolved_includes(puml, resolutions)
    return "ok", puml


def _semantic_status(case: SkillEvalCase, puml: str, failures: list[Failure]) -> str:
    missing_patterns = [
        pattern for pattern in case.required_patterns if pattern and pattern.lower() not in puml.lower()
    ]
    missing_edges = [edge for edge in case.required_edges if not _has_edge(puml, edge[0], edge[1])]
    if missing_patterns:
        failures.append(
            Failure(
                "missing_required_pattern",
                "Required prompt terms are missing from the PlantUML.",
                details={"patterns": missing_patterns},
            )
        )
    if missing_edges:
        failures.append(
            Failure(
                "missing_required_edge",
                "Required relationships are missing from the PlantUML.",
                details={"edges": [list(edge) for edge in missing_edges]},
            )
        )
    return "ok" if not missing_patterns and not missing_edges else "failed"


def _output_contract_status(
    case: SkillEvalCase,
    raw_text: str,
    puml: str,
    failures: list[Failure],
    block_count: int,
) -> str:
    failed = False
    if block_count == 0:
        failed = True
    if block_count > 1 and not case.allow_multiple_blocks:
        failed = True
    forbidden = [pattern for pattern in case.forbidden_patterns if pattern and pattern.lower() in raw_text.lower()]
    if forbidden:
        failures.append(
            Failure(
                "forbidden_output_pattern",
                "Forbidden patterns were present in the response.",
                details={"patterns": forbidden},
            )
        )
        failed = True
    if not puml.strip().lower().startswith("@start"):
        failed = True
    return "failed" if failed else "ok"


def _render_status(
    case: SkillEvalCase,
    puml: str,
    renderer: PlantUMLRenderer | None,
    failures: list[Failure],
    render_dir: Path | None,
) -> tuple[str, str, Path | None]:
    if renderer is None:
        return "skipped", "", None
    result = renderer.render_svg(puml)
    if not result.ok:
        failures.append(
            Failure(
                _render_failure_code(result.stderr),
                result.stderr or f"PlantUML renderer returned {result.returncode}.",
                details={"returncode": result.returncode},
            )
        )
        return "failed", "", None
    try:
        digest = svg_hash(result.output)
    except Exception as exc:
        failures.append(Failure("render_hash_failed", f"Rendered SVG could not be normalized: {exc}"))
        return "failed", "", None
    output_path = None
    if render_dir:
        render_dir.mkdir(parents=True, exist_ok=True)
        output_path = render_dir / f"{case.id}.svg"
        output_path.write_bytes(result.output)
    return "ok", digest, output_path


def _render_failure_code(stderr: str) -> str:
    lowered = stderr.lower()
    if "timeout" in lowered:
        return "render_timeout"
    if "dot" in lowered or "graphviz" in lowered:
        return "graphviz_layout_failure"
    return "render_failed"


def _has_edge(puml: str, left: str, right: str) -> bool:
    left_lower = left.lower()
    right_lower = right.lower()
    for line in puml.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("'"):
            continue
        lowered = stripped.lower()
        if left_lower not in lowered or right_lower not in lowered:
            continue
        left_index = lowered.find(left_lower)
        right_index = lowered.find(right_lower)
        if left_index < right_index:
            middle = stripped[left_index + len(left) : right_index]
        else:
            middle = stripped[right_index + len(right) : left_index]
        if RELATION_RE.search(middle):
            return True
    return False
