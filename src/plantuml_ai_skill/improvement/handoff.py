"""Codex prompt artifacts that bridge improvement runs across conversations."""

from __future__ import annotations

from pathlib import Path

from .eval_cases import load_eval_cases
from .models import FailureCluster, ImprovementRun
from .palette import PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED, PALETTE_POLICY_AETHER_DARK_REQUIRED


def write_codex_generation_prompt(run: ImprovementRun) -> Path:
    path = Path(run.suite_path)
    cases = load_eval_cases(path) if path.exists() else []
    output = Path(run.next_handoff_path).with_name("codex-generate-attempts-prompt.md")
    lines = [
        "# Codex Attempt Generation Prompt",
        "",
        "Use the `plantuml-diagram` skill.",
        "",
        "For each eval case below, generate exactly one PlantUML diagram that follows the case prompt.",
        "Store each response as a Markdown file named `<case-id>.md` in this run's `codex_responses/` directory.",
        "",
        f"- run: `{run.id}`",
        f"- suite: `{run.suite_path}`",
        "- local C4 include root: `data/vendor/c4-plantuml`",
        "",
        "## Cases",
        "",
    ]
    for case in cases:
        if case.hidden:
            continue
        lines.extend(
            [
                f"### {case.id}",
                "",
                case.prompt,
                "",
                f"- expected type: `{case.expected_diagram_type}`",
                f"- include policy: `{case.include_policy}`",
                f"- palette policy: `{case.palette_policy}`",
                *_case_guidance(case.expected_diagram_type, case.include_policy),
                *_palette_guidance(case.palette_policy),
                "",
            ]
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def _case_guidance(expected_diagram_type: str, include_policy: str) -> list[str]:
    if expected_diagram_type.lower() == "c4" and include_policy != "self_contained_only":
        return [
            "- C4 guidance: use `!include <C4/C4_Container.puml>`; repo validation maps it to the vendored C4 snapshot; do not reimplement C4 macros inline.",
        ]
    return []


def _palette_guidance(palette_policy: str) -> list[str]:
    if palette_policy == PALETTE_POLICY_AETHER_DARK_REQUIRED:
        return [
            "- Palette guidance: insert the AEther dark PlantUML style block immediately after `@start...` and use only contract colors.",
        ]
    if palette_policy == PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED:
        return [
            "- Palette guidance: insert the certified AEther dark family style block immediately after `@start...`; rendered SVG must have no warning banner, no fallback colors, and readable role contrast.",
        ]
    return []


def write_codex_next_prompt(run: ImprovementRun, clusters: list[FailureCluster]) -> Path:
    output = Path(run.next_handoff_path)
    lines = [
        "# Codex Handoff: PlantUML Skill Improvement",
        "",
        "## Goal",
        "",
        "Improve the repo-scoped PlantUML skill based on the latest deterministic evaluation report.",
        "",
        "## Read First",
        "",
        f"- `{run.suite_path}`",
        f"- `{run.attempts_path}`",
        f"- `{run.results_path}`",
        f"- `{run.report_path}`",
        f"- `{output.parent / 'failure-clusters.json'}`",
        "- `.agents/skills/plantuml-diagram/SKILL.md`",
        "- `.agents/skills/plantuml-skill-improver/SKILL.md`",
        "",
        "## Current Metrics",
        "",
    ]
    if run.metrics:
        for key, value in sorted(run.metrics.items()):
            lines.append(f"- `{key}`: {value}")
    else:
        lines.append("- No metrics recorded yet.")
    lines.extend(["", "## Top Failure Clusters", ""])
    if clusters:
        for cluster in clusters[:10]:
            evidence = ", ".join(cluster.evidence_case_ids)
            lines.append(f"- `{cluster.id}` count={cluster.count} evidence={evidence}")
    else:
        lines.append("- No failure clusters recorded.")
    lines.extend(
        [
            "",
            "## Allowed Edits",
            "",
            "- `.agents/skills/plantuml-diagram/**`",
            "- `.agents/skills/plantuml-skill-improver/**`",
            "- `src/plantuml_ai_skill/improvement/**`",
            "- `tests/test_improvement_*.py`",
            "- `docs/implementation/skill-improvement-system.md`",
            "- `docs/implementation/codex-human-loop.md`",
            "",
            "## Do Not Edit",
            "",
            "- generated rendered files except under `data/improvement/runs/`",
            "- downloaded jars",
            "- vendored external corpora",
            "- unrelated source modules unless required by tests",
            "",
            "## Required Commands",
            "",
            "```bash",
            "python -m unittest discover -s tests -v",
            "plantuml-skill improve evaluate --run latest",
            "plantuml-skill improve diagnose --run latest",
            "plantuml-skill improve next-prompt --run latest",
            "```",
            "",
            "## Definition Of Done",
            "",
            "- Tests pass.",
            "- Candidate skill improves or preserves protected metrics.",
            "- No new remote include violations.",
            "- Final response lists changed files, test results, and remaining risks.",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output
