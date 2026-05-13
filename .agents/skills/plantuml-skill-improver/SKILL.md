---
name: plantuml-skill-improver
description: Continue the human-triggered PlantUML skill improvement loop. Use when asked to inspect latest eval runs, diagnose failures, update skill or harness files, run tests, and write the next Codex handoff.
---

# PlantUML Skill Improver

## Goal

Improve the repo-scoped `plantuml-diagram-author` skill using deterministic evaluation evidence. The loop is human-triggered: Codex proposes changes, the evaluator measures them, and a human approves promotion.

## Resume Workflow

1. Read the user's handoff file, usually `data/improvement/runs/<run-id>/codex-next-prompt.md`.
2. Inspect `run.json`, `evaluation-report.md`, `failure-clusters.json`, and the current skill files.
3. Modify only files allowed by the handoff.
4. Prefer concise skill guidance, reference files, and deterministic scripts over broad rewrites.
5. Run the required tests from the handoff.
6. Run `plantuml-skill improve evaluate`, `diagnose`, and `next-prompt` when attempts are available.
7. Do not promote a candidate unless promotion gates pass and a human approval file exists.

Read `references/improvement-loop-protocol.md` before substantial changes, `references/scoring-rubric.md` when interpreting metrics, and `references/codex-handoff-template.md` when regenerating handoffs.

## Edit Discipline

- Keep generated run artifacts under `data/improvement/runs/`.
- Keep skill guidance short enough to load easily.
- Do not expose hidden acceptance cases in generated prompts.
- Do not edit unrelated corpus, renderer, or acquisition code unless tests prove it is required.
- Final responses must list changed files, tests run, and remaining risks.
