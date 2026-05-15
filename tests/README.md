# Tests

This folder contains unit and integration-style tests for the PlantUML skill
pipeline, release package builder, renderer contracts, and improvement harness.

## Fixtures

`fixtures/` contains small tracked examples used by tests. Keep fixtures small,
permissively reusable, and deterministic. Large corpora, rendered batches, and
downloaded sources belong under ignored `data/` paths.

## Common Commands

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Focused release package check:

```bash
PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/plantuml-pycache /opt/homebrew/bin/python3.12 -m unittest tests.test_release_packages -v
```

The parallel verifier tests can fail under restricted sandboxes that block
worker processes. Rerun outside the sandbox before treating those failures as
repository regressions.
