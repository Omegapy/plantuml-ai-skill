# Synthetic Dataset Scale Validation

Date: 2026-05-14

## Scope

This validates the staged synthetic dataset at `data/raw/PlantUML_Data` without changing acquisition semantics. The validation started with the two small subsets and now records the completed small, medium, and large scale gates. All rows remain augmentation-only records:

- `Small_English_Act_Data_Total`
- `Small_English_Seq_Data_Total`
- `Med_English_Act_Data_Total`
- `Med_English_Seq_Data_Total`
- `Large_English_Act_Data_Total`
- `Large_English_Seq_Data_Total`

The synthetic dataset is useful as scale augmentation and renderer-stability evidence. It is not treated as high-trust train or gold-evaluation data because the license family remains `unknown`, the rows are synthetic, and the published PNGs show substantial renderer/version drift against the pinned local renderer.

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

## Extended Scale Results

Later scale gates reused the same acquire, batched render, verify, report, and split posture as the small phases. Medium and large pilot timings below are local artifact timestamp spans because no timer logs were preserved for those commands; they should be read as operational evidence, not benchmark-grade measurements. The large-full timings came from the completed timed run and are preserved here because the generated `data/` artifacts are ignored.

| Gate | Rows | Activity Rows | Sequence Rows | Render OK | PNG Match | PNG Mismatch | Render Time | Verify Time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| small 2k | 2,000 | 1,000 | 1,000 | 2,000 | 747 | 1,253 | 243.52s | 496.03s |
| small-full | 15,000 | 7,500 | 7,500 | 15,000 | 5,953 | 9,047 | 2,080.08s | 833.68s |
| medium 2k | 2,000 | 1,000 | 1,000 | 2,000 | 723 | 1,277 | ~270s | ~389s |
| medium 5k | 5,000 | 2,500 | 2,500 | 5,000 | 2,185 | 2,815 | ~805s | ~323s |
| medium-full | 17,998 | 15,000 | 2,998 | 17,998 | 8,198 | 9,800 | ~3,837s | ~1,311s |
| large 2k | 2,000 | 1,000 | 1,000 | 2,000 | 736 | 1,264 | ~275s | ~610s |
| large 5k | 5,000 | 2,500 | 2,500 | 5,000 | 2,227 | 2,773 | ~816s | ~265s |
| large-full | 59,924 | 29,963 | 29,961 | 59,924 | 29,298 | 30,626 | 13,575.70s | 3,104.47s |

Verification by diagram type:

| Gate | Activity Match | Activity Mismatch | Sequence Match | Sequence Mismatch |
| --- | ---: | ---: | ---: | ---: |
| small 2k | 302 | 698 | 445 | 555 |
| small-full | 2,833 | 4,667 | 3,120 | 4,380 |
| medium 2k | 284 | 716 | 439 | 561 |
| medium 5k | 1,089 | 1,411 | 1,096 | 1,404 |
| medium-full | 6,890 | 8,110 | 1,308 | 1,690 |
| large 2k | 303 | 697 | 433 | 567 |
| large 5k | 1,077 | 1,423 | 1,150 | 1,350 |
| large-full | 14,915 | 15,048 | 14,383 | 15,578 |

Large-full split generation was run after verification:

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill report \
  --manifest data/manifests/synthetic-large-full-verified.jsonl \
  --output data/reports/synthetic-large-full-report.md
```

```bash
PYTHONPATH=src /opt/homebrew/bin/python3.12 -m plantuml_ai_skill build-splits \
  --manifest data/manifests/synthetic-large-full-verified.jsonl \
  --output-dir data/manifests/synthetic-large-full-splits \
  --synthetic-cap 5000
