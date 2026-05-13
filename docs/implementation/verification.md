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

Resolved local includes are inlined before the diagram is piped to PlantUML. This keeps rendering compatible with the conservative sandbox profile without letting the renderer read arbitrary files at runtime.

## SVG Comparison

SVG is the preferred verification format. `plantuml_ai_skill.verify.normalize_svg` removes unstable generator metadata, comments, ids, and URL fragments, then canonicalizes attributes while preserving document order. Hash comparison then uses SHA-256 over the normalized SVG.

This avoids false mismatches from volatile SVG identifiers without pretending that every rendered pixel is semantically irrelevant.

## PNG Fallback

PNG comparison is a fallback for sources that publish only raster references. The stdlib implementation decodes 8-bit grayscale, RGB, RGBA, and indexed-color PNGs, computes an average hash, and compares Hamming distance. It is intentionally secondary to SVG comparison.

## Source-Conditioned Evaluation

The fixtures include py2puml-style Python source to PlantUML expected-output pairs. These records populate `source_conditioned_eval`, keeping Python-source-conditioned verification separate from general PlantUML text training.

## Recommended Local Verification

```bash
plantuml-skill coverage
plantuml-skill init-assets
plantuml-skill doctor
plantuml-skill acquire --source fixtures --output data/manifests/fixtures.jsonl
plantuml-skill render --manifest data/manifests/fixtures.jsonl --output data/manifests/rendered.jsonl
plantuml-skill verify --manifest data/manifests/rendered.jsonl --output data/manifests/verified.jsonl
plantuml-skill audit-licenses --manifest data/manifests/verified.jsonl
plantuml-skill build-splits --manifest data/manifests/verified.jsonl
plantuml-skill report --manifest data/manifests/verified.jsonl
```

If Java is not installed, `doctor`, `init-assets` verification, and real rendering will stop with an actionable runtime message.
