# Training Data Pipeline

This project implements the recommendations from `docs/Reviews/PlantUML Training Data Report.md` as a manifest-first corpus pipeline.

## Source Registry

`config/sources.yml` is the canonical source registry. It includes the report's recommended sources:

- official PlantUML docs
- Repo-PlantUML-Dataset
- C4-PlantUML
- py2puml
- Synthetic UML Diagram Dataset
- plantuml-stdlib
- AWS Icons for PlantUML
- PlantUML-Examples by mattjhayes
- coni2k PlantUML reference examples
- plantuml-test
- pdiff

The registry is JSON-valid YAML so the package can parse it with Python's standard library. Each source declares acquisition mode, license policy, pin strategy, expected diagram families, default purpose, and allowed split targets.

## Acquisition

The `plantuml-skill acquire` command creates JSONL manifests from local fixtures and configured external sources.

Supported modes:

- `local`: read an already staged local tree.
- `git`: clone or fetch a repository into `data/raw/<source-id>/`.
- `docs_crawl`: download declared seed pages and extract PlantUML blocks.
- `manual_dataset` and `huggingface_dataset`: require explicit manual staging because the report identified mixed or unclear licensing.

The fixture source is fully runnable without network access:

```bash
plantuml-skill acquire --source fixtures --output data/manifests/fixtures.jsonl
```

## Extraction And Annotation

Extraction supports:

- `.puml`, `.plantuml`, `.iuml`
- Markdown fences tagged `plantuml`, `puml`, or `uml`
- generic `@start...` / `@end...` blocks
- same-basename render pairing such as `diagram.puml` to `diagram.svg`
- include dependency capture through `!include`, `!includeurl`, `!include_many`, and `!include_once`

Each extracted diagram is classified with lightweight heuristics for C4, class, sequence, use case, component, state, activity, and custom `@startXYZ` diagrams.

## Manifest Model

Every corpus row uses `schemas/corpus-record.schema.json` and `plantuml_ai_skill.manifest.CorpusRecord`.

Required metadata includes:

- source name, URL, kind, and pin/ref
- row-level license and license family
- diagram type
- PlantUML path and optional published render path
- Python source paths for source-conditioned examples
- include dependencies and self-contained flags
- PlantUML and Graphviz versions
- SVG/PNG render hashes
- verification status and failure reason
- split purposes such as `training`, `gold_eval`, `renderer_regression`, `source_conditioned_eval`, and `augmentation`

## Splits

`plantuml-skill build-splits` applies the default policy from the report:

- only permissive-license records enter broad training splits;
- unclear-license records stay out of broad training until reviewed;
- gold evaluation is separate from bulk training;
- source-conditioned Python cases get their own split;
- synthetic records are capped before entering augmentation.

## Real-Source Smoke Coverage

The first external smoke target is `plantuml-examples-mattjhayes`, pinned in `config/sources.yml` to a concrete commit. This source is small, permissively licensed, and varied enough to test Markdown extraction, published PNG references, renderer failures, and remote include blocking.

Expected workflow:

```bash
plantuml-skill acquire --source plantuml-examples-mattjhayes --output data/manifests/plantuml-examples.jsonl
plantuml-skill render --manifest data/manifests/plantuml-examples.jsonl --output data/manifests/plantuml-examples-rendered.jsonl --render-dir data/rendered/plantuml-examples
plantuml-skill verify --manifest data/manifests/plantuml-examples-rendered.jsonl --output data/manifests/plantuml-examples-verified.jsonl
```

Non-green records are still valuable. They identify syntax incompatibilities, renderer drift, remote include dependencies, and PNG reference mismatches that should be curated before records are promoted into gold evaluation.

`py2puml` is also pinned and smoke-tested as a source-conditioned corpus. Acquisition pairs expected `.puml` files with nearby Python files, then keeps those records in `source_conditioned_eval`:

```bash
plantuml-skill acquire --source py2puml --output data/manifests/py2puml.jsonl
plantuml-skill render --manifest data/manifests/py2puml.jsonl --output data/manifests/py2puml-rendered.jsonl --render-dir data/rendered/py2puml
plantuml-skill verify --manifest data/manifests/py2puml-rendered.jsonl --output data/manifests/py2puml-verified.jsonl
```
