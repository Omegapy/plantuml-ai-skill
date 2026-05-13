from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import copy_vendor_include_files


class VendorIncludesTests(unittest.TestCase):
    def test_copy_vendor_include_files_preserves_include_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged = root / "staged"
            vendor = root / "vendor"
            (staged / "themes").mkdir(parents=True)
            (staged / ".git").mkdir()
            (staged / "C4_Container.puml").write_text("' include\n", encoding="utf-8")
            (staged / "themes" / "theme.iuml").write_text("' theme\n", encoding="utf-8")
            (staged / ".git" / "ignored.puml").write_text("' ignored\n", encoding="utf-8")

            copied = copy_vendor_include_files(staged, vendor)

            self.assertEqual(
                ["C4_Container.puml", "themes/theme.iuml"],
                sorted(path.relative_to(vendor).as_posix() for path in copied),
            )
            self.assertTrue((vendor / "C4_Container.puml").exists())
            self.assertFalse((vendor / ".git" / "ignored.puml").exists())


if __name__ == "__main__":
    unittest.main()
