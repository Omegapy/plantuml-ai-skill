"""Failure clustering and lesson generation for improvement runs."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json

from .models import FailureCluster, SkillEvaluationResult, SkillLesson


CLUSTER_ALIASES = {
    "multiple_plantuml_blocks": "generated_markdown_instead_of_single_puml",
    "no_plantuml_block": "generated_markdown_instead_of_single_puml",
    "invalid_start_end_pair": "invalid_plantuml_document_shape",
    "wrong_diagram_family": "wrong_diagram_family",
    "remote_include_policy_violation": "remote_include_policy_violation",
    "include_policy_violation": "include_policy_violation",
    "include_resolution_failed": "c4_macro_used_without_include",
    "missing_required_pattern": "omitted_required_actor",
    "missing_required_edge": "missing_required_relationship",
    "render_timeout": "render_timeout",
    "graphviz_layout_failure": "graphviz_layout_failure",
    "render_failed": "render_failed",
    "missing_attempt": "missing_attempt",
    "palette_policy_violation": "palette_policy_violation",
    "render_palette_check_skipped": "render_palette_policy_violation",
    "render_palette_policy_violation": "render_palette_policy_violation",
}


def cluster_failures(results: list[SkillEvaluationResult]) -> list[FailureCluster]:
    buckets: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for result in results:
        for failure in result.failures:
            cluster_id = CLUSTER_ALIASES.get(failure.code, failure.code)
            buckets[cluster_id].append((result.case_id, failure.severity, failure.message))
    clusters: list[FailureCluster] = []
    for cluster_id, evidence in buckets.items():
        severity = "error" if any(item[1] == "error" for item in evidence) else evidence[0][1]
        clusters.append(
            FailureCluster(
                id=cluster_id,
                count=len(evidence),
                severity=severity,
                evidence_case_ids=sorted({item[0] for item in evidence}),
                messages=sorted({item[2] for item in evidence})[:5],
            )
        )
    return sorted(clusters, key=lambda item: (-item.count, item.id))


def write_failure_report(clusters: list[FailureCluster], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".json":
        output.write_text(
            json.dumps([cluster.to_mapping() for cluster in clusters], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output
    lines = ["# Failure Clusters", ""]
    if not clusters:
        lines.append("No failure clusters recorded.")
    for cluster in clusters:
        lines.append(f"## {cluster.id}")
        lines.append("")
        lines.append(f"- count: `{cluster.count}`")
        lines.append(f"- severity: `{cluster.severity}`")
        lines.append(f"- evidence: {', '.join(cluster.evidence_case_ids)}")
        for message in cluster.messages:
            lines.append(f"- message: {message}")
        lines.append("")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def lessons_from_failures(clusters: list[FailureCluster]) -> list[SkillLesson]:
    lessons: list[SkillLesson] = []
    for cluster in clusters:
        instruction = _lesson_instruction(cluster.id)
        if not instruction:
            continue
        lessons.append(
            SkillLesson(
                id=f"lesson-{cluster.id}",
                trigger=cluster.id,
                instruction=instruction,
                evidence_case_ids=cluster.evidence_case_ids,
            )
        )
    return lessons


def write_lessons(lessons: list[SkillLesson], path: Path | str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps([lesson.to_mapping() for lesson in lessons], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _lesson_instruction(cluster_id: str) -> str:
    return {
        "generated_markdown_instead_of_single_puml": "For single-diagram requests, output exactly one complete PlantUML document and avoid extra PlantUML blocks.",
        "invalid_plantuml_document_shape": "Always check that the generated document has a matching @start... and @end... pair.",
        "wrong_diagram_family": "Choose the diagram family from the user's requested relationships and workflow, not from a single ambiguous keyword.",
        "remote_include_policy_violation": "Do not use remote !includeurl in generated diagrams; prefer self-contained PlantUML or local vendored includes.",
        "include_policy_violation": "Use self-contained PlantUML unless the request explicitly needs a local or vendored include.",
        "c4_macro_used_without_include": "When using C4 macros, include the required vendored C4 file or avoid C4 macros.",
        "omitted_required_actor": "List the user's named actors/entities before drawing relationships so none are omitted.",
        "missing_required_relationship": "Add explicit relationships for every requested interaction, ownership, dependency, or transition.",
        "render_failed": "Prefer simple PlantUML syntax that renders through the pinned Java PlantUML jar.",
        "palette_policy_violation": "When the AEther palette is required, insert the dark PlantUML style block immediately after @start... and use only contract colors.",
        "render_palette_policy_violation": "For strict AEther rendered palette cases, use the certified family style block and avoid unstyleable PlantUML pseudo-nodes or fallback colors.",
    }.get(cluster_id, "")
