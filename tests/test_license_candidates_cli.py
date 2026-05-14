from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.cli import main
from plantuml_ai_skill.manifest import CorpusRecord, write_jsonl


def record(**overrides: object) -> CorpusRecord:
    payload = {
        "id": "record-1",
        "source_name": "repo-plantuml-dataset",
        "source_url": "https://example.test/source",
        "source_kind": "git_repository",
        "source_ref": "owner/repo",
        "license": "verify-on-clone",
        "license_family": "unknown",
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
        "render_hash_svg": "",
        "render_hash_png": "",
        "verification_status": "rendered_no_reference",
        "render_fail_reason": "",
        "purpose": ["training"],
        "attribution": "source",
        "license_path": "",
        "source_commit": "commit",
        "source_repo_url": "https://example.test/source",
    }
    payload.update(overrides)
    return CorpusRecord(**payload)


class LicenseCandidatesCliTests(unittest.TestCase):
    def test_license_candidates_annotates_reviewed_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.jsonl"
            blocklist = root / "license-blocklist.yml"
            write_jsonl(
                [
                    record(id="blocked-ok", source_ref="owner/blocked", render_status="ok"),
                    record(id="blocked-failed", source_ref="owner/blocked", render_status="failed"),
                    record(id="safe", source_ref="owner/safe", license="MIT", license_family="permissive"),
                ],
                manifest,
            )
            blocklist.write_text(
                json.dumps(
                    {
                        "repositories": {
                            "owner/blocked": {
                                "license": "GPL-3.0",
                                "license_family": "copyleft",
                                "license_path": "LICENSE",
                                "notes": "Reviewed upstream license",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            output = StringIO()
            with redirect_stdout(output):
                result = main(
                    [
                        "license-candidates",
                        "--manifest",
                        str(manifest),
                        "--blocklist",
                        str(blocklist),
                    ]
                )

        self.assertEqual(0, result)
        self.assertIn("count\tsource_ref\trender_ok\trender_failed", output.getvalue())
        self.assertIn(
            "2\towner/blocked\t1\t1\t0\tyes\tGPL-3.0\tcopyleft\tLICENSE\tReviewed upstream license",
            output.getvalue(),
        )
        self.assertNotIn("owner/safe", output.getvalue())

    def test_render_failure_summary_cli_groups_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.jsonl"
            write_jsonl(
                [
                    record(
                        id="dot-1",
                        source_ref="owner/dot",
                        license="MIT",
                        license_family="permissive",
                        render_status="failed",
                        render_fail_reason=(
                            "This looks like a DOT diagram. Please use @startdot instead of @startuml."
                        ),
                    ),
                    record(
                        id="dot-2",
                        source_ref="owner/dot",
                        license="MIT",
                        license_family="permissive",
                        render_status="failed",
                        render_fail_reason=(
                            "This looks like a DOT diagram. Please use @startdot instead of @startuml."
                        ),
                    ),
                    record(
                        id="blocked",
                        source_ref="owner/gpl",
                        license="GPL-3.0",
                        license_family="copyleft",
                        render_status="failed",
                        render_fail_reason="ERROR 72 Cannot find if (Assumed diagram type: activity)",
                    ),
                    record(
                        id="ok",
                        source_ref="owner/ok",
                        license="MIT",
                        license_family="permissive",
                    ),
                ],
                manifest,
            )

            output = StringIO()
            with redirect_stdout(output):
                result = main(["render-failure-summary", "--manifest", str(manifest)])

        self.assertEqual(0, result)
        self.assertIn(
            "2\tpermissive\towner/dot\t2\t0\tdot_inside_startuml\tnot_recoverable_as_plantuml",
            output.getvalue(),
        )
        self.assertIn("1\tcopyleft\towner/gpl\t1\t0\tactivity_syntax\tblocked_by_license", output.getvalue())
        self.assertNotIn("owner/ok", output.getvalue())


if __name__ == "__main__":
    unittest.main()
