from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.improvement.skill_builder import (
    REQUIRED_DIAGRAM_REFERENCES,
    SkillBuildConfig,
    build_skill_package,
    lint_skill_package,
    skill_hash,
)


class SkillBuilderTests(unittest.TestCase):
    def test_builds_valid_skill_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "plantuml-diagram"
            version = build_skill_package(SkillBuildConfig(output_dir=output))
            skill_md = output / "SKILL.md"
            self.assertTrue(skill_md.exists())
            text = skill_md.read_text(encoding="utf-8")
            self.assertIn("name: plantuml-diagram", text)
            self.assertIn("Output Contract", text)
            self.assertIn("Include Policy", text)
            self.assertIn("diagram-family-playbook.md", text)
            self.assertIn("palette-contract.md", text)
            self.assertTrue((output / "references" / "palette-contract.md").exists())
            self.assertEqual(version.skill_sha256, skill_hash(skill_md))
            self.assertEqual([], lint_skill_package(output, REQUIRED_DIAGRAM_REFERENCES))

    def test_rebuild_with_same_inputs_produces_same_skill_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "skill"
            build_skill_package(SkillBuildConfig(output_dir=output))
            first = skill_hash(output / "SKILL.md")
            build_skill_package(SkillBuildConfig(output_dir=output))
            second = skill_hash(output / "SKILL.md")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
