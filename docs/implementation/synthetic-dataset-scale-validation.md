# Synthetic Dataset Scale Validation

Date: 2026-05-14

## Scope

This validates the staged synthetic dataset at `data/raw/PlantUML_Data` without changing acquisition semantics. The run used only the two small subsets and kept all rows as augmentation-only records:

- `Small_English_Act_Data_Total`
- `Small_English_Seq_Data_Total`

## Commands

Phase 1 pilot:

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

Phase 2 small-full:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill acquire \
  --source synthetic-uml-diagram-dataset \
  --subset Small_English_Act_Data_Total \
  --subset Small_English_Seq_Data_Total \
  --output data/manifests/synthetic-small-full.jsonl
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill render \
  --manifest data/manifests/synthetic-small-full.jsonl \
  --output data/manifests/synthetic-small-full-rendered.jsonl \
  --render-dir data/rendered/synthetic-small-full \
  --batch-size 100
```

The initial single-process verify run exceeded 60 minutes of CPU time without finishing and was stopped. The completed small-full verified manifest was produced by splitting `synthetic-small-full-rendered.jsonl` into 15 ordered 1,000-row shards, running the existing `verify` command on shards with 8 workers, and concatenating `verified-000` through `verified-014` in order:

```bash
mkdir -p data/manifests/synthetic-small-full-verify-shards
split -l 1000 -d -a 3 \
  data/manifests/synthetic-small-full-rendered.jsonl \
  data/manifests/synthetic-small-full-verify-shards/input-
```

```bash
PYTHONPATH=src /usr/bin/time -p zsh -lc '
workers=8
count=0
for input in data/manifests/synthetic-small-full-verify-shards/input-*; do
  output=${input/input-/verified-}
  (
    PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill verify \
      --manifest "$input" \
      --output "$output" > "$output.log" 2>&1
    exit 0
  ) &
  count=$((count + 1))
  if [ $((count % workers)) -eq 0 ]; then
    wait
  fi
done
wait
'
cat data/manifests/synthetic-small-full-verify-shards/verified-[0-9][0-9][0-9] \
  > data/manifests/synthetic-small-full-verified.jsonl
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill build-splits \
  --manifest data/manifests/synthetic-small-full-verified.jsonl \
  --output-dir data/manifests/synthetic-small-full-splits
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill report \
  --manifest data/manifests/synthetic-small-full-verified.jsonl \
  --output data/reports/synthetic-small-full-report.md
```

## Throughput

The original per-record renderer shells out once for SVG and once for PNG. On the 40-row smoke sample it rendered 40 rows in 61.32 seconds, or about 39 rows/minute.

The new batched renderer writes temporary `.puml` files and invokes PlantUML once per SVG batch and once per PNG batch. On the same 40 rows with `--batch-size 40`, it rendered in 5.59 seconds, or about 429 rows/minute.

Phase 1 rendered 2,000/2,000 rows in 243.52 seconds, or about 493 rows/minute, using `--batch-size 100`.

PNG verification is now the slower scaling step. After removing redundant PNG decodes and reading dimensions from the PNG header, the 40-row verify step took 8.81 seconds. Phase 1 verify took 496.03 seconds, or about 242 rows/minute.

Phase 2 small-full acquisition wrote 15,000 rows in 5.05 seconds. Batched render completed 15,000/15,000 rows in 2,080.08 seconds, or about 433 rows/minute. Single-process verify did not finish after more than 60 minutes of CPU time, so small-full verification was completed with 15 ordered shards and 8 workers in 833.68 seconds, or about 1,080 rows/minute wall-clock.

## Phase 1 Results

- Acquired rows: 2,000
- Activity rows: 1,000
- Sequence rows: 1,000
- Render status: 2,000 `ok`
- Verification: 747 `png_match`, 1,253 `png_mismatch`
- Splits: 2,000 augmentation, 0 train, 0 gold eval, 0 renderer regression, 0 source-conditioned eval
- License family: 2,000 `unknown`
- Purpose: 2,000 `augmentation`

## Phase 2 Small-Full Results

- Acquired rows: 15,000
- Activity rows: 7,500
- Sequence rows: 7,500
- Render status: 15,000 `ok`
- Verification: 5,953 `png_match`, 9,047 `png_mismatch`
- Activity verification: 2,833 `png_match`, 4,667 `png_mismatch`
- Sequence verification: 3,120 `png_match`, 4,380 `png_mismatch`
- Splits: 5,000 augmentation, 0 train, 0 gold eval, 0 renderer regression, 0 source-conditioned eval
- License family: 15,000 `unknown`
- Purpose: 15,000 `augmentation`

## PNG Mismatch Interpretation

The PNG references are paired correctly by same stem, but they should not be treated as strict verification truth with the pinned PlantUML 1.2026.3 renderer.

The 40-row contact sheet and manual spot checks show two main causes:

- Activity diagrams using older `group` syntax render with new warning banners in PlantUML 1.2026.3. The published PNGs omit these banners, so dimensions and perceptual hashes differ even though the diagram body is the same.
- Sequence diagrams commonly show font, spacing, and layout drift between the published PNGs and the current pinned renderer. Spot-checked high-distance sequence mismatches were visually the same diagram, not bad pairings.

In the 2,000-row Phase 1 run, 549 activity SVGs contained the PlantUML bracket-warning banner text. Of those, 511 were `png_mismatch`. The remaining mismatches are consistent with renderer version, font, and layout drift plus a strict 8x8 average-hash threshold.

In the 15,000-row small-full run, 3,457 rendered SVGs contained the bracket-warning banner text. Of those, 3,228 were `png_mismatch` and 229 were still within the current PNG perceptual threshold. Almost all warning-banner rows were activity diagrams. Mismatch distances remained consistent with the Phase 1 interpretation: matches had distances 0-5 with median 2, and mismatches had distances 6-61 with median 13.

## Scale-Up Gates

Phase 2 small-full is practical only with `render --batch-size 100` or similar. The completed run confirms render is acceptable for the 15,000-row small set, but single-process PNG verification is not operationally acceptable for larger phases.

Recommended next gate:

- Add first-class parallel or checkpointed verification before medium, large, extra-large, or all-synthetic runs.
- Add progress logging to both batched render and verify so long validations are observable without filesystem probing.
- Treat PNG mismatch as diagnostic evidence, not a failure gate, until warnings/layout drift are normalized or curated.
- Keep broad training blocked because license remains `verify-on-clone` and `license_family="unknown"`.
- Keep the balanced synthetic augmentation cap at the existing 5,000-row default for now; the small-full split already selects 5,000 augmentation records from 15,000 candidates.
- Use the 2,000-row Phase 1 cap for fast iteration and the 5,000-row split cap for downstream experiments that need more variety.
- Do not scale beyond small-full until parallel verification is implemented in the CLI rather than as an ad hoc shard wrapper.
