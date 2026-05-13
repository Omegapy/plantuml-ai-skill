import unittest

from plantuml_ai_skill.manifest import CorpusRecord


VALID_RECORD = {
    "id": "record-1",
    "source_name": "fixtures",
    "source_url": "local",
    "source_kind": "local",
    "source_ref": "local",
    "license": "MIT",
    "license_family": "permissive",
    "diagram_type": "sequence",
    "puml_path": "plantuml/sequence.puml",
    "published_render_path": "",
    "python_source_paths": [],
    "include_deps": [],
    "is_self_contained": True,
    "uses_include": False,
    "uses_icon_library": False,
    "plantuml_version": "1.2026.3",
    "graphviz_version": "",
    "render_status": "not_rendered",
    "render_hash_svg": "",
    "render_hash_png": "",
    "verification_status": "not_verified",
    "render_fail_reason": "",
    "purpose": ["gold_eval"],
    "attribution": "fixtures",
    "license_path": "",
    "source_commit": "local",
    "source_repo_url": "local",
}


class SchemaValidationTests(unittest.TestCase):
    def test_valid_record_passes_schema_subset(self) -> None:
        record = CorpusRecord.from_mapping(dict(VALID_RECORD))
        self.assertEqual("record-1", record.id)

    def test_invalid_render_status_fails_with_useful_message(self) -> None:
        invalid = dict(VALID_RECORD)
        invalid["render_status"] = "surprise"
        with self.assertRaisesRegex(ValueError, "render_status"):
            CorpusRecord.from_mapping(invalid)

    def test_missing_attribution_fails_required_field_check(self) -> None:
        invalid = dict(VALID_RECORD)
        invalid.pop("attribution")
        with self.assertRaisesRegex(ValueError, "attribution"):
            CorpusRecord.from_mapping(invalid)


if __name__ == "__main__":
    unittest.main()
