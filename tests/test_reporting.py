import unittest

from plantuml_ai_skill.manifest import CorpusRecord
from plantuml_ai_skill.reporting import (
    classify_render_failure,
    markdown_report,
    render_failure_report,
    render_failure_summary_report,
    render_failure_triage_report,
)


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
                    id="mirrored",
                    include_deps=[
                        "https://raw.githubusercontent.com/plantuml-stdlib/"
                        "C4-PlantUML/master/C4_Container.puml"
                    ],
                    uses_include=True,
                    is_self_contained=False,
                    extra={
                        "include_resolution_status": "trusted_remote_mirrored",
                        "mirrored_include_deps": [
                            "https://raw.githubusercontent.com/plantuml-stdlib/"
                            "C4-PlantUML/master/C4_Container.puml"
                        ],
                    },
                ),
                record(
                    id="mismatch",
                    published_render_path="diagram.png",
                    verification_status="png_mismatch",
                    extra={
                        "curation_status": "minor_acceptable_drift",
                        "curation_rationale": "same diagram with small styling drift",
                    },
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
        self.assertIn("### trusted_remote_includes_mirrored", report)
        self.assertIn("`mirrored`", report)
        self.assertIn("### png_svg_mismatches", report)
        self.assertIn("`mismatch`", report)
        self.assertIn("reviewed=minor_acceptable_drift", report)
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

    def test_render_failure_report_lists_failed_and_skipped_records(self) -> None:
        report = render_failure_report(
            [
                record(
                    source_ref="owner/failed",
                    puml_path="failed.puml",
                    render_status="failed",
                    render_fail_reason="Syntax Error?\nSome detail",
                ),
                record(
                    source_ref="owner/skipped",
                    puml_path="skipped.puml",
                    render_status="skipped",
                    render_fail_reason="remote_include_blocked",
                ),
                record(source_ref="owner/ok", puml_path="ok.puml"),
            ]
        )

        self.assertIn("source_ref\tpuml_path\trender_status\trender_fail_reason", report)
        self.assertIn("owner/failed\tfailed.puml\tfailed\tSyntax Error? Some detail", report)
        self.assertIn("owner/skipped\tskipped.puml\tskipped\tremote_include_blocked", report)
        self.assertNotIn("owner/ok", report)

    def test_render_failure_triage_report_classifies_conservatively(self) -> None:
        report = render_failure_triage_report(
            [
                record(
                    source_ref="owner/dot",
                    puml_path="dot.puml",
                    render_status="failed",
                    render_fail_reason="This looks like a DOT diagram. Please use @startdot instead of @startuml.",
                ),
                record(
                    source_ref="owner/remote",
                    puml_path="remote.puml",
                    render_status="skipped",
                    render_fail_reason="remote_include_blocked",
                ),
                record(
                    source_ref="owner/gpl",
                    puml_path="activity.puml",
                    license_family="copyleft",
                    render_status="failed",
                    render_fail_reason="ERROR 72 Cannot find if (Assumed diagram type: activity)",
                ),
            ]
        )

        self.assertIn(
            "source_ref\tpuml_path\tlicense_family\trender_status\tfailure_class\tactionability",
            report,
        )
        self.assertIn("owner/dot\tdot.puml\tpermissive\tfailed\tdot_inside_startuml", report)
        self.assertIn("not_recoverable_as_plantuml", report)
        self.assertIn("owner/remote\tremote.puml\tpermissive\tskipped\tunsupported_remote_include", report)
        self.assertIn("potentially_recoverable_with_audited_vendor_includes", report)
        self.assertIn("owner/gpl\tactivity.puml\tcopyleft\tfailed\tactivity_syntax\tblocked_by_license", report)

    def test_render_failure_summary_report_groups_by_license_repo_and_actionability(self) -> None:
        report = render_failure_summary_report(
            [
                record(
                    source_ref="owner/dot",
                    puml_path="dot-1.puml",
                    render_status="failed",
                    render_fail_reason="This looks like a DOT diagram. Please use @startdot instead of @startuml.",
                ),
                record(
                    source_ref="owner/dot",
                    puml_path="dot-2.puml",
                    render_status="failed",
                    render_fail_reason="This looks like a DOT diagram. Please use @startdot instead of @startuml.",
                ),
                record(
                    source_ref="owner/remote",
                    puml_path="remote.puml",
                    render_status="skipped",
                    render_fail_reason="remote_include_blocked",
                ),
                record(
                    source_ref="owner/gpl",
                    puml_path="activity.puml",
                    license_family="copyleft",
                    render_status="failed",
                    render_fail_reason="ERROR 72 Cannot find if (Assumed diagram type: activity)",
                ),
                record(source_ref="owner/ok", puml_path="ok.puml"),
            ]
        )

        self.assertIn(
            "count\tlicense_family\tsource_ref\trender_failed\trender_skipped\tfailure_class",
            report,
        )
        self.assertIn(
            "2\tpermissive\towner/dot\t2\t0\tdot_inside_startuml\tnot_recoverable_as_plantuml",
            report,
        )
        self.assertIn(
            "1\tpermissive\towner/remote\t0\t1\tunsupported_remote_include"
            "\tpotentially_recoverable_with_audited_vendor_includes",
            report,
        )
        self.assertIn(
            "1\tcopyleft\towner/gpl\t1\t0\tactivity_syntax\tblocked_by_license",
            report,
        )
        self.assertNotIn("owner/ok", report)

    def test_classify_render_failure_marks_local_include_gap(self) -> None:
        self.assertEqual(
            (
                "missing_local_include",
                "potentially_recoverable_with_local_include_root",
                "add an auditable local include root only if the dependency is already acquired",
            ),
            classify_render_failure(
                record(
                    render_status="skipped",
                    render_fail_reason="include_resolution_required",
                )
            ),
        )


if __name__ == "__main__":
    unittest.main()
