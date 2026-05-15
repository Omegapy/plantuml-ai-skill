# PlantUML Diagram Skill `skill-b63b348d98c6`

Release date: 2026-05-15

Legacy naming note: this release evidence was originally prepared with the `plantuml-diagram-author` slug. The current canonical skill slug and archive root are `plantuml-diagram`.

## Artifacts

### Installer Packet

Use this archive when installing the skill into another project or into the global Codex skills directory.

```text
plantuml-diagram-installer-b63b348d98c6.tar.gz
```

Local build location:

```text
/private/tmp/plantuml-diagram-installer-b63b348d98c6-v2/
```

SHA-256:

```text
8f0949fd75afa1d62123a6df912b065bfeb6f00d9d5b57f7d9c0f23927e1c890
```

The installer packet contains:

- `README.md`
- `install.sh`
- `plantuml-diagram/`

Install into one project:

```bash
./install.sh --repo /path/to/project
```

Install globally for Codex:

```bash
./install.sh --global
```

### Skill-Only Archive

```text
plantuml-diagram-skill-b63b348d98c6.tar.gz
```

Local build location:

```text
/private/tmp/plantuml-skill-release-b63b348d98c6/
```

SHA-256:

```text
986120a3a9d81801a355f92fb4f28e4afe8a9621991207593edf3394c38c0de0
```

The archive is rooted at `plantuml-diagram/` and contains only the promoted skill package.

## Package Contents

- `plantuml-diagram/SKILL.md`
- `plantuml-diagram/references/diagram-family-playbook.md`
- `plantuml-diagram/references/examples.md`
- `plantuml-diagram/references/include-policy.md`
- `plantuml-diagram/references/large-diagram-patterns.md`
- `plantuml-diagram/references/output-contract.md`
- `plantuml-diagram/scripts/validate_plantuml_attempt.py`

The validation helper is executable and portable. When the full `plantuml_ai_skill` evaluator is available, it uses it. Otherwise, it falls back to built-in PlantUML shape, required-pattern, forbidden-pattern, and diagram-family checks.

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

The archives and checksums are not committed to the repository. Attach them to a GitHub release or external release store if publication is required.

Suggested tag:

```text
plantuml-diagram-installer-b63b348d98c6
```
