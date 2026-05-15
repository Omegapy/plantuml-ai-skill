# Schemas

This folder documents persisted JSON contracts used by the PlantUML skill
pipeline and improvement harness.

## Contracts

- `corpus-record.schema.json`: JSONL manifest rows produced by acquisition,
  rendering, verification, and split-building commands.
- `skill-*.schema.json`: skill improvement cases, attempts, versions, and
  evaluation results.
- `improvement-run.schema.json`: durable state for human-in-the-loop
  improvement runs.

When changing a schema, update the corresponding Python model, CLI writer or
reader, and tests in the same change.
