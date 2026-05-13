# PlantUML AI Skill

An AI skill project for generating, validating, rendering, and verifying PlantUML diagrams and PlantUML training-data corpora.

## Goal

This project provides a Python-based workflow that helps agents turn plain-language diagram requests into inspectable PlantUML source, validate that source, render diagrams for review, and assemble verified training/evaluation corpora from public PlantUML sources.

## Python Setup

Create and activate the repo-local virtual environment with Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

The `.venv/` directory is ignored by Git and should not be committed.

If an older `.venv` already exists, remove and recreate it so `python --version` reports Python 3.11 or newer.

## Runtime Requirements

PlantUML rendering uses the official Java jar as the primary renderer.

- Java 11 or newer is required to run `plantuml-1.2026.3.jar`.
- Graphviz `dot` is required for PlantUML diagram families that use Graphviz layout.
- The pinned PlantUML jar is downloaded into ignored local tooling with `plantuml-skill init-assets`.

On macOS with Homebrew, Java can be installed with:

```bash
brew install openjdk
```

The tooling automatically detects Homebrew's keg-only OpenJDK path at `/opt/homebrew/opt/openjdk/bin/java`. You can override that with `PLANTUML_JAVA` or CLI `--java`.

After Java is available, initialize assets and verify the renderer stack:

```bash
plantuml-skill init-assets
plantuml-skill doctor
```

`doctor` checks Java, Graphviz, the pinned jar checksum, and `java -jar plantuml.jar -testdot`.

## CLI Workflow

The package exposes `plantuml-skill`:

```bash
plantuml-skill coverage
plantuml-skill acquire --source fixtures --output data/manifests/fixtures.jsonl
plantuml-skill render --manifest data/manifests/fixtures.jsonl --output data/manifests/rendered.jsonl
plantuml-skill verify --manifest data/manifests/rendered.jsonl --output data/manifests/verified.jsonl
plantuml-skill audit-licenses --manifest data/manifests/verified.jsonl
plantuml-skill build-splits --manifest data/manifests/verified.jsonl
plantuml-skill report --manifest data/manifests/verified.jsonl
```

External corpus acquisition is deliberately conservative. Git sources can be cloned from `config/sources.yml`; dataset sources that retain mixed original licenses must be manually staged after license review.

## Data Policy

Tracked files include code, schemas, configuration, documentation, and small fixtures. Generated or downloaded artifacts are ignored:

- `data/raw/`
- `data/rendered/`
- `data/manifests/`
- `data/reports/`
- `tools/plantuml/`
- `.cache/`

The durable interchange format is JSONL manifests. Each record keeps row-level source provenance, license family, include dependencies, renderer versions, render hashes, verification status, and split purpose.

## Tests

Run the current test suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The unit tests cover source-registry recommendation coverage, manifest shape, extraction, include parsing, license filtering, split construction, SVG normalization, PNG fallback hashing, CLI behavior, and the Java renderer command contract.
