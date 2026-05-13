# Verification

The report emphasizes renderer reproducibility as strongly as corpus size. The implementation follows that guidance with a pinned Java renderer, Graphviz checks, local include policy, normalized SVG comparison, and PNG fallback hashing.

## Renderer Stack

The primary renderer is:

```bash
java -Djava.awt.headless=true \
  -DPLANTUML_SECURITY_PROFILE=SANDBOX \
  -jar tools/plantuml/plantuml-1.2026.3.jar \
  -tsvg -pipe -charset UTF-8
```

Java 11 or newer is required. Graphviz remains required because PlantUML uses `dot` for several diagram families, including class, component, deployment, state, object, use case, legacy activity, and DOT-backed diagrams.

On macOS, Homebrew installs OpenJDK as keg-only. The CLI automatically checks `/opt/homebrew/opt/openjdk/bin/java` and `/usr/local/opt/openjdk/bin/java` before falling back to `java` on `PATH`. Set `PLANTUML_JAVA` or pass `--java` to override detection.

`plantuml-skill doctor` checks:

- `java -version`
- `dot -V`
- pinned jar checksum
- `java -jar plantuml.jar -testdot`

## Asset Pinning

`plantuml-skill init-assets` downloads `plantuml-1.2026.3.jar` from the official PlantUML release, verifies its SHA-256 checksum, and writes local metadata next to the jar. The asset directory is ignored by Git.

## Include Handling

The extractor records `!include` dependencies and marks diagrams as non-self-contained when includes are present. External rendering uses local vendored include roots only. Remote includes are treated as blocked during batch verification.

Resolved local includes are inlined before the diagram is piped to PlantUML. Inlining is recursive for local nested includes, while unresolved remote includes remain blocked. This keeps rendering compatible with the conservative sandbox profile without letting the renderer read arbitrary files at runtime.

C4-PlantUML includes can be vendored from the pinned source registry entry:

```bash
plantuml-skill vendor-includes --source c4-plantuml --output data/vendor/c4-plantuml --force
```

Known C4-PlantUML URLs of the form `https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/<include>.puml` are mapped to the pinned local C4 vendor snapshot. This mapping is intentionally narrow: arbitrary remote includes are still reported as `remote_include_blocked`.

## SVG Comparison

SVG is the preferred verification format. `plantuml_ai_skill.verify.normalize_svg` removes unstable generator metadata, comments, ids, and URL fragments, then canonicalizes attributes while preserving document order. Hash comparison then uses SHA-256 over the normalized SVG.

This avoids false mismatches from volatile SVG identifiers without pretending that every rendered pixel is semantically irrelevant.

## PNG Fallback

PNG comparison is a fallback for sources that publish only raster references. The stdlib implementation decodes 8-bit grayscale, RGB, RGBA, and indexed-color PNGs, computes an average hash, and compares Hamming distance. Verified records retain PNG hash distance and published/rendered dimensions in manifest metadata so curators can distinguish small drift from obvious mismatches. It is intentionally secondary to SVG comparison.

For visual review, generate a side-by-side HTML contact sheet for PNG mismatches:

```bash
plantuml-skill png-contact-sheet --manifest data/manifests/plantuml-examples-verified.jsonl --output data/reports/plantuml-examples-png-contact-sheet.html
```

Reviewed visual mismatches are recorded under `config/curation/`. The accepted status vocabulary is:

- `renderer_version_drift`: same source appears to render differently under the pinned PlantUML/Graphviz stack.
- `published_image_drift`: published PNG likely came from an older or different source or include snapshot.
- `minor_acceptable_drift`: visually equivalent enough for curator-approved `gold_eval` promotion.
- `suspicious_pairing`: image and code may still be incorrectly paired.
- `true_regression`: rendered output appears meaningfully wrong.

Promotion stays conservative: a PNG/SVG mismatch without curation is blocked, and a reviewed mismatch is promoted only when the curation status is explicitly allowed for that split. Currently `minor_acceptable_drift` is allowed for `gold_eval`; other reviewed mismatch classes remain blocked.

The remaining PlantUML-Examples mindmap failure has a recorded `renderer_version_drift` disposition. The raw source is intact, and `PlantUML 1.2026.3` rejects `style mindmapDiagram`; removing only that style block renders successfully. The pipeline records the incompatibility rather than silently transforming the example.

Some PlantUML diagram families emit status chatter before piped SVG/PNG bytes. The renderer strips that prefix before hashing or decoding so valid diagrams are not mislabeled as renderer failures.

## Source-Conditioned Evaluation

The fixtures include py2puml-style Python source to PlantUML expected-output pairs. These records populate `source_conditioned_eval`, keeping Python-source-conditioned verification separate from general PlantUML text training.

External py2puml acquisition maps fully qualified classes and enums in expected `.puml` files back to Python modules first. Records carry `source_pairing_confidence` metadata so reports can distinguish high-confidence source-conditioned rows from heuristic fallbacks.

## Recommended Local Verification

This is a local-only development project. Verification is intended to run on the developer machine with the pinned PlantUML jar, a local Java runtime, and local Graphviz. GitHub Actions, GitHub CLI authentication, and remote runners are not required quality gates.

```bash
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m plantuml_ai_skill doctor
PYTHONPATH=src python -m plantuml_ai_skill acquire --source fixtures --output data/manifests/fixtures.jsonl
PYTHONPATH=src python -m plantuml_ai_skill render --manifest data/manifests/fixtures.jsonl --output data/manifests/rendered.jsonl --render-dir data/rendered
PYTHONPATH=src python -m plantuml_ai_skill verify --manifest data/manifests/rendered.jsonl --output data/manifests/verified.jsonl
```

If Java is not installed, `doctor`, `init-assets` verification, and real rendering will stop with an actionable runtime message.
