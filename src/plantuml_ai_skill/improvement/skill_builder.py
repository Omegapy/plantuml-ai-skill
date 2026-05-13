"""Build and lint Codex skill packages for PlantUML diagram authoring."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
from pathlib import Path
from typing import Iterable

from plantuml_ai_skill.manifest import CorpusRecord, read_jsonl as read_manifest_jsonl

from .models import SkillVersion, write_json
from .state import AUTHOR_SKILL_DIR, PROJECT_ROOT, git_commit, relative_to_project, utc_now


BUILDER_VERSION = "0.1.0"
REQUIRED_AUTHOR_REFERENCES = {
    "diagram-family-playbook.md",
    "include-policy.md",
    "output-contract.md",
    "examples.md",
}
REQUIRED_IMPROVER_REFERENCES = {
    "improvement-loop-protocol.md",
    "scoring-rubric.md",
    "codex-handoff-template.md",
}


@dataclass(frozen=True)
class SkillBuildConfig:
    output_dir: Path = AUTHOR_SKILL_DIR
    manifest_paths: list[Path] = field(default_factory=list)
    lessons_path: Path | None = None
    max_examples: int = 6
    notes: str = "Generated PlantUML diagram author skill"


@dataclass(frozen=True)
class SkillBuildContext:
    examples: list[CorpusRecord]
    lessons: list[str]


def build_skill_package(config: SkillBuildConfig) -> SkillVersion:
    """Build the target Codex skill package and write its version metadata."""

    output_dir = Path(config.output_dir)
    references_dir = output_dir / "references"
    scripts_dir = output_dir / "scripts"
    references_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    context = SkillBuildContext(
        examples=_select_manifest_examples(config.manifest_paths, config.max_examples),
        lessons=_read_lessons(config.lessons_path),
    )
    skill_md = render_skill_markdown(context)
    (output_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    _write_author_references(references_dir, context)
    script_path = scripts_dir / "validate_plantuml_attempt.py"
    if not script_path.exists():
        script_path.write_text(_validation_script_text(), encoding="utf-8")

    version = SkillVersion(
        id=_skill_version_id(),
        created_at=utc_now(),
        git_commit=git_commit(),
        skill_path=relative_to_project(output_dir / "SKILL.md"),
        skill_sha256=skill_hash(output_dir / "SKILL.md"),
        builder_version=BUILDER_VERSION,
        source_manifests=[relative_to_project(path) for path in config.manifest_paths],
        notes=config.notes,
    )
    write_json(version, output_dir / "skill-version.json")
    return version


def render_skill_markdown(context: SkillBuildContext) -> str:
    lessons = "\n".join(f"- {lesson}" for lesson in context.lessons) or "- Keep diagrams self-contained and renderable."
    example_lines = _example_summary_lines(context.examples)
    examples = "\n".join(example_lines) or "- See `references/examples.md` for hand-authored examples."
    return "\n".join(
        [
            "---",
            "name: plantuml-diagram-author",
            "description: Generate, validate, and repair PlantUML diagrams from natural-language requests. Use for sequence, class, activity, state, use case, component, deployment, C4, mindmap, gantt, and other PlantUML diagram tasks.",
            "---",
            "",
            "# PlantUML Diagram Author",
            "",
            "## When To Use",
            "",
            "Use this skill for PlantUML generation, repair, validation, and diagram-family selection.",
            "",
            "## Output Contract",
            "",
            "- Emit exactly one complete PlantUML document unless the user explicitly asks for multiple diagrams.",
            "- Include a matching `@start...` and `@end...` pair.",
            "- Preserve required actors, systems, relationships, labels, constraints, and requested style.",
            "- Avoid TODOs, placeholders, prose-only answers, and arbitrary remote includes.",
            "",
            "Read `references/output-contract.md` when strict formatting matters.",
            "",
            "## Generation Workflow",
            "",
            "1. Choose the diagram family from intent, using `references/diagram-family-playbook.md` when needed.",
            "2. Draft self-contained PlantUML first.",
            "3. Add participants/entities before relationships.",
            "4. Label important edges and outcomes.",
            "5. For lifecycle requests, use explicit state syntax such as `state` declarations or `[*]` transitions.",
            "6. Validate locally with the bundled script or `plantuml-skill improve evaluate` when a run exists.",
            "",
            "## Include Policy",
            "",
            "Prefer no includes. Read `references/include-policy.md` before adding local/vendored includes. Never use arbitrary `!includeurl`. For C4 in this repo, use vendored includes instead of inline macro shims.",
            "",
            "## Current Lessons Learned",
            "",
            lessons,
            "",
            "## Selected Example Signals",
            "",
            examples,
            "",
            "## References",
            "",
            "- `references/diagram-family-playbook.md`",
            "- `references/include-policy.md`",
            "- `references/output-contract.md`",
            "- `references/examples.md`",
            "",
        ]
    )


def skill_hash(path: Path | str) -> str:
    digest = hashlib.sha256()
    digest.update(Path(path).read_bytes())
    return digest.hexdigest()


def lint_skill_package(path: Path | str, required_references: Iterable[str] | None = None) -> list[str]:
    """Return lint errors for a Codex skill package."""

    skill_dir = Path(path)
    skill_md = skill_dir / "SKILL.md"
    errors: list[str] = []
    if not skill_md.exists():
        return [f"missing SKILL.md: {skill_md}"]
    text = skill_md.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    if not frontmatter:
        errors.append("missing YAML frontmatter")
    else:
        if not frontmatter.get("name"):
            errors.append("frontmatter missing name")
        description = frontmatter.get("description", "")
        if not description:
            errors.append("frontmatter missing description")
        elif len(description.split()) > 45:
            errors.append("description should be concise")
    for name in required_references or []:
        if not (skill_dir / "references" / name).exists():
            errors.append(f"missing reference: {name}")
    for script in (skill_dir / "scripts").glob("*.py") if (skill_dir / "scripts").exists() else []:
        if not script.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3"):
            errors.append(f"script missing python shebang: {script.name}")
    return errors


def _select_manifest_examples(paths: list[Path], max_examples: int) -> list[CorpusRecord]:
    records: list[CorpusRecord] = []
    for path in paths:
        if Path(path).exists():
            records.extend(read_manifest_jsonl(path))
    selected: list[CorpusRecord] = []
    seen_types: set[str] = set()
    for record in sorted(records, key=lambda item: (item.diagram_type, item.id)):
        if record.diagram_type in seen_types:
            continue
        if record.render_status not in {"", "ok", "not_rendered"}:
            continue
        selected.append(record)
        seen_types.add(record.diagram_type)
        if len(selected) >= max_examples:
            break
    return selected


def _read_lessons(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    lessons: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped:
            lessons.append(stripped)
    return lessons


def _write_author_references(references_dir: Path, context: SkillBuildContext) -> None:
    files = {
        "diagram-family-playbook.md": _diagram_family_reference(),
        "include-policy.md": _include_policy_reference(),
        "output-contract.md": _output_contract_reference(),
        "examples.md": _examples_reference(context.examples),
    }
    for name, text in files.items():
        (references_dir / name).write_text(text, encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"(?s)^---\n(?P<body>.*?)\n---", text)
    if not match:
        return {}
    values: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _skill_version_id() -> str:
    stamp = utc_now().replace(":", "").replace("-", "").replace("Z", "")
    return f"skill-{stamp}"


def _example_summary_lines(records: list[CorpusRecord]) -> list[str]:
    return [
        f"- `{record.diagram_type}` example from `{record.id}`; include-safe={record.is_self_contained}."
        for record in records
    ]


def _diagram_family_reference() -> str:
    return """# Diagram Family Playbook

