# Local Data Workspace

This directory is the local workspace for generated manifests, downloaded
corpora, rendered diagrams, reports, vendored include snapshots, and
improvement-run state.

Most subdirectories under `data/` are intentionally ignored by Git. They may be
large or expensive to regenerate and should not be committed unless a future
task explicitly promotes a small, reviewed artifact into tracked documentation.

## Common Subdirectories

- `raw/`: downloaded or manually staged source corpora.
- `rendered/`: renderer outputs produced by `plantuml-skill render`.
- `manifests/`: JSONL records produced by acquisition, rendering, and
  verification commands.
- `reports/`: generated curator-facing reports and review assets.
- `vendor/`: pinned local include snapshots used to avoid remote includes.
- `improvement/`: generated suites, runs, approvals, and improvement state.

Tracked project policy and durable evidence belong in `docs/`, `config/`, and
`schemas/`, not in generated `data/` outputs.
