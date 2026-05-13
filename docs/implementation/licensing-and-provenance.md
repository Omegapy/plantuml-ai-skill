# Licensing And Provenance

The training-data report calls out licensing clarity as a primary risk. The implementation treats licensing as row-level metadata rather than a dataset-level afterthought.

## Row-Level Provenance

Every manifest record stores:

- `source_name`
- `source_url`
- `source_kind`
- `source_ref`
- `license`
- `license_family`
- `puml_path`
- `published_render_path`
- `include_deps`
- `attribution`
- `license_path`
- `source_commit`
- `source_repo_url`

This keeps mixed sources such as Repo-PlantUML-Dataset auditable after extraction, rendering, and split construction.

For Git sources, acquisition records the checked-out commit and the first detected root license/notice file. Mixed-license datasets still require row-level license staging before any broad training use.

## License Families

`plantuml_ai_skill.license_policy` classifies license strings into:

- `permissive`
- `weak_copyleft`
- `copyleft`
- `mixed`
- `unknown`

Only `permissive` records may enter the broad `training` split by default. Sources with unclear terms, docs reuse questions, icon asset constraints, or retained original licenses remain in evaluation or manual-review workflows until their terms are verified.

## Source-Specific Defaults

The source registry encodes the report's recommendations:

- Official docs are treated as gold evaluation and syntax tests until documentation reuse terms are verified.
- Repo-PlantUML-Dataset is marked mixed-license and requires row-level filtering.
- C4-PlantUML, py2puml, PlantUML-Examples, and coni2k reference examples are treated as permissive when their registry license policy declares MIT or Apache-2.0.
- plantuml-stdlib and AWS Icons for PlantUML are treated conservatively until clone-time license and asset terms are reviewed.
- Synthetic UML data is augmentation-only until dataset license terms are verified.

## Generated Artifacts

Downloaded corpora, cloned repositories, rendered diagrams, generated manifests, reports, caches, and the PlantUML jar live in ignored directories. This prevents accidental redistribution of mixed-license or unclear-license material.

Tracked files contain only source code, schemas, docs, and small project-owned fixtures.
