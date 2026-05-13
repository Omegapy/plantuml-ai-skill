# Improvement Loop Protocol

The loop is:

1. Build or update a candidate skill.
2. Generate or collect Codex attempts for eval cases.
3. Evaluate attempts deterministically.
4. Cluster failures.
5. Convert repeated failures into skill lessons or harness fixes.
6. Write the next handoff prompt.
7. Wait for human review and continuation.

Codex may propose edits, but the repository evaluator and the human decide what counts as improvement.

Never promote automatically. Promotion needs passing gates and an approval file under `data/improvement/approvals/`.
