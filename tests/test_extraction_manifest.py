from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_fixtures
from plantuml_ai_skill.extraction import (
    classify_diagram_type,
    extract_from_file,
    extract_from_tree,
    extract_plantuml_blocks,
)
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

    def test_include_inlining_embeds_nested_local_includes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested.puml").write_text("' nested content\n", encoding="utf-8")
            (root / "outer.puml").write_text(
                "!include ./nested.puml\n!include https://example.test/remote.puml\n",
                encoding="utf-8",
            )
            resolutions = resolve_include_deps(["outer.puml"], [root])
            inlined = inline_resolved_includes("@startuml\n!include outer.puml\n@enduml\n", resolutions)
        self.assertIn("begin inlined include: ./nested.puml", inlined)
        self.assertIn("' nested content", inlined)
        self.assertIn("!include https://example.test/remote.puml", inlined)

    def test_markdown_fenced_block_fallback(self) -> None:
        text = "```plantuml\n@startuml\nAlice -> Bob: hi\n@enduml\n```"
        self.assertEqual(1, len(extract_plantuml_blocks(text)))

    def test_markdown_pairing_uses_adjacent_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "first.png").write_bytes(b"png")
            (root / "second.png").write_bytes(b"png")
            markdown = root / "examples.md"
            markdown.write_text(
                "\n".join(
                    [
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: first",
                        "@enduml",
                        "```",
                        "![first](first.png)",
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: second",
                        "@enduml",
                        "```",
                        "![second](second.png)",
                    ]
                ),
                encoding="utf-8",
            )
            diagrams = extract_from_file(markdown, "test")
        self.assertEqual(["first.png", "second.png"], [item.published_render_path.name for item in diagrams])
        self.assertEqual(
            ["markdown_adjacent_after", "markdown_adjacent_after"],
            [item.published_render_pairing_status for item in diagrams],
        )

    def test_markdown_pairing_does_not_duplicate_one_image_across_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "only.png").write_bytes(b"png")
            markdown = root / "examples.md"
            markdown.write_text(
                "\n".join(
                    [
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: first",
                        "@enduml",
                        "```",
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: second",
                        "@enduml",
                        "```",
                        "![only](only.png)",
                    ]
                ),
                encoding="utf-8",
            )
            diagrams = extract_from_file(markdown, "test")
        self.assertEqual("", diagrams[0].published_render_pairing_status)
        self.assertIsNone(diagrams[0].published_render_path)
        self.assertEqual("only.png", diagrams[1].published_render_path.name)

    def test_markdown_pairing_leaves_multiblock_without_images_unreferenced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            markdown = root / "examples.md"
            markdown.write_text(
                "\n".join(
                    [
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: first",
                        "@enduml",
                        "```",
                        "```plantuml",
                        "@startuml",
                        "Alice -> Bob: second",
                        "@enduml",
                        "```",
                    ]
                ),
                encoding="utf-8",
            )
            diagrams = extract_from_file(markdown, "test")
        self.assertEqual([None, None], [item.published_render_path for item in diagrams])

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
