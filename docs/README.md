# Documentation Map

This directory contains durable project documentation. It is intentionally
separate from generated manifests, rendered diagrams, and local acquisition
outputs under `data/`.

## Subdirectories

- `implementation/`: design notes, validation evidence, promotion records, and
  pipeline documentation for maintainers.
- `releases/`: user-facing package installation docs and historical release
  evidence.
- `Reviews/`: historical research-review material that informed the training
  data pipeline. The capitalized path is retained for compatibility with
  existing references.

## Canonical Release Docs

Use `releases/plantuml-diagram-package-installation.md` for the current
cross-platform package installation guide. It covers macOS/Linux `.tar.gz`
packages, Windows `-windows.zip` packages, and the shared `SHA256SUMS` file.
