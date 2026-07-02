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
from .palette import (
    PALETTE_POLICY_AETHER_DARK_REQUIRED,
    PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED,
    PALETTE_POLICY_NONE,
    aether_dark_palette_issues,
    aether_dark_rendered_palette_issues,
    has_rendered_palette_issues,
)
from .scoring import metrics_from_results, score_statuses


START_END_RE = re.compile(r"(?is)^\s*@start(?P<kind>[A-Za-z0-9_ -]*)\b.*@end(?P=kind)\b\s*$")
RELATION_RE = re.compile(r"[-.]+[->ox*]+|<[-.]+|[*o]--|--[*o]?|\\.\\.|-->|->")
DECLARATION_ALIAS_RE = re.compile(
    r'(?im)^\s*(?:actor|participant|boundary|control|entity|database|collections|queue|component|node|cloud|class|interface|enum|usecase)\s+"(?P<label>[^"]+)"\s+as\s+(?P<alias>[A-Za-z_][\w.]*)'
)
BRACKET_ALIAS_RE = re.compile(r"(?im)^\s*\[(?P<label>[^\]]+)\]\s+as\s+(?P<alias>[A-Za-z_][\w.]*)")
C4_ALIAS_RE = re.compile(
    r'(?i)\b(?:Person|System|Container|Component|Database|Queue|Boundary|System_Boundary|Container_Boundary|Component_Boundary)\(\s*(?P<alias>[A-Za-z_][\w.]*)\s*,\s*"(?P<label>[^"]+)"'
)


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
        puml,
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
    if _palette_policy_failed(case, puml, failures):
        failed = True
    return "failed" if failed else "ok"


def _palette_policy_failed(case: SkillEvalCase, puml: str, failures: list[Failure]) -> bool:
    if case.palette_policy == PALETTE_POLICY_NONE:
        return False
    if case.palette_policy not in {
        PALETTE_POLICY_AETHER_DARK_REQUIRED,
        PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED,
    }:
        failures.append(
            Failure(
                "invalid_palette_policy",
                f"Unknown palette policy: {case.palette_policy}.",
                details={"palette_policy": case.palette_policy},
            )
        )
        return True
    missing, unapproved = aether_dark_palette_issues(puml)
    if not missing and not unapproved:
        return False
    failures.append(
        Failure(
            "palette_policy_violation",
            "PlantUML does not satisfy the AEther dark palette contract.",
            details={"missing_required_colors": missing, "unapproved_colors": unapproved},
        )
    )
    return True


def _render_status(
    case: SkillEvalCase,
    source_puml: str,
    render_puml: str,
    renderer: PlantUMLRenderer | None,
    failures: list[Failure],
    render_dir: Path | None,
) -> tuple[str, str, Path | None]:
    if renderer is None:
        if case.palette_policy == PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED:
            failures.append(
                Failure(
                    "render_palette_check_skipped",
                    "AEther rendered palette policy requires renderer output, but rendering was skipped.",
                    details={"palette_policy": case.palette_policy},
                )
            )
            return "failed", "", None
        return "skipped", "", None
    result = renderer.render_svg(render_puml)
    if not result.ok:
        failures.append(
            Failure(
                _render_failure_code(result.stderr),
                result.stderr or f"PlantUML renderer returned {result.returncode}.",
                details={"returncode": result.returncode},
            )
        )
        return "failed", "", None
    if case.palette_policy == PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED:
        issues = aether_dark_rendered_palette_issues(
            result.output,
            puml=source_puml,
            diagram_type=case.expected_diagram_type,
        )
        if has_rendered_palette_issues(issues):
            failures.append(
                Failure(
                    "render_palette_policy_violation",
                    "Rendered SVG does not satisfy the AEther dark render palette contract.",
                    details=issues,
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
    aliases = _aliases_by_label(puml)
    left_terms = _candidate_terms(left, aliases)
    right_terms = _candidate_terms(right, aliases)
    for line in puml.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("'"):
            continue
        lowered = stripped.lower()
        for left_term in left_terms:
            left_index = lowered.find(left_term)
            if left_index < 0:
                continue
            for right_term in right_terms:
                right_index = lowered.find(right_term)
                if right_index < 0:
                    continue
                if left_index < right_index:
                    middle = stripped[left_index + len(left_term) : right_index]
                else:
                    middle = stripped[right_index + len(right_term) : left_index]
                if RELATION_RE.search(middle):
                    return True
    return False


def _candidate_terms(label: str, aliases: dict[str, set[str]]) -> set[str]:
    normalized = label.lower()
    terms = {normalized}
    terms.update(aliases.get(normalized, set()))
    return {term for term in terms if term}


def _aliases_by_label(puml: str) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    for pattern in (DECLARATION_ALIAS_RE, BRACKET_ALIAS_RE, C4_ALIAS_RE):
        for match in pattern.finditer(puml):
            label = match.group("label").strip().lower()
            alias = match.group("alias").strip().lower()
            aliases.setdefault(label, set()).add(alias)
    return aliases
