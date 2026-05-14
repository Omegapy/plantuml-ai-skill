from pathlib import Path
import os
import tempfile
import textwrap
import unittest

from plantuml_ai_skill.cli import main
from plantuml_ai_skill.doctor import parse_java_major
from plantuml_ai_skill.manifest import CorpusRecord, read_jsonl, write_jsonl
from plantuml_ai_skill.renderer import PlantUMLRenderer


ROOT = Path(__file__).resolve().parents[1]


class RendererDoctorCliTests(unittest.TestCase):
    def test_parse_java_major(self) -> None:
        self.assertEqual(17, parse_java_major('openjdk version "17.0.12" 2024-07-16'))
        self.assertEqual(8, parse_java_major('java version "1.8.0_401"'))

    def test_renderer_invokes_java_jar_pipe_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            fake_jar.write_text("fake", encoding="utf-8")
            fake_java.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    case "$*" in
                      *-testdot*) echo "dot ok"; exit 0 ;;
                      *-tsvg*) echo '<svg xmlns="http://www.w3.org/2000/svg"><text>Alice</text></svg>'; exit 0 ;;
                      *) echo "unexpected args: $*" >&2; exit 2 ;;
                    esac
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_java, 0o755)
            renderer = PlantUMLRenderer(jar_path=fake_jar, java_bin=str(fake_java))
            result = renderer.render_svg("@startuml\nAlice -> Bob: hi\n@enduml")
            self.assertTrue(result.ok, result.stderr)
            self.assertIn("-pipe", result.command)
            self.assertIn("-DPLANTUML_SECURITY_PROFILE=SANDBOX", result.command)
            self.assertTrue(renderer.testdot().ok)

    def test_renderer_strips_svg_pipe_status_chatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            fake_jar.write_text("fake", encoding="utf-8")
            fake_java.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    echo 'RUNNING net.sourceforge.plantuml.project.lang.Sentence'
                    echo '<svg xmlns="http://www.w3.org/2000/svg"><text>Gantt</text></svg>'
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_java, 0o755)
            renderer = PlantUMLRenderer(jar_path=fake_jar, java_bin=str(fake_java))
            result = renderer.render_svg("@startgantt\n@endgantt")
        self.assertTrue(result.output.startswith(b"<svg"))

    def test_renderer_strips_png_pipe_status_chatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            fake_jar.write_text("fake", encoding="utf-8")
            fake_java.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    printf 'RUNNING status\\n\\211PNG\\r\\n\\032\\nrest'
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_java, 0o755)
            renderer = PlantUMLRenderer(jar_path=fake_jar, java_bin=str(fake_java))
            result = renderer.render_png("@startgantt\n@endgantt")
        self.assertTrue(result.output.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_renderer_includes_vendored_include_path_property(self) -> None:
        renderer = PlantUMLRenderer(
            jar_path=Path("plantuml.jar"),
            java_bin="/tmp/java",
            include_roots=[Path("/tmp/vendor/c4"), Path("/tmp/vendor/stdlib")],
        )
        command = renderer.command_for("-tsvg")
        self.assertIn("-Dplantuml.include.path=/tmp/vendor/c4:/tmp/vendor/stdlib", command)

    def test_renderer_batch_uses_file_contract_without_pipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            puml_path = tmp_path / "one.puml"
            output_dir = tmp_path / "out"
            fake_jar.write_text("fake", encoding="utf-8")
            puml_path.write_text("@startuml\nAlice -> Bob: hi\n@enduml\n", encoding="utf-8")
            fake_java.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            os.chmod(fake_java, 0o755)
            renderer = PlantUMLRenderer(jar_path=fake_jar, java_bin=str(fake_java))
            result = renderer.render_batch([puml_path], "-tsvg", output_dir)
        self.assertTrue(result.ok, result.stderr)
        self.assertNotIn("-pipe", result.command)
        self.assertIn("-o", result.command)
        self.assertIn(str(output_dir), result.command)

    def test_cli_render_batch_preserves_row_statuses_and_record_id_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source"
            rendered = tmp_path / "rendered"
            source.mkdir()
            (source / "first.puml").write_text("@startuml\nAlice -> Bob: hi\n@enduml\n", encoding="utf-8")
            (source / "second.puml").write_text("@startuml\nBob -> Alice: ok\n@enduml\n", encoding="utf-8")
            fake_java = tmp_path / "java"
            fake_jar = tmp_path / "plantuml.jar"
            fake_jar.write_text("fake", encoding="utf-8")
            fake_java.write_text(
                textwrap.dedent(
                    """\
                    #!/bin/sh
                    out=""
                    ext=""
                    while [ "$#" -gt 0 ]; do
                      case "$1" in
                        -o) out="$2"; shift 2 ;;
                        -tsvg) ext="svg"; shift ;;
                        -tpng) ext="png"; shift ;;
                        *.puml)
                          base=$(basename "$1" .puml)
                          mkdir -p "$out"
                          if [ "$ext" = "svg" ]; then
                            printf '<svg xmlns="http://www.w3.org/2000/svg"><text>%s</text></svg>' "$base" > "$out/$base.svg"
                          else
                            printf 'not-png' > "$out/$base.png"
                          fi
                          shift
                          ;;
                        *) shift ;;
                      esac
                    done
                    exit 0
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_java, 0o755)
            manifest = tmp_path / "manifest.jsonl"
            output = tmp_path / "rendered.jsonl"
            records = [
                _local_record("record-one", "first.puml", source),
                _local_record("record-two", "second.puml", source),
            ]
            write_jsonl(records, manifest)

            status = main(
                [
                    "render",
                    "--manifest",
                    str(manifest),
                    "--source-root",
                    str(source),
                    "--output",
                    str(output),
                    "--render-dir",
                    str(rendered),
                    "--java",
                    str(fake_java),
                    "--jar",
                    str(fake_jar),
                    "--batch-size",
                    "2",
                ]
            )
            updated = read_jsonl(output)
            first_svg_exists = (rendered / "record-one.svg").exists()
            second_svg_exists = (rendered / "record-two.svg").exists()
            first_svg_path = str(rendered / "record-one.svg")

        self.assertEqual(0, status)
        self.assertEqual(["ok", "ok"], [record.render_status for record in updated])
        self.assertTrue(first_svg_exists)
        self.assertTrue(second_svg_exists)
        self.assertEqual(first_svg_path, updated[0].extra["rendered_svg_path"])

    def test_cli_coverage_and_fixture_acquire(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fixtures.jsonl"
            self.assertEqual(0, main(["coverage"]))
            self.assertEqual(0, main(["acquire", "--source", "fixtures", "--output", str(output)]))
            self.assertTrue(output.exists())


def _local_record(record_id: str, puml_path: str, source: Path) -> CorpusRecord:
    return CorpusRecord(
        id=record_id,
        source_name="local",
        source_url=str(source),
        source_kind="local",
        source_ref="local",
        license="MIT",
        license_family="permissive",
        diagram_type="sequence",
        puml_path=puml_path,
        published_render_path="",
        python_source_paths=[],
        include_deps=[],
        is_self_contained=True,
        uses_include=False,
        uses_icon_library=False,
        plantuml_version="",
        graphviz_version="",
        render_status="not_rendered",
        render_hash_svg="",
        render_hash_png="",
        verification_status="not_verified",
        render_fail_reason="",
        purpose=["gold_eval"],
        attribution="local",
        license_path="",
        source_commit="local",
        source_repo_url=str(source),
    )


if __name__ == "__main__":
    unittest.main()
