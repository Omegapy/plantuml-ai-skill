from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import python_sources_for_expected_puml


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


if __name__ == "__main__":
    unittest.main()
