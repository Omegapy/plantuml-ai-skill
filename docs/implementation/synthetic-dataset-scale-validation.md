# Synthetic Dataset Scale Validation

Date: 2026-05-14

## Scope

This validates the staged synthetic dataset at `data/raw/PlantUML_Data` without changing acquisition semantics. The run used only the two small subsets and kept all rows as augmentation-only records:

- `Small_English_Act_Data_Total`
- `Small_English_Seq_Data_Total`

## Commands

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill acquire \
  --source synthetic-uml-diagram-dataset \
  --subset Small_English_Act_Data_Total \
  --subset Small_English_Seq_Data_Total \
  --max-records-per-subset 1000 \
  --output data/manifests/synthetic-phase1.jsonl
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill render \
  --manifest data/manifests/synthetic-phase1.jsonl \
  --output data/manifests/synthetic-phase1-rendered.jsonl \
  --render-dir data/rendered/synthetic-phase1 \
  --batch-size 100
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill verify \
  --manifest data/manifests/synthetic-phase1-rendered.jsonl \
  --output data/manifests/synthetic-phase1-verified.jsonl
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill build-splits \
  --manifest data/manifests/synthetic-phase1-verified.jsonl \
  --output-dir data/manifests/synthetic-phase1-splits
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill report \
  --manifest data/manifests/synthetic-phase1-verified.jsonl \
  --output data/reports/synthetic-phase1-report.md
```

## Throughput

The original per-record renderer shells out once for SVG and once for PNG. On the 40-row smoke sample it rendered 40 rows in 61.32 seconds, or about 39 rows/minute.

The new batched renderer writes temporary `.puml` files and invokes PlantUML once per SVG batch and once per PNG batch. On the same 40 rows with `--batch-size 40`, it rendered in 5.59 seconds, or about 429 rows/minute.

Phase 1 rendered 2,000/2,000 rows in 243.52 seconds, or about 493 rows/minute, using `--batch-size 100`.

PNG verification is now the slower scaling step. After removing redundant PNG decodes and reading dimensions from the PNG header, the 40-row verify step took 8.81 seconds. Phase 1 verify took 496.03 seconds, or about 242 rows/minute.

## Phase 1 Results

- Acquired rows: 2,000
- Activity rows: 1,000
- Sequence rows: 1,000
- Render status: 2,000 `ok`
- Verification: 747 `png_match`, 1,253 `png_mismatch`
- Splits: 2,000 augmentation, 0 train, 0 gold eval, 0 renderer regression, 0 source-conditioned eval
- License family: 2,000 `unknown`
- Purpose: 2,000 `augmentation`

## PNG Mismatch Interpretation

The PNG references are paired correctly by same stem, but they should not be treated as strict verification truth with the pinned PlantUML 1.2026.3 renderer.

The 40-row contact sheet and manual spot checks show two main causes:

- Activity diagrams using older `group` syntax render with new warning banners in PlantUML 1.2026.3. The published PNGs omit these banners, so dimensions and perceptual hashes differ even though the diagram body is the same.
- Sequence diagrams commonly show font, spacing, and layout drift between the published PNGs and the current pinned renderer. Spot-checked high-distance sequence mismatches were visually the same diagram, not bad pairings.

In the 2,000-row Phase 1 run, 549 activity SVGs contained the PlantUML bracket-warning banner text. Of those, 511 were `png_mismatch`. The remaining mismatches are consistent with renderer version, font, and layout drift plus a strict 8x8 average-hash threshold.

## Scale-Up Gates

Phase 2 small-full is practical only with `render --batch-size 100` or similar. At Phase 1 rates, 15,000 small rows would project to roughly 30 minutes of rendering and about 62 minutes of PNG verification, depending on image sizes.

Recommended next gate:

- Run all 15,000 small rows with `--batch-size 100`.
- Treat PNG mismatch as diagnostic evidence, not a failure gate, until warnings/layout drift are normalized or curated.
- Keep broad training blocked because license remains `verify-on-clone` and `license_family="unknown"`.
- Use the proven 2,000-row cap for immediate downstream experiments.
- Do not raise the balanced synthetic augmentation cap above the existing 5,000-row default until the 15,000-row small-full pass confirms similar render success and mismatch causes.
