"""Promotion gates for candidate PlantUML skills."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ImprovementRun, PromotionDecision
from .state import APPROVALS_ROOT


def promotion_decision(
    run: ImprovementRun,
    baseline_metrics: dict[str, float | int] | None = None,
    unit_tests_passed: bool = False,
    human_approval_recorded: bool = False,
) -> PromotionDecision:
    baseline = baseline_metrics or {}
    metrics = run.metrics
    reasons: list[str] = []

    if not unit_tests_passed:
        reasons.append("unit_tests_not_recorded")
    if not human_approval_recorded:
        reasons.append("human_approval_missing")
    if int(metrics.get("remote_include_violations", 0)) != 0:
        reasons.append("remote_include_violations")
    if float(metrics.get("render_ok_rate", 0.0)) < float(baseline.get("render_ok_rate", 0.0)):
        reasons.append("render_ok_rate_regressed")
    baseline_semantic = float(baseline.get("semantic_pass_rate", 0.0))
    if float(metrics.get("semantic_pass_rate", 0.0)) < min(1.0, baseline_semantic + 0.02):
        reasons.append("semantic_pass_rate_gate_not_met")
    if int(metrics.get("protected_regressions", 0)) != 0:
        reasons.append("protected_regressions")

    return PromotionDecision(
        run_id=run.id,
        promote=not reasons,
        reasons=reasons,
        metrics=dict(metrics),
    )


def approval_path(run_id: str, approvals_root: Path = APPROVALS_ROOT) -> Path:
    return approvals_root / f"{run_id}.json"


def has_human_approval(run_id: str, approvals_root: Path = APPROVALS_ROOT) -> bool:
    path = approval_path(run_id, approvals_root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return data.get("run_id") == run_id and bool(data.get("approved_by")) and bool(data.get("approved_at"))
