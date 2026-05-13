# Codex Human Loop

The improvement loop is resumable across Codex conversations because state lives in files, not chat memory.

## Human Role

The human schedules each iteration, reviews diffs, decides whether to continue, and records approval before promotion. Codex can generate attempts and propose skill or harness changes, but it does not decide promotion alone.

## Starting A New Thread

Generate or refresh the handoff:

```bash
plantuml-skill improve next-prompt --run latest
```

Then start a new Codex thread with:

```text
Use the plantuml-skill-improver skill.

Continue the PlantUML skill improvement loop using the latest codex-next-prompt.md.
Follow the handoff exactly.
```

## Durable Run Files

Each run directory contains:

- `run.json`
- `eval_cases.jsonl`
- `attempts.jsonl`
- `results.jsonl`
- `evaluation-report.md`
- `failure-clusters.json`
- `lessons.json`
- `codex-next-prompt.md`

These files let a fresh Codex thread reconstruct what happened and what remains to be improved.