```

The split output kept the expected posture:

- `augmentation`: 5,000
- `train`: 0
- `gold_eval`: 0
- `renderer_regression`: 0
- `source_conditioned_eval`: 0

## Acceptance Criteria

The scale gate is a stability gate, not a visual-equivalence gate:

- Every acquired row must produce a rendered row.
- `render_status` must be `ok` for every row.
- `verify` must write a verified row for every rendered row.
- `verify_error` must be 0.
- Remote include violations must be 0.
- Synthetic rows must remain augmentation-only unless licensing and curation policy changes.

Under these criteria, large-full passed. The `verify` command can still exit nonzero when `png_mismatch` rows exist; that is expected for this dataset. PNG mismatch is diagnostic evidence about renderer/version/layout drift and should not be used as a blocking failure without additional curation.

## PNG Mismatch Interpretation

The PNG references are paired correctly by same stem, but they should not be treated as strict verification truth with the pinned PlantUML 1.2026.3 renderer.

The 40-row contact sheet and manual spot checks show two main causes:

- Activity diagrams using older `group` syntax render with new warning banners in PlantUML 1.2026.3. The published PNGs omit these banners, so dimensions and perceptual hashes differ even though the diagram body is the same.
- Sequence diagrams commonly show font, spacing, and layout drift between the published PNGs and the current pinned renderer. Spot-checked high-distance sequence mismatches were visually the same diagram, not bad pairings.

In the 2,000-row Phase 1 run, 549 activity SVGs contained the PlantUML bracket-warning banner text. Of those, 511 were `png_mismatch`. The remaining mismatches are consistent with renderer version, font, and layout drift plus a strict 8x8 average-hash threshold.

In the 15,000-row small-full run, 3,457 rendered SVGs contained the bracket-warning banner text. Of those, 3,228 were `png_mismatch` and 229 were still within the current PNG perceptual threshold. Almost all warning-banner rows were activity diagrams. Mismatch distances remained consistent with the Phase 1 interpretation: matches had distances 0-5 with median 2, and mismatches had distances 6-61 with median 13.

## Large-Full Mismatch Diagnostics

Large-full verification produced 29,298 `png_match` rows and 30,626 `png_mismatch` rows, a 51.11% mismatch rate. The mismatch rate was balanced enough that it does not indicate a broken pairing pipeline:

- Activity: 15,048/29,963 mismatches, 50.22%.
- Sequence: 15,578/29,961 mismatches, 51.99%.
- `Test`: 6,091/11,930 mismatches, 51.06%.
- `Train/1`: 5,167/7,950 mismatches, 64.99%.
- `Train/2`: 4,119/8,028 mismatches, 51.31%.
- `Train/3`: 4,125/8,111 mismatches, 50.86%.
- `Train/4`: 11,124/23,905 mismatches, 46.53%.

Hash-distance distribution stayed consistent with the earlier small-full interpretation:

| Status | Min | P25 | Median | P75 | P90 | P95 | P99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `png_match` | 0 | 1 | 2 | 4 | 5 | 5 | 5 | 5 |
| `png_mismatch` | 6 | 8 | 12 | 18 | 29 | 35 | 45 | 61 |

Dimension drift exists even among rows that match under the current threshold, so dimensions alone are not a reliable failure signal:

| Status | Median Abs Width Delta | P90 Abs Width Delta | Max Abs Width Delta | Median Abs Height Delta | P90 Abs Height Delta | Max Abs Height Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `png_match` | 25px | 70px | 303px | 11px | 17px | 104px |
| `png_mismatch` | 27px | 118px | 410px | 13px | 59px | 113px |

The strongest activity-diagram mismatch feature is legacy `group` syntax. In large-full activity rows, filenames with `Group>0` mismatched 9,051/9,622 times, or 94.07%. A representative rendered SVG for `Act443315188-If0-Switch0-Repeat0-While0-Fork0-Split0-Group1-Lane0.txt` contains PlantUML warning-banner text telling the author to use bracketed `group` syntax; the published PNG omits the banner, so the rendered dimensions changed from 161x176 to 527x231 and the hash distance was 42.

Low-distance mismatches are often harmless renderer drift:

- `Seq540827388-Part2-Mess1-Box0-Group1-Activ0-Delay0-AutoNum0.txt`: distance 6, dimensions 362x163 published versus 362x165 rendered.
- `Seq540827181-Part1-Mess2-Box1-Group0-Activ1-Delay0-AutoNum0.txt`: distance 6, dimensions 171x242 published versus 171x244 rendered.

High-distance sequence mismatches deserve targeted curation before they are used as fidelity lessons:

- `Seq770042090-Part4-Mess5-Box2-Group0-Activ0-Delay1-AutoNum0.txt`: distance 61, dimensions 546x357 published versus 579x348 rendered.
- `Seq770013475-Part4-Mess7-Box2-Group3-Activ4-Delay2-AutoNum1.txt`: distance 60, dimensions 611x717 published versus 650x697 rendered.

These diagnostics do not justify changing verifier semantics just to reduce mismatch counts. They justify a separate, curated fidelity loop only if the project wants to classify renderer drift families and turn a small number of stable lessons into skill guidance.

## Large-Full Conclusion

Large-full passed the scale and stability gates:

- 59,924 input rows.
- 59,924 rendered rows.
- 59,924 verified rows.
- 59,924 `render_status=ok`.
- 0 render failures.
- 0 verification errors.
- 0 skipped rows.
- 0 remote include violations.

The current decision is to treat the skill as promoted and package-ready, while keeping the synthetic corpus as augmentation and diagnostics. The next improvement loop should not be another broad synthetic scale run. If further work is desired, it should be a small mismatch-derived curation loop focused on activity `group` warning patterns and high-distance sequence layout drift.

## Scale-Up Gates

Phase 2 small-full is practical only with `render --batch-size 100` or similar. The completed run confirms render is acceptable for the 15,000-row small set, but single-process PNG verification is not operationally acceptable for larger phases.

Recommended next gate:

- Add first-class parallel or checkpointed verification before medium, large, extra-large, or all-synthetic runs.
- Add progress logging to both batched render and verify so long validations are observable without filesystem probing.
- Treat PNG mismatch as diagnostic evidence, not a failure gate, until warnings/layout drift are normalized or curated.
- Keep broad training blocked because license remains `verify-on-clone` and `license_family="unknown"`.
- Keep the balanced synthetic augmentation cap at the existing 5,000-row default for now; the small-full split already selects 5,000 augmentation records from 15,000 candidates.
- Use the 2,000-row Phase 1 cap for fast iteration and the 5,000-row split cap for downstream experiments that need more variety.
- Do not scale beyond large-full without a specific curation question; the pipeline has already passed the large-full stability gate.
