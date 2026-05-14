import csv
import json
from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.acquisition import acquire_repo_plantuml_dataset
from plantuml_ai_skill.config import SourceDefinition
from plantuml_ai_skill.manifest import read_jsonl
from plantuml_ai_skill.splits import build_splits


def _repo_dataset_source() -> SourceDefinition:
    return SourceDefinition(
        id="repo-plantuml-dataset",
        name="Repo-PlantUML-Dataset",
        url="https://zenodo.org/records/18764889",
        kind="real_world_corpus",
        priority=2,
        default_purpose=["training"],
        license_policy="mixed: original repo licenses retained; row-level filtering required",
        acquisition_mode="manual_dataset",
        pin_strategy="zenodo_record_version",
        expected_diagram_families=["mixed_plantuml"],
        allowed_split_targets=["training"],
    )


def _write_tiny_dataset(root: Path) -> None:
    repo_docs = root / "data" / "owner__repo" / "docs"
    repo_docs.mkdir(parents=True)
    (repo_docs / "style.puml").write_text("skinparam handwritten true\n", encoding="utf-8")
    (repo_docs / "diagram.puml").write_text(
        "\n".join(
            [
                "@startuml",
                "!include style.puml",
                "Alice -> Bob: hello",
                "@enduml",
            ]
        ),
        encoding="utf-8",
    )
    c4_lib = repo_docs / "c4" / "lib"
    c4_lib.mkdir(parents=True)
    (c4_lib / "C4_Container.puml").write_text("!procedure Container($alias)\n!endprocedure\n", encoding="utf-8")

    with (root / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "repo_name",
                "extension",
                "puml_file_links",
                "language",
                "stargazers_count",
                "forks_count",
                "open_issues_count",
                "watchers_count",
                "created_at",
                "updated_at",
                "size_kb",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "repo_name": "owner/repo",
                "extension": "{'.puml'}",
                "puml_file_links": (
                    "https://raw.githubusercontent.com/owner/repo/main/docs/diagram.puml;"
                    "https://raw.githubusercontent.com/owner/repo/main/docs/style.puml"
                ),
                "language": "Python",
                "stargazers_count": "42",
                "forks_count": "7",
                "open_issues_count": "3",
                "watchers_count": "42",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "size_kb": "123",
            }
        )


class RepoPlantUmlDatasetTests(unittest.TestCase):
    def test_acquire_staged_dataset_enriches_records_and_skips_support_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tiny_dataset(root)
            output = root / "manifest.jsonl"
            records = acquire_repo_plantuml_dataset(
                _repo_dataset_source(),
                root,
                output,
                license_overrides_path=root / "missing-overrides.yml",
            )
            persisted_id = read_jsonl(output)[0].id

        self.assertEqual(1, len(records))
        record = records[0]
        self.assertEqual("data/owner__repo/docs/diagram.puml", record.puml_path)
        self.assertEqual("owner/repo", record.source_ref)
        self.assertEqual("https://github.com/owner/repo", record.source_repo_url)
        self.assertEqual("https://raw.githubusercontent.com/owner/repo/main/docs/diagram.puml", record.source_url)
        self.assertEqual("verify-on-clone", record.license)
        self.assertEqual("unknown", record.license_family)
        self.assertEqual(["style.puml"], record.include_deps)
        self.assertEqual("Python", record.extra["repo_language"])
        self.assertEqual("42", record.extra["repo_stars"])
        self.assertIn("content_sha1", record.extra)
        self.assertEqual(record.id, persisted_id)

    def test_license_override_allows_rendered_dataset_records_into_train(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tiny_dataset(root)
            source = _repo_dataset_source()

            unknown = acquire_repo_plantuml_dataset(
                source,
                root,
                root / "unknown.jsonl",
                license_overrides_path=root / "missing-overrides.yml",
            )
            overrides_path = root / "license-overrides.yml"
            overrides_path.write_text(
                json.dumps(
                    {
                        "repositories": {
                            "owner/repo": {
                                "license": "MIT",
                                "license_path": "LICENSE",
                                "notes": "Reviewed fixture license",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            allowed = acquire_repo_plantuml_dataset(
                source,
                root,
                root / "allowed.jsonl",
                license_overrides_path=overrides_path,
            )

            for record in unknown + allowed:
                record.render_status = "ok"
                record.verification_status = "rendered_no_reference"
            unknown_splits = build_splits(unknown, root / "unknown-splits")
            allowed_splits = build_splits(allowed, root / "allowed-splits")

        self.assertEqual([], unknown_splits["train"])
        self.assertEqual(1, len(allowed_splits["train"]))
        self.assertEqual("MIT", allowed[0].license)
        self.assertEqual("permissive", allowed[0].license_family)
        self.assertEqual("LICENSE", allowed[0].license_path)
        self.assertEqual("Reviewed fixture license", allowed[0].extra["license_override_notes"])


if __name__ == "__main__":
    unittest.main()