- Sequence: time-ordered calls, responses, callbacks, retries, errors.
- Class: static types, fields, methods, inheritance, aggregation, composition.
- Activity: workflows, branching, approvals, process steps.
- State: lifecycle states and event-driven transitions; use explicit state declarations or `[*]` transitions.
- Use case: actors and goals around a system boundary.
- Component: modules, services, databases, dependencies.
- Deployment: nodes, runtimes, infrastructure placement.
- C4: architecture context/container/component views; use vendored C4 includes, not hand-written macro shims.
"""


def _include_policy_reference() -> str:
    return """# Include Policy

Prefer self-contained PlantUML.

Allowed includes must be local, vendored, and auditable. Block arbitrary HTTP/HTTPS `!includeurl` usage. Use C4 includes only when C4 notation is requested or clearly needed. In this repo, prefer `!include C4_Container.puml` for C4 container views and do not redefine C4 macros inline.
"""


def _output_contract_reference() -> str:
    return """# Output Contract

Return exactly one complete PlantUML document for a single-diagram request. The document must include matching start/end directives, satisfy named entities and relationships, and avoid TODOs/placeholders.
"""


def _examples_reference(records: list[CorpusRecord]) -> str:
    static = """# Examples

```plantuml
@startuml
actor Client
participant API
database Database
Client -> API: request
API -> Database: query
Database --> API: timeout
API --> Client: error response
@enduml
```

```plantuml
@startuml
!include C4_Container.puml
Person(user, "User")
System_Boundary(system, "Diagram Service") {
  Container(api, "API", "Python/FastAPI")
}
Rel(user, api, "Uses")
@enduml
```
"""
    if not records:
        return static
    lines = [static, "\n## Manifest-Derived Signals\n"]
    lines.extend(_example_summary_lines(records))
    lines.append("")
    return "\n".join(lines)


def _validation_script_text() -> str:
    script = PROJECT_ROOT / ".agents" / "skills" / "plantuml-diagram-author" / "scripts" / "validate_plantuml_attempt.py"
    if script.exists():
        return script.read_text(encoding="utf-8")
    return "#!/usr/bin/env python3\nprint('Run plantuml-skill improve evaluate for validation.')\n"
