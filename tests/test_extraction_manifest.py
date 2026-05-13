from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.extraction import classify_diagram_type, extract_from_tree, extract_plantuml_blocks
from plantuml_ai_skill.includes import parse_include_deps, uses_c4
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
        self.assertEqual(["C4_Container.puml"], includes)
        self.assertTrue(uses_c4(includes, c4))

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


if __name__ == "__main__":
    unittest.main()
