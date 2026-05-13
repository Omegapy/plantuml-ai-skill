# AGENTS.md

## Project Purpose

This repo builds and improves a Codex skill for generating, validating, rendering, and evaluating PlantUML diagrams.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
plantuml-skill init-assets
plantuml-skill doctor
```

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Required Smoke Workflow

```bash
plantuml-skill coverage
plantuml-skill acquire --source fixtures --output data/manifests/fixtures.jsonl
plantuml-skill render --manifest data/manifests/fixtures.jsonl --output data/manifests/rendered.jsonl
plantuml-skill verify --manifest data/manifests/rendered.jsonl --output data/manifests/verified.jsonl
plantuml-skill build-splits --manifest data/manifests/verified.jsonl
plantuml-skill report --manifest data/manifests/verified.jsonl
```

## Improvement Loop

```bash
plantuml-skill improve init
plantuml-skill improve make-suite --output data/improvement/suites/core.jsonl --max-cases 20
plantuml-skill improve begin-run --suite data/improvement/suites/core.jsonl
plantuml-skill improve evaluate --run latest
plantuml-skill improve diagnose --run latest
plantuml-skill improve next-prompt --run latest
```

## Rules

- Keep generated artifacts under ignored `data/` paths.
- Do not commit downloaded corpora, rendered bulk outputs, caches, or local jars.
- Prefer deterministic evaluation before model judging.
- Reuse the existing extraction, include parsing, renderer, verification, and manifest code.
- Never promote a skill candidate without passing gates and recording human approval.
