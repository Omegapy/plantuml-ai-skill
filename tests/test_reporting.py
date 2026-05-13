import unittest

from plantuml_ai_skill.manifest import CorpusRecord
from plantuml_ai_skill.reporting import markdown_report


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
        "published_render_path": "",
        "python_source_paths": [],
        "include_deps": [],
        "is_self_contained": True,
        "uses_include": False,
        "uses_icon_library": False,
        "plantuml_version": "plantuml-java-jar-test",
        "graphviz_version": "",
        "render_status": "ok",
        "render_hash_svg": "hash",
        "render_hash_png": "",
        "verification_status": "rendered_no_reference",
        "render_fail_reason": "",
        "purpose": ["gold_eval"],
        "attribution": "source",
        "license_path": "LICENSE",
        "source_commit": "commit",
        "source_repo_url": "https://example.test/source",
    }
    payload.update(overrides)
    return CorpusRecord(**payload)


class ReportingTests(unittest.TestCase):
    def test_report_groups_curator_diagnostics(self) -> None:
        report = markdown_report(
            [
                record(
                    id="remote",
                    include_deps=["https://example.test/C4.puml"],
                    uses_include=True,
                    is_self_contained=False,
                    render_status="skipped",
                    verification_status="render_skipped",
                    render_fail_reason="remote_include_blocked",
                ),
                record(
                    id="mismatch",
                    published_render_path="diagram.png",
                    verification_status="png_mismatch",
                ),
                record(
                    id="blocked-license",
                    license="GPL-3.0",
                    license_family="copyleft",
                    purpose=["training"],
                ),
            ]
        )
        self.assertIn("### remote_include_blocked", report)
        self.assertIn("`remote`", report)
        self.assertIn("### png_svg_mismatches", report)
        self.assertIn("`mismatch`", report)
        self.assertIn("### license_policy_exclusions", report)
        self.assertIn("blocked_copyleft_license", report)

    def test_report_lists_source_conditioned_pairing_confidence(self) -> None:
        report = markdown_report(
            [
                record(
                    id="source-pair",
                    puml_path="expected.puml",
                    python_source_paths=["model.py"],
                    extra={"source_pairing_confidence": "high"},
                    purpose=["source_conditioned_eval"],
                )
            ]
        )
        self.assertIn("## Source-Conditioned Pairings", report)
        self.assertIn("`expected.puml`", report)
        self.assertIn("`model.py`", report)
        self.assertIn("high", report)


if __name__ == "__main__":
    unittest.main()
