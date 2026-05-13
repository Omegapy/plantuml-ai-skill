# PlantUML Skill Improvement System

This repository includes a human-in-the-loop improvement harness for a repo-scoped Codex skill.

The invariant is:

```text
Codex may propose changes.
The evaluator measures changes.
The human approves continuation and promotion.
The repository preserves state.
```

## Components

- `.agents/skills/plantuml-diagram-author/` teaches Codex to generate inspectable PlantUML.
- `.agents/skills/plantuml-skill-improver/` teaches Codex to resume an improvement run from durable files.
- `src/plantuml_ai_skill/improvement/` stores models, suite generation, attempt recording, evaluation, diagnostics, handoff generation, and promotion gates.
- `schemas/skill-*.schema.json` documents the persisted JSON contracts.
- `data/improvement/runs/` holds generated run state and is ignored by git.

## Typical Flow

```bash
plantuml-skill improve init
plantuml-skill improve make-suite --output data/improvement/suites/core.jsonl --max-cases 20
plantuml-skill improve begin-run --suite data/improvement/suites/core.jsonl --run-id mvp-001
plantuml-skill improve next-prompt --run mvp-001
```

After Codex attempts are collected:

```bash
plantuml-skill improve record-attempt --run mvp-001 --responses-dir data/improvement/runs/mvp-001/codex_responses
plantuml-skill improve evaluate --run mvp-001
plantuml-skill improve diagnose --run mvp-001
plantuml-skill improve next-prompt --run mvp-001
```

## Evaluation

The default evaluator is deterministic and offline. It checks extractability, start/end syntax, diagram family, include policy, renderability through the pinned PlantUML renderer, semantic patterns and edges, and output-contract violations.

Model judging can be added later, but it should remain opt-in.

## Promotion

`plantuml-skill improve promote` reports gate status. It blocks promotion when tests are not recorded as passed, human approval is missing, remote include violations exist, render rate regresses, semantic metrics fail the configured gate, or protected regressions are recorded.
