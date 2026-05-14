"""Shared constants for the PlantUML training-data pipeline."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PLANTUML_VERSION = "1.2026.3"
PLANTUML_JAR_NAME = f"plantuml-{PLANTUML_VERSION}.jar"
PLANTUML_RELEASE_TAG = f"v{PLANTUML_VERSION}"
PLANTUML_JAR_URL = (
    "https://github.com/plantuml/plantuml/releases/download/"
    f"{PLANTUML_RELEASE_TAG}/{PLANTUML_JAR_NAME}"
)
PLANTUML_JAR_SHA256 = (
    "53af6760d96bb2737e5e4386e832b46339fc29dec74f412d7c12db7c30db8ec4"
)

MIN_JAVA_MAJOR = 11
DEFAULT_ASSET_DIR = PROJECT_ROOT / "tools" / "plantuml"
DEFAULT_JAR_PATH = DEFAULT_ASSET_DIR / PLANTUML_JAR_NAME
DEFAULT_SOURCES_CONFIG = PROJECT_ROOT / "config" / "sources.yml"
DEFAULT_LICENSE_OVERRIDES_PATH = PROJECT_ROOT / "config" / "license-overrides.yml"
DEFAULT_LICENSE_BLOCKLIST_PATH = PROJECT_ROOT / "config" / "license-blocklist.yml"
DEFAULT_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "corpus-record.schema.json"

GENERATED_DIRS = (
    PROJECT_ROOT / "data" / "raw",
    PROJECT_ROOT / "data" / "rendered",
    PROJECT_ROOT / "data" / "manifests",
    PROJECT_ROOT / "data" / "reports",
)

PERMISSIVE_LICENSES = {
    "apache-2.0",
    "bsd",
    "bsd-2-clause",
    "bsd-3-clause",
    "cc0",
    "isc",
    "mit",
    "unlicense",
}

WEAK_COPYLEFT_LICENSES = {"epl", "epl-2.0", "lgpl", "lgpl-3.0", "mpl", "mpl-2.0"}
COPYLEFT_LICENSES = {"agpl", "gpl", "gpl-2.0", "gpl-3.0"}

REPORT_RECOMMENDED_SOURCES = {
    "official-plantuml-docs",
    "repo-plantuml-dataset",
    "c4-plantuml",
    "py2puml",
    "synthetic-uml-diagram-dataset",
    "plantuml-stdlib",
    "aws-icons-for-plantuml",
    "plantuml-examples-mattjhayes",
    "coni2k-plantuml-reference",
    "plantuml-test",
    "pdiff",
    "azure-plantuml",
}

REPORT_RECOMMENDED_FEATURES = {
    "pinned_java_plantuml_renderer",
    "graphviz_testdot_check",
    "vendored_include_roots",
    "row_level_provenance_manifest",
    "license_family_filtering",
    "gold_eval_split",
    "synthetic_augmentation_cap",
    "normalized_svg_comparison",
    "png_perceptual_fallback",
    "python_source_conditioned_cases",
    "recommendation_coverage_test",
}
