# PlantUML Diagram Author Skill `skill-b63b348d98c6`

Release date: 2026-05-15

## Artifact

```text
plantuml-diagram-author-skill-b63b348d98c6.tar.gz
```

Local build location:

```text
/private/tmp/plantuml-skill-release-b63b348d98c6/
```

SHA-256:

```text
a389c174395385a0cdb78be0e4e0f84c303c547fc16872c49dc41fac7446299b
```

The archive is rooted at `plantuml-diagram-author/` and contains only the promoted skill package.

## Package Contents

- `plantuml-diagram-author/SKILL.md`
- `plantuml-diagram-author/references/diagram-family-playbook.md`
- `plantuml-diagram-author/references/examples.md`
- `plantuml-diagram-author/references/include-policy.md`
- `plantuml-diagram-author/references/large-diagram-patterns.md`
- `plantuml-diagram-author/references/output-contract.md`
- `plantuml-diagram-author/scripts/validate_plantuml_attempt.py`

## Promotion Evidence

```text
run_id: large-pilot-training
candidate_skill_version_id: skill-b63b348d98c6
approved_by: human
approved_at: 2026-05-15T01:05:53Z
promote: true
cases: 9
passed: 9
average_score: 1.0
render_ok_rate: 1.0
semantic_pass_rate: 1.0
remote_include_violations: 0
```

## Scale Evidence

Large-full synthetic validation passed the stability gate:

```text
input rows: 59,924
rendered rows: 59,924
verified rows: 59,924
render ok: 59,924
verify errors: 0
png_match: 29,298
png_mismatch: 30,626
```

PNG mismatches are diagnostic renderer/version/layout drift evidence, not a release blocker. Synthetic records remain augmentation-only.

## Verification

Release verification commands:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill improve lint-skill
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m unittest discover -s tests -v
```

Both passed for this release artifact.

## Publication Notes

The archive and checksum are not committed to the repository. Attach them to a GitHub release or external release store if publication is required.

Suggested tag:

```text
plantuml-diagram-author-skill-b63b348d98c6
```
