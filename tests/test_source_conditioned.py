from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import (
    python_source_pairing_for_expected_puml,
    python_sources_for_expected_puml,
)


class SourceConditionedTests(unittest.TestCase):
    def test_pairs_same_stem_python_source_with_expected_puml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "case.py").write_text("class Case: pass\n", encoding="utf-8")
            puml = root / "case.puml"
            puml.write_text("@startuml\nclass Case\n@enduml\n", encoding="utf-8")
            self.assertEqual([root / "case.py"], python_sources_for_expected_puml(puml, root))

    def test_falls_back_to_package_python_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            (package / "__init__.py").write_text("", encoding="utf-8")
            (package / "model.py").write_text("class Model: pass\n", encoding="utf-8")
            puml = package / "expected.puml"
            puml.write_text("@startuml\nclass Model\n@enduml\n", encoding="utf-8")
            self.assertEqual([package / "model.py"], python_sources_for_expected_puml(puml, root))

    def test_pairs_fully_qualified_diagram_items_with_source_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "src" / "package"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("class PublicModel: pass\n", encoding="utf-8")
            (package / "model.py").write_text("class Model: pass\n", encoding="utf-8")
            puml = root / "expected.puml"
            puml.write_text(
                "\n".join(
                    [
                        "@startuml",
                        "class package.model.Model",
                        "class package.PublicModel",
                        "@enduml",
                    ]
                ),
                encoding="utf-8",
            )
            pairing = python_source_pairing_for_expected_puml(puml, root)
        self.assertEqual([package / "__init__.py", package / "model.py"], pairing.paths)
        self.assertEqual("high", pairing.confidence)
        self.assertEqual("matched_fully_qualified_diagram_items", pairing.reason)


if __name__ == "__main__":
    unittest.main()
