"""CLI implementation for the PlantUML skill improvement loop."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

from plantuml_ai_skill.config import load_sources_config
from plantuml_ai_skill.constants import DEFAULT_JAR_PATH, PROJECT_ROOT
from plantuml_ai_skill.renderer import PlantUMLRenderer

from .attempts import load_attempts, record_attempt_file, write_attempts
from .diagnostics import cluster_failures, lessons_from_failures, write_failure_report, write_lessons
from .eval_cases import (
    hand_authored_core_cases,
    load_eval_cases,
    make_eval_suite_from_manifest_paths,
    write_eval_cases,
)
from .evaluator import evaluate_attempts, write_evaluation_report
from .handoff import write_codex_generation_prompt, write_codex_next_prompt
from .models import ImprovementRun, SkillEvaluationResult, SkillVersion, read_jsonl, write_json, write_jsonl
from .promotion import has_human_approval, promotion_decision
from .scoring import metrics_from_results
from .skill_builder import (
    BUILDER_VERSION,
    REQUIRED_AUTHOR_REFERENCES,
    REQUIRED_IMPROVER_REFERENCES,
    SkillBuildConfig,
    build_skill_package,
    lint_skill_package,
    skill_hash,
)
from .state import (
    APPROVALS_ROOT,
    AUTHOR_SKILL_DIR,
    IMPROVEMENT_ROOT,
    IMPROVER_SKILL_DIR,
    PROJECT_ROOT as STATE_PROJECT_ROOT,
    RUNS_ROOT,
    SUITES_ROOT,
    ensure_improvement_dirs,
    git_commit,
    load_run,
    relative_to_project,
    resolve_run_dir,
    save_run,
    update_latest_run,
    utc_now,
)


def add_improve_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    improve = sub.add_parser("improve", help="run the skill improvement system")
    improve_sub = improve.add_subparsers(dest="improve_command", required=True)

    init = improve_sub.add_parser("init", help="create baseline skill-improvement directories")
    init.add_argument("--no-overwrite", action="store_true")

    lint = improve_sub.add_parser("lint-skill", help="lint repo-scoped PlantUML skill packages")
    lint.add_argument("--path", action="append", default=[])

    build = improve_sub.add_parser("build-skill", help="build the target PlantUML author skill")
    build.add_argument("--manifest", action="append", default=[])
    build.add_argument("--lessons", default="")
    build.add_argument("--output", default=str(AUTHOR_SKILL_DIR))
    build.add_argument("--max-examples", type=int, default=6)

    suite = improve_sub.add_parser("make-suite", help="build a deterministic skill eval suite")
    suite.add_argument("--manifest", action="append", default=[])
    suite.add_argument("--output", default=str(SUITES_ROOT / "core.jsonl"))
    suite.add_argument("--max-cases", type=int, default=100)

    begin = improve_sub.add_parser("begin-run", help="start a new improvement run")
    begin.add_argument("--suite", required=True)
    begin.add_argument("--run-id", default="")
    begin.add_argument("--baseline-skill-version-id", default="")
    begin.add_argument("--candidate-skill-version-id", default="")

    record = improve_sub.add_parser("record-attempt", help="record Codex output for one or more eval cases")
    record.add_argument("--run", required=True)
    record.add_argument("--case", default="")
    record.add_argument("--response-file", default="")
    record.add_argument("--responses-dir", default="")
    record.add_argument("--model-or-agent", default="codex-app")

    evaluate = improve_sub.add_parser("evaluate", help="evaluate recorded attempts")
    evaluate.add_argument("--run", required=True)
    evaluate.add_argument("--render-dir", default="")
    evaluate.add_argument("--jar", default=str(DEFAULT_JAR_PATH))
    evaluate.add_argument("--java", default="")
    evaluate.add_argument("--include-root", action="append", default=[])
    evaluate.add_argument("--allow-missing-attempts", action="store_true")
    evaluate.add_argument("--no-render", action="store_true")

    diagnose = improve_sub.add_parser("diagnose", help="cluster evaluation failures")
    diagnose.add_argument("--run", required=True)

    next_prompt = improve_sub.add_parser("next-prompt", help="write the next Codex handoff prompt")
    next_prompt.add_argument("--run", required=True)

    promote = improve_sub.add_parser("promote", help="evaluate promotion gates for a candidate skill")
    promote.add_argument("--run", required=True)
    promote.add_argument("--baseline-metrics", default="")
    promote.add_argument("--unit-tests-passed", action="store_true")

    status = improve_sub.add_parser("status", help="show improvement run status")
    status.add_argument("--run", default="latest")


def dispatch(args: argparse.Namespace) -> int:
    command = args.improve_command
    if command == "init":
        return _init(args)
    if command == "lint-skill":
        return _lint_skill(args)
    if command == "build-skill":
        return _build_skill(args)
    if command == "make-suite":
        return _make_suite(args)
    if command == "begin-run":
        return _begin_run(args)
    if command == "record-attempt":
        return _record_attempt(args)
    if command == "evaluate":
        return _evaluate(args)
    if command == "diagnose":
        return _diagnose(args)
    if command == "next-prompt":
        return _next_prompt(args)
    if command == "promote":
        return _promote(args)
    if command == "status":
        return _status(args)
    raise ValueError(f"unknown improve command: {command}")


def _init(args: argparse.Namespace) -> int:
    ensure_improvement_dirs()
    written: list[Path] = []
    for skill_dir in (AUTHOR_SKILL_DIR, IMPROVER_SKILL_DIR):
        skill_dir.mkdir(parents=True, exist_ok=True)

    author_skill = AUTHOR_SKILL_DIR / "SKILL.md"
    if not author_skill.exists():
        version = build_skill_package(SkillBuildConfig(output_dir=AUTHOR_SKILL_DIR))
        _ = version
        written.append(author_skill)
    written.extend(_ensure_improver_skill_files(no_overwrite=args.no_overwrite))

    if not (AUTHOR_SKILL_DIR / "skill-version.json").exists() and not args.no_overwrite:
        version = SkillVersion(
            id=_current_skill_version_id(),
            created_at=utc_now(),
            git_commit=git_commit(),
            skill_path=relative_to_project(author_skill),
            skill_sha256=skill_hash(author_skill),
            builder_version=BUILDER_VERSION,
            source_manifests=[],
            notes="Initialized from existing skill files",
        )
        write_json(version, AUTHOR_SKILL_DIR / "skill-version.json")
        written.append(AUTHOR_SKILL_DIR / "skill-version.json")
    starter_suite = SUITES_ROOT / "core.jsonl"
    if not starter_suite.exists():
        write_eval_cases(hand_authored_core_cases(), starter_suite)
        written.append(starter_suite)
    index = IMPROVEMENT_ROOT / "index.json"
    if not index.exists() or not args.no_overwrite:
        index.parent.mkdir(parents=True, exist_ok=True)
        index.write_text(json.dumps({"latest_run_id": ""}, indent=2) + "\n", encoding="utf-8")
        written.append(index)
    for path in written:
        print(path)
    if not written:
        print("Improvement system already initialized.")
    return 0


def _lint_skill(args: argparse.Namespace) -> int:
    paths = [Path(path) for path in args.path] if args.path else [AUTHOR_SKILL_DIR, IMPROVER_SKILL_DIR]
    errors: list[str] = []
    for path in paths:
        required = REQUIRED_AUTHOR_REFERENCES if path.name == "plantuml-diagram-author" else REQUIRED_IMPROVER_REFERENCES
        package_errors = lint_skill_package(path, required)
        for error in package_errors:
            errors.append(f"{path}: {error}")
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Skill packages passed lint.")
    return 0


def _build_skill(args: argparse.Namespace) -> int:
    config = SkillBuildConfig(
        output_dir=Path(args.output),
        manifest_paths=[Path(path) for path in args.manifest],
        lessons_path=Path(args.lessons) if args.lessons else None,
        max_examples=args.max_examples,
    )
    version = build_skill_package(config)
    print(f"Built skill {version.id}: {version.skill_path}")
    return 0


def _make_suite(args: argparse.Namespace) -> int:
    if args.manifest:
        cases = make_eval_suite_from_manifest_paths([Path(path) for path in args.manifest], args.max_cases)
    else:
        cases = hand_authored_core_cases()
        if args.max_cases > 0:
            cases = cases[: args.max_cases]
    path = write_eval_cases(cases, args.output)
    print(f"Wrote {len(cases)} eval cases to {path}")
    return 0


def _begin_run(args: argparse.Namespace) -> int:
    ensure_improvement_dirs()
    run_id = args.run_id or _default_run_id()
    run_dir = RUNS_ROOT / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    suite_src = _project_path(args.suite)
    suite_dest = run_dir / "eval_cases.jsonl"
    shutil.copyfile(suite_src, suite_dest)
    attempts_path = run_dir / "attempts.jsonl"
    results_path = run_dir / "results.jsonl"
    report_path = run_dir / "evaluation-report.md"
    handoff_path = run_dir / "codex-next-prompt.md"
    candidate_id = args.candidate_skill_version_id or _current_skill_version_id()
    run = ImprovementRun(
        id=run_id,
        created_at=utc_now(),
        status="initialized",
        baseline_skill_version_id=args.baseline_skill_version_id,
        candidate_skill_version_id=candidate_id,
        suite_path=relative_to_project(suite_dest),
        attempts_path=relative_to_project(attempts_path),
        results_path=relative_to_project(results_path),
        report_path=relative_to_project(report_path),
        next_handoff_path=relative_to_project(handoff_path),
        metrics={},
    )
    save_run(run)
    write_attempts([], attempts_path)
    write_jsonl([], results_path)
    write_codex_generation_prompt(run)
    update_latest_run(run_id)
    print(f"Created improvement run: {run_id}")
    print(f"Run directory: {run_dir}")
    return 0


def _record_attempt(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    attempts_path = _project_path(run.attempts_path)
    attempts = load_attempts(attempts_path)
    attempts_dir = attempts_path.parent / "attempts"
    if args.response_file:
        if not args.case:
            raise ValueError("--case is required with --response-file")
        attempts = record_attempt_file(
            attempts,
            attempts_dir,
            run.id,
            run.candidate_skill_version_id,
            args.case,
            Path(args.response_file),
            model_or_agent=args.model_or_agent,
        )
    elif args.responses_dir:
        for response_file in sorted(Path(args.responses_dir).iterdir()):
            if response_file.suffix.lower() not in {".md", ".puml", ".plantuml", ".txt"}:
                continue
            attempts = record_attempt_file(
                attempts,
                attempts_dir,
                run.id,
                run.candidate_skill_version_id,
                response_file.stem,
                response_file,
                model_or_agent=args.model_or_agent,
            )
    else:
        raise ValueError("pass --response-file or --responses-dir")
    write_attempts(sorted(attempts, key=lambda item: item.case_id), attempts_path)
    print(f"Wrote {len(attempts)} attempts to {attempts_path}")
    return 0


def _evaluate(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    cases = load_eval_cases(_project_path(run.suite_path))
    attempts = load_attempts(_project_path(run.attempts_path))
    render_dir = Path(args.render_dir) if args.render_dir else _project_path(run.results_path).parent / "rendered"
    include_roots = _include_roots(args.include_root)
    renderer = (
        None
        if args.no_render
        else PlantUMLRenderer(jar_path=args.jar, java_bin=args.java or None, include_roots=include_roots)
    )
    results = evaluate_attempts(
        cases,
        attempts,
        renderer,
        render_dir=render_dir,
        include_roots=include_roots,
        allow_missing_attempts=args.allow_missing_attempts,
    )
    write_jsonl(results, _project_path(run.results_path))
    write_evaluation_report(results, _project_path(run.report_path), title=f"PlantUML Skill Evaluation Report: {run.id}")
    run.metrics = metrics_from_results(results)
    run.status = "evaluated"
    save_run(run)
    print(f"Evaluated {len(results)} cases; average_score={run.metrics.get('average_score', 0.0)}")
    if args.allow_missing_attempts:
        return 0
    return 0 if all(result.score >= 0.9 and not result.failures for result in results) else 1


def _diagnose(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    results = read_jsonl(_project_path(run.results_path), SkillEvaluationResult)
    clusters = cluster_failures(results)
    run_dir = _project_path(run.results_path).parent
    write_failure_report(clusters, run_dir / "failure-clusters.json")
    write_failure_report(clusters, run_dir / "failure-clusters.md")
    write_lessons(lessons_from_failures(clusters), run_dir / "lessons.json")
    run.status = "diagnosed"
    save_run(run)
    print(f"Wrote {len(clusters)} failure clusters to {run_dir}")
    return 0


def _next_prompt(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    results_path = _project_path(run.results_path)
    clusters = []
    if results_path.exists():
        clusters = cluster_failures(read_jsonl(results_path, SkillEvaluationResult))
    path = write_codex_next_prompt(run, clusters)
    run.next_handoff_path = relative_to_project(path)
    save_run(run)
    print(f"Wrote Codex handoff prompt: {path}")
    return 0


def _promote(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    baseline = {}
    if args.baseline_metrics:
        baseline = json.loads(_project_path(args.baseline_metrics).read_text(encoding="utf-8"))
    decision = promotion_decision(
        run,
        baseline_metrics=baseline,
        unit_tests_passed=args.unit_tests_passed,
        human_approval_recorded=has_human_approval(run.id),
    )
    path = _project_path(run.results_path).parent / "promotion-decision.json"
    write_json(decision, path)
    print(json.dumps(decision.to_mapping(), indent=2, sort_keys=True))
    return 0 if decision.promote else 1


def _status(args: argparse.Namespace) -> int:
    run = load_run(args.run)
    print(json.dumps(run.to_mapping(), indent=2, sort_keys=True))
    return 0


def _default_run_id() -> str:
    return "run-" + utc_now().replace(":", "").replace("-", "").replace("Z", "")


def _current_skill_version_id() -> str:
    version_path = AUTHOR_SKILL_DIR / "skill-version.json"
    if version_path.exists():
        try:
            data = json.loads(version_path.read_text(encoding="utf-8"))
            return str(data.get("id") or "")
        except json.JSONDecodeError:
            pass
    skill_md = AUTHOR_SKILL_DIR / "SKILL.md"
    if skill_md.exists():
        return f"skill-{skill_hash(skill_md)[:12]}"
    return f"skill-{git_commit()}"


def _project_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return STATE_PROJECT_ROOT / path


def _include_roots(extra_roots: list[str]) -> list[Path]:
    config = load_sources_config()
    configured = config.renderer.get("include_roots", [])
    return [_project_path(path) for path in [*configured, *extra_roots]]


def _ensure_improver_skill_files(no_overwrite: bool) -> list[Path]:
    files = {
        IMPROVER_SKILL_DIR / "SKILL.md": """---
