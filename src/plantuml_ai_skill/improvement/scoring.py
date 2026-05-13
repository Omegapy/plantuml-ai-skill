"""Scoring helpers for deterministic skill evaluation."""

from __future__ import annotations

from .models import SkillEvaluationResult


WEIGHTS = {
    "extract_status": 0.10,
    "syntax_status": 0.10,
    "diagram_type_status": 0.10,
    "include_policy_status": 0.10,
    "render_status": 0.25,
    "semantic_status": 0.25,
    "output_contract_status": 0.10,
}


def score_statuses(statuses: dict[str, str]) -> float:
    score = 0.0
    for key, weight in WEIGHTS.items():
        if statuses.get(key) == "ok":
            score += weight
    return round(score, 4)


def metrics_from_results(results: list[SkillEvaluationResult]) -> dict[str, float | int]:
    cases = len(results)
    if cases == 0:
        return {
            "cases": 0,
            "passed": 0,
            "average_score": 0.0,
            "render_ok_rate": 0.0,
            "semantic_pass_rate": 0.0,
            "remote_include_violations": 0,
        }
    passed = sum(result.score >= 0.9 and not result.failures for result in results)
    render_ok = sum(result.render_status == "ok" for result in results)
    semantic_ok = sum(result.semantic_status == "ok" for result in results)
    remote_include_violations = sum(
        1
        for result in results
        for failure in result.failures
        if failure.code == "remote_include_policy_violation"
    )
    return {
        "cases": cases,
        "passed": passed,
        "average_score": round(sum(result.score for result in results) / cases, 4),
        "render_ok_rate": round(render_ok / cases, 4),
        "semantic_pass_rate": round(semantic_ok / cases, 4),
        "remote_include_violations": remote_include_violations,
    }
