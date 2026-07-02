import unittest

from plantuml_ai_skill.improvement.palette import (
    AETHER_DARK_BASE_STYLE_BLOCK,
    AETHER_DARK_C4_STYLE_BLOCK,
    PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED,
    PALETTE_POLICY_AETHER_DARK_REQUIRED,
    aether_dark_style_block,
    contrast_ratio,
    palette_policy_for_diagram_type,
)


class PaletteContractTests(unittest.TestCase):
    def test_certified_family_uses_rendered_required_policy(self) -> None:
        self.assertEqual(PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED, palette_policy_for_diagram_type("sequence"))
        self.assertEqual(PALETTE_POLICY_AETHER_DARK_RENDERED_REQUIRED, palette_policy_for_diagram_type("c4"))

    def test_uncertified_family_uses_source_policy_and_base_block_only(self) -> None:
        self.assertEqual(PALETTE_POLICY_AETHER_DARK_REQUIRED, palette_policy_for_diagram_type("mindmap"))
        self.assertEqual(AETHER_DARK_BASE_STYLE_BLOCK, aether_dark_style_block("mindmap"))
        self.assertEqual(AETHER_DARK_BASE_STYLE_BLOCK, aether_dark_style_block("gantt"))

    def test_unknown_family_rejected_by_style_helper(self) -> None:
        with self.assertRaises(ValueError):
            aether_dark_style_block("wireframe")

    def test_cyan_actor_fill_uses_high_contrast_outline(self) -> None:
        self.assertIn("skinparam ActorBackgroundColor #0f364d", AETHER_DARK_BASE_STYLE_BLOCK)
        self.assertIn("skinparam ActorBorderColor #d6c3b4", AETHER_DARK_BASE_STYLE_BLOCK)
        self.assertNotIn("skinparam ActorBorderColor #48a0c0", AETHER_DARK_BASE_STYLE_BLOCK)
        self.assertIn(
            'UpdateElementStyle("person", $bgColor="#0f364d", $fontColor="#fff8ef", $borderColor="#d6c3b4")',
            AETHER_DARK_C4_STYLE_BLOCK,
        )
        self.assertGreaterEqual(contrast_ratio("#d6c3b4", "#0f364d"), 7.0)


if __name__ == "__main__":
    unittest.main()
