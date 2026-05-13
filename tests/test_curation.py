import json
from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.curation import apply_curation, load_curation_decisions
from plantuml_ai_skill.manifest import CorpusRecord


def record(**overrides: object) -> CorpusRecord:
    payload = {
        "id": "record-1",
        "source_name": "source",
        "source_url": "https://example.test/source",
        "source_kind": "git_repository",
        "source_ref": "ref",
        "license": "MIT",
        "license_family": "permissive",
        "diagram_type": "class",
        "puml_path": "diagram.puml",
        "published_render_path": "diagram.png",
        "python_source_paths": [],
        "include_deps": [],
        "is_self_contained": True,
        "uses_include": False,
        "uses_icon_library": False,
        "plantuml_version": "plantuml-java-jar-test",
        "graphviz_version": "",
        "render_status": "ok",
        "render_hash_svg": "hash",
        "render_hash_png": "hash",
        "verification_status": "png_mismatch",
        "render_fail_reason": "",
        "purpose": ["gold_eval"],
        "attribution": "source",
        "license_path": "LICENSE",
        "source_commit": "commit",
        "source_repo_url": "https://example.test/source",
    }
    payload.update(overrides)
    return CorpusRecord(**payload)


class CurationTests(unittest.TestCase):
    def test_load_and_apply_curation_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "curation.json"
            path.write_text(
                json.dumps(
                    {
                        "source_name": "source",
                        "reviewer": "curator",
                        "reviewed_at": "2026-05-13",
                        "decisions": [
                            {
                                "record_id": "record-1",
                                "applies_to": "png_mismatch",
                                "status": "minor_acceptable_drift",
                                "rationale": "same diagram with small styling drift",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            decisions = load_curation_decisions(path)
            records = apply_curation([record()], decisions)
        self.assertEqual("minor_acceptable_drift", records[0].extra["curation_status"])
        self.assertEqual("curator", records[0].extra["curation_reviewer"])
        self.assertEqual("2026-05-13", records[0].extra["curation_reviewed_at"])

    def test_curation_source_must_match_record_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "curation.json"
            path.write_text(
                json.dumps(
                    {
                        "source_name": "other-source",
                        "decisions": [
                            {
                                "record_id": "record-1",
                                "applies_to": "png_mismatch",
                                "status": "minor_acceptable_drift",
                                "rationale": "same diagram",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            decisions = load_curation_decisions(path)
            records = apply_curation([record()], decisions)
        self.assertNotIn("curation_status", records[0].extra)


if __name__ == "__main__":
    unittest.main()
