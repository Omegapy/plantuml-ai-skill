from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.extraction import classify_diagram_type, extract_from_tree, extract_plantuml_blocks
from plantuml_ai_skill.includes import (
    parse_include_deps,
    inline_resolved_includes,
    resolve_include_deps,
    rewrite_includes_to_local_paths,
    unresolved_include_reason,
    uses_c4,
)
from plantuml_ai_skill.manifest import read_jsonl


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class ExtractionManifestTests(unittest.TestCase):
    def test_extracts_raw_and_markdown_blocks(self) -> None:
        diagrams = extract_from_tree(FIXTURES / "plantuml", source_name="fixtures")
        diagram_names = {diagram.path.name for diagram in diagrams}
        self.assertIn("sequence.puml", diagram_names)
        self.assertIn("markdown_example.md", diagram_names)
        self.assertGreaterEqual(len(diagrams), 4)

    def test_classifies_representative_diagrams(self) -> None:
        sequence = (FIXTURES / "plantuml" / "sequence.puml").read_text()
        c4 = (FIXTURES / "plantuml" / "c4_container.puml").read_text()
        class_diagram = (FIXTURES / "plantuml" / "class_graphviz.puml").read_text()
        self.assertEqual("sequence", classify_diagram_type(sequence))
        self.assertEqual("c4", classify_diagram_type(c4))
        self.assertEqual("class", classify_diagram_type(class_diagram))

    def test_include_parsing_marks_c4_dependency(self) -> None:
        c4 = (FIXTURES / "plantuml" / "c4_container.puml").read_text()
        includes = parse_include_deps(c4)
        self.assertEqual(["c4_fixture_container_include.puml"], includes)
        self.assertTrue(uses_c4(includes, c4))

    def test_include_resolution_uses_vendored_roots_and_blocks_remote_includes(self) -> None:
        resolutions = resolve_include_deps(
            ["c4_fixture_container_include.puml"],
            [FIXTURES / "vendor" / "c4"],
        )
        self.assertTrue(resolutions[0].resolved_path)
        self.assertEqual(
            "",
            unresolved_include_reason(["c4_fixture_container_include.puml"], [FIXTURES / "vendor" / "c4"]),
        )
        self.assertEqual(
            "remote_include_blocked",
            unresolved_include_reason(["https://example.com/remote.puml"], [FIXTURES / "vendor" / "c4"]),
        )

    def test_include_rewrite_uses_absolute_local_paths(self) -> None:
        resolutions = resolve_include_deps(["c4_fixture_container_include.puml"], [FIXTURES / "vendor" / "c4"])
        rewritten = rewrite_includes_to_local_paths(
            "!include c4_fixture_container_include.puml\n@startuml\n@enduml\n",
            resolutions,
        )
        self.assertIn(
            (FIXTURES / "vendor" / "c4" / "c4_fixture_container_include.puml").as_posix(),
            rewritten,
        )

    def test_include_inlining_embeds_vendor_content_for_sandboxed_rendering(self) -> None:
        resolutions = resolve_include_deps(["c4_fixture_container_include.puml"], [FIXTURES / "vendor" / "c4"])
        inlined = inline_resolved_includes(
            "!include c4_fixture_container_include.puml\n@startuml\n@enduml\n",
            resolutions,
        )
        self.assertIn("begin inlined include: c4_fixture_container_include.puml", inlined)
        self.assertIn("!procedure Container", inlined)
        self.assertNotIn("!include c4_fixture_container_include.puml", inlined)

    def test_markdown_fenced_block_fallback(self) -> None:
        text = "```plantuml\n@startuml\nAlice -> Bob: hi\n@enduml\n```"
        self.assertEqual(1, len(extract_plantuml_blocks(text)))

    def test_acquire_fixtures_writes_valid_jsonl_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fixtures.jsonl"
            records = acquire_fixtures(FIXTURES, output)
            loaded = read_jsonl(output)
        self.assertEqual(len(records), len(loaded))
        self.assertTrue(any(record.python_source_paths for record in loaded))
        self.assertTrue(any("renderer_regression" in record.purpose for record in loaded))
        self.assertTrue(all(record.attribution for record in loaded))
        self.assertTrue(all(record.source_repo_url for record in loaded))
        self.assertTrue(all("block_index" in record.extra for record in loaded if not record.python_source_paths))


if __name__ == "__main__":
    unittest.main()
