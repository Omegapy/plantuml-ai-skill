# Configuration

This folder contains tracked configuration used by the acquisition,
verification, licensing, and curation pipeline.

## Files

- `sources.yml`: canonical source registry for fixture, local, Git, crawler,
  and manually staged corpus sources.
- `license-blocklist.yml`: repositories or license families that must not enter
  trusted training/evaluation splits.
- `license-overrides.yml`: reviewed license classifications that supplement
  source metadata.
- `curation/`: human-reviewed decisions for known render drift, PNG/SVG
  mismatches, suspicious pairings, and other corpus diagnostics.

Generated manifests and rendered outputs belong under ignored `data/` paths.
