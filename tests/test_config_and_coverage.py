from pathlib import Path
import json
import unittest

from plantuml_ai_skill.config import load_sources_config
from plantuml_ai_skill.constants import REPORT_RECOMMENDED_FEATURES, REPORT_RECOMMENDED_SOURCES
from plantuml_ai_skill.manifest import REQUIRED_RECORD_FIELDS
from plantuml_ai_skill.recommendation_coverage import check_recommendation_coverage


ROOT = Path(__file__).resolve().parents[1]


class ConfigCoverageTests(unittest.TestCase):
    def test_sources_config_covers_report_sources_and_features(self) -> None:
        config = load_sources_config(ROOT / "config" / "sources.yml")
        result = check_recommendation_coverage(config)
        self.assertTrue(result.ok, result)
        self.assertEqual(REPORT_RECOMMENDED_SOURCES, config.source_ids())
        self.assertEqual(REPORT_RECOMMENDED_FEATURES, config.recommendation_features)

    def test_schema_declares_manifest_required_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "corpus-record.schema.json").read_text())
        self.assertEqual(set(REQUIRED_RECORD_FIELDS), set(schema["required"]))

    def test_eval_case_schema_accepts_palette_policy(self) -> None:
        schema = json.loads((ROOT / "schemas" / "skill-eval-case.schema.json").read_text())
        self.assertIn("palette_policy", schema["properties"])
        self.assertIn("aether_dark_required", schema["properties"]["palette_policy"]["enum"])
        self.assertIn("aether_dark_rendered_required", schema["properties"]["palette_policy"]["enum"])


if __name__ == "__main__":
    unittest.main()