name: plantuml-skill-improver
description: Continue the human-triggered PlantUML skill improvement loop. Use when asked to inspect latest eval runs, diagnose failures, update skill or harness files, run tests, and write the next Codex handoff.
---

# PlantUML Skill Improver

Read the latest handoff, inspect evaluation failures, modify only allowed files, run required tests, and write the next handoff. Never promote without passing gates and human approval.
""",
        IMPROVER_SKILL_DIR / "references" / "improvement-loop-protocol.md": (
            "# Improvement Loop Protocol\n\n"
            "Codex proposes changes, the evaluator measures them, and the human approves promotion.\n"
        ),
        IMPROVER_SKILL_DIR / "references" / "scoring-rubric.md": (
            "# Scoring Rubric\n\n"
            "Use deterministic extractability, syntax, family, include, render, semantic, and output-contract checks.\n"
        ),
        IMPROVER_SKILL_DIR / "references" / "codex-handoff-template.md": (
            "# Codex Handoff Template\n\n"
            "Include goal, metrics, clusters, allowed edits, required commands, and definition of done.\n"
        ),
        IMPROVER_SKILL_DIR / "scripts" / "continue_loop.py": (
            "#!/usr/bin/env python3\nprint('Run plantuml-skill improve status --run latest')\n"
        ),
    }
    written: list[Path] = []
    for path, text in files.items():
        if path.exists():
            continue
        if no_overwrite and path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
