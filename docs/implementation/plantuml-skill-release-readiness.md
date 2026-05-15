# PlantUML Skill Release Readiness

Date: 2026-05-15

## Decision

The repo-scoped `plantuml-diagram-author` skill is ready to package from the current tracked state.

This is a skill-package release decision, not model fine-tuning. The durable release surface is the skill directory under `.agents/skills/plantuml-diagram-author/`; generated manifests, rendered images, verification reports, and improvement-run artifacts under `data/` remain local evidence and are intentionally ignored by Git.

## Release Role

Recommended next-instance role: **PlantUML Skill Release Packaging Steward**.

The steward's job is to preserve the promoted skill package, verify it, and publish or tag it only when the project explicitly asks for that mechanical release step. The steward should avoid starting another broad synthetic-data validation run unless there is a specific curation question.

## Package Surface

Package these tracked files as the skill:

- `.agents/skills/plantuml-diagram-author/SKILL.md`
- `.agents/skills/plantuml-diagram-author/references/diagram-family-playbook.md`
- `.agents/skills/plantuml-diagram-author/references/examples.md`
- `.agents/skills/plantuml-diagram-author/references/include-policy.md`
- `.agents/skills/plantuml-diagram-author/references/large-diagram-patterns.md`
- `.agents/skills/plantuml-diagram-author/references/output-contract.md`
- `.agents/skills/plantuml-diagram-author/scripts/validate_plantuml_attempt.py`

Do not package generated `data/` artifacts unless a separate archival/reproducibility task explicitly asks for them.

## Promotion Evidence

Promotion run:

```text
run_id: large-pilot-training
candidate_skill_version_id: skill-b63b348d98c6
approved_by: human
approved_at: 2026-05-15T01:05:53Z
promote: true
reasons: []
```

Promotion metrics:

| Metric | Value |
| --- | ---: |
| Cases | 9 |
| Passed | 9 |
| Average score | 1.0 |
| Render OK rate | 1.0 |
| Semantic pass rate | 1.0 |
| Remote include violations | 0 |

Durable promotion record:

- `docs/implementation/skill-promotion-record.md`

## Scale Evidence

Large-full synthetic validation completed successfully as a pipeline stability gate:

| Measure | Value |
| --- | ---: |
| Input rows | 59,924 |
| Rendered rows | 59,924 |
| Verified rows | 59,924 |
| Render OK | 59,924 |
| Render failed | 0 |
| Render skipped | 0 |
| Verify errors | 0 |
| PNG match | 29,298 |
| PNG mismatch | 30,626 |
| Remote include violations | 0 |

The acceptance criterion was `verify_error == 0`. The nonzero verifier exit caused by PNG mismatches is expected for this dataset and is not a release blocker.

Durable scale-validation record:

- `docs/implementation/synthetic-dataset-scale-validation.md`

## Known Limits

- Synthetic rows remain augmentation-only because the license family is `unknown`, the source is synthetic, and the published PNG references show renderer/version/layout drift.
- PNG mismatch counts are diagnostic. They should not be reduced by loosening verifier semantics.
- The dominant activity mismatch family is legacy `group` syntax that causes warning banners under the pinned PlantUML 1.2026.3 renderer.
- High-distance sequence mismatches need manual curation before they become skill lessons; they are not proof of bad source/render pairing by themselves.
- The release does not install, tag, upload, or copy the skill. Those are separate mechanical steps.

## Verification Commands

Use Python 3.12 or newer:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill improve lint-skill
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m unittest discover -s tests -v
```

If the test suite is run inside a restricted sandbox, the parallel verifier tests may fail with `Operation not permitted` when worker processes are blocked. Rerun outside the sandbox before treating that as a repo regression.

## Release Recommendation

Default path:

```text
Package or tag the current promoted skill as-is.
```

Only start a new improvement loop if the project chooses targeted fidelity/curation work. If so, the loop should be small and mismatch-derived, focused on activity `group` warning patterns and high-distance sequence layout drift. Do not run another broad full-scale synthetic pass first.
