"""Checks that the report recommendations have implementation coverage."""

from __future__ import annotations

from dataclasses import dataclass

from .config import SourcesConfig
from .constants import REPORT_RECOMMENDED_FEATURES, REPORT_RECOMMENDED_SOURCES


@dataclass(frozen=True)
class CoverageResult:
    missing_sources: set[str]
    missing_features: set[str]

    @property
    def ok(self) -> bool:
        return not self.missing_sources and not self.missing_features


def check_recommendation_coverage(config: SourcesConfig) -> CoverageResult:
    return CoverageResult(
        missing_sources=REPORT_RECOMMENDED_SOURCES - config.source_ids(),
        missing_features=REPORT_RECOMMENDED_FEATURES - config.recommendation_features,
    )
