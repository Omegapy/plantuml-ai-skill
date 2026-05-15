# PlantUML AI Skill

An AI skill project for generating, validating, rendering, and verifying PlantUML diagrams and PlantUML training-data corpora.

## Goal

This project provides a Python-based workflow that helps agents turn plain-language diagram requests into inspectable PlantUML source, validate that source, render diagrams for review, and assemble verified training/evaluation corpora from public PlantUML sources.

## For Users: Download a Package

If you only want to install the PlantUML Diagram skill into your own Codex project on macOS, Linux, or Windows 11, use the GitHub release packages instead of this developer setup.

- Download one package from the [v0.1.0 release](https://github.com/Omegapy/plantuml-ai-skill/releases/tag/v0.1.0).
- Read the beginner guide: [PlantUML Diagram Package Installation Guide](docs/releases/plantuml-diagram-package-installation.md).
- The package unzips into its own installer folder. On macOS or Linux, `install.sh` copies the files into your project's hidden `.agents/` folder. On Windows 11, `install.ps1` or `install.cmd` does the same.
- These packages are for Codex and the Codex app, not Claude Code.
- These packages are for creating, checking, and rendering PlantUML diagrams. They are not for training, fine-tuning, or improving the skill.

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

For a real permissive Git-source smoke run:

```bash
plantuml-skill acquire --source plantuml-examples-mattjhayes --output data/manifests/plantuml-examples.jsonl
plantuml-skill render --manifest data/manifests/plantuml-examples.jsonl --output data/manifests/plantuml-examples-rendered.jsonl --render-dir data/rendered/plantuml-examples
plantuml-skill verify --manifest data/manifests/plantuml-examples-rendered.jsonl --output data/manifests/plantuml-examples-verified.jsonl
plantuml-skill report --manifest data/manifests/plantuml-examples-rendered.jsonl --output data/reports/plantuml-examples-report.md
```

The real-source verifier may report renderer failures, remote include skips, or PNG mismatches. Those are useful corpus diagnostics rather than repository test failures.

For Python-source-conditioned examples:

```bash
plantuml-skill acquire --source py2puml --output data/manifests/py2puml.jsonl
plantuml-skill render --manifest data/manifests/py2puml.jsonl --output data/manifests/py2puml-rendered.jsonl --render-dir data/rendered/py2puml
plantuml-skill verify --manifest data/manifests/py2puml-rendered.jsonl --output data/manifests/py2puml-verified.jsonl
```

## Data Policy

Tracked files include code, schemas, configuration, documentation, and small fixtures. Generated or downloaded artifacts are ignored:

- `data/raw/`
- `data/rendered/`
- `data/manifests/`
- `data/reports/`
- `data/vendor/`
- `tools/plantuml/`
- `.cache/`

The durable interchange format is JSONL manifests. Each record keeps row-level source provenance, license family, include dependencies, renderer versions, render hashes, verification status, and split purpose.

## Tests

Run the current test suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The unit tests cover source-registry recommendation coverage, manifest shape, extraction, include parsing, license filtering, split construction, SVG normalization, PNG fallback hashing, CLI behavior, and the Java renderer command contract.
