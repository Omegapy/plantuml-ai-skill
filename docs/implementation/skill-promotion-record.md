# PlantUML Skill Promotion Record

This document records durable promotion outcomes for the repo-scoped PlantUML Codex skill. Detailed generated run artifacts remain under ignored `data/improvement/` paths.

## 2026-05-13: `promotion-readiness`

Role: promotion execution steward and release/audit coordinator.

Outcome: approved and promotion gate passed.

The `promotion-readiness` run validated the current committed skill and evaluator state after two evidence-driven improvement loops. The human explicitly approved promotion, an approval record was created under `data/improvement/approvals/promotion-readiness.json`, and the promotion gate returned:

```json
{
  "promote": true,
  "reasons": [],
  "run_id": "promotion-readiness"
}
```

Promotion metrics:

| Run | Cases | Passed | Average Score | Render OK Rate | Semantic Pass Rate | Remote Include Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `first-real-loop` | 12 | 11 | 0.9792 | 0.9167 | 1.0 | 0 |
| `c4-guidance-followup` | 12 | 12 | 1.0 | 1.0 | 1.0 | 0 |
| `promotion-readiness` | 15 | 15 | 1.0 | 1.0 | 1.0 | 0 |

Validation context:

- The broader local suite was built from `data/manifests/plantuml-examples-verified.jsonl`, which had 73 verified records available locally.
- The current suite builder samples one manifest record per diagram family and prepends the hand-authored core cases, so `--max-cases 40` produced 15 cases.
- The promotion-readiness suite covered core/recent regression cases plus manifest-driven activity, sequence, C4, class, use case, gantt, mindmap, and component cases.
- No network acquisition was used.
- No failure clusters were recorded.

Operational note:

`plantuml-skill improve promote` is a gate reporter. It does not publish, install, tag, or copy the skill. For this repo, the approved candidate is the repo-scoped skill under `.agents/skills/plantuml-diagram-author/`; no additional mechanical promotion step was required.

Environment note:

Use Python 3.12 or newer for validation commands. The system Python 3.9.6 fails on `datetime.UTC`; the validated command path was:

```bash
PYTHONPATH=src /opt/homebrew/opt/python@3.12/libexec/bin/python3 -m plantuml_ai_skill.cli ...
```

## 2026-05-14/15: `large-pilot-training`

Role: large-full evidence consolidation and release/readiness triage.

Outcome: approved, promotion gate passed, and large-full synthetic scale validation passed the stability gate.

The `large-pilot-training` run validated the updated `plantuml-diagram-author` skill after large synthetic evidence had been folded into the skill package. This was skill-package training, not model fine-tuning. The human approval record was written at `2026-05-15T01:05:53Z` under `data/improvement/approvals/large-pilot-training.json`, and the promotion gate returned:

```json
{
  "promote": true,
  "reasons": [],
  "run_id": "large-pilot-training"
}
```

Promotion metrics:

| Run | Cases | Passed | Average Score | Render OK Rate | Semantic Pass Rate | Remote Include Violations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `large-pilot-training` | 9 | 9 | 1.0 | 1.0 | 1.0 | 0 |

Scale-validation context:

- Large-full synthetic validation processed 59,924 input rows, rendered 59,924 rows, and verified 59,924 rows.
- Rendering completed with 59,924 `ok`, 0 failed, and 0 skipped.
- Verification completed with 29,298 `png_match`, 30,626 `png_mismatch`, and 0 verification errors.
- The `verify` command's nonzero exit from PNG mismatches was expected; the accepted stability gate is `verify_error == 0`.
- Large-full split generation selected 5,000 augmentation rows and 0 train/gold-eval rows.

Readiness decision:

The repo-scoped skill is package-ready at the current promotion level. The large-full mismatch population is diagnostic evidence about renderer/version/layout drift, not a blocker for release. The next improvement loop should only start if the project chooses to improve diagram fidelity or curation from selected mismatch families, especially activity `group` warning banners and high-distance sequence layout drift. Otherwise, avoid more generated-data churn and package the promoted skill as-is.
