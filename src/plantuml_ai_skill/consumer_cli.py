"""Consumer-side CLI installed by PlantUML skill packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from plantuml_ai_skill.assets import init_assets, verify_asset, write_asset_metadata
from plantuml_ai_skill.constants import DEFAULT_ASSET_DIR, DEFAULT_JAR_PATH, PLANTUML_JAR_NAME
from plantuml_ai_skill.doctor import run_doctor
from plantuml_ai_skill.improvement.evaluator import evaluate_attempt
from plantuml_ai_skill.improvement.models import SkillAttempt, SkillEvalCase
from plantuml_ai_skill.renderer import PlantUMLRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plantuml-ai")
    parser.add_argument(
        "--agents-root",
        default="",
        help=argparse.SUPPRESS,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate one PlantUML attempt")
    validate.add_argument("attempt", help="Path to a raw Codex response or PlantUML file")
    validate.add_argument("--case-id", default="manual")
    validate.add_argument("--expected-type", default="uml")
    validate.add_argument("--required", action="append", default=[])
    validate.add_argument("--required-edge", action="append", default=[])
    validate.add_argument("--forbidden", action="append", default=["!includeurl", "TODO", "placeholder"])
    validate.add_argument("--include-root", action="append", default=[])
    validate.add_argument("--render", action="store_true")
    validate.add_argument("--render-dir", default="")
    validate.add_argument("--c4", action="store_true")
    validate.add_argument("--jar", default="")
    validate.add_argument("--java", default="")

    render = sub.add_parser("render", help="render PlantUML to SVG or PNG")
    render.add_argument("input", help="Path to a PlantUML file, or '-' for stdin")
    render.add_argument("--format", choices=["svg", "png"], default="svg")
    render.add_argument("--output", required=True)
    render.add_argument("--include-root", action="append", default=[])
    render.add_argument("--c4", action="store_true")
    render.add_argument("--jar", default="")
    render.add_argument("--java", default="")

    doctor = sub.add_parser("doctor", help="check Java, Graphviz, jar, and -testdot")
    doctor.add_argument("--jar", default="")
    doctor.add_argument("--java", default="")
    doctor.add_argument("--json", action="store_true")

    assets = sub.add_parser("init-assets", help="download or install the pinned PlantUML jar")
    assets.add_argument("--asset-dir", default="")
    assets.add_argument("--force", action="store_true")
    assets.add_argument("--offline-jar", default="")

    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("error: plantuml-ai requires Python 3.11 or newer", file=sys.stderr)
        return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    agents_root = Path(args.agents_root).resolve() if args.agents_root else _discover_agents_root()
    try:
        if args.command == "validate":
            return _validate(args, agents_root)
        if args.command == "render":
            return _render(args, agents_root)
        if args.command == "doctor":
            return _doctor(args)
        if args.command == "init-assets":
            return _init_assets(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error("unreachable command")
    return 2


def _validate(args: argparse.Namespace, agents_root: Path) -> int:
    path = Path(args.attempt)
    puml_text = path.read_text(encoding="utf-8", errors="replace")
    include_roots = _include_roots(args.include_root, args.c4, agents_root)
    include_policy = "local_includes_allowed" if include_roots else "self_contained_only"
    renderer = None
    if args.render:
        renderer = PlantUMLRenderer(
            jar_path=args.jar or DEFAULT_JAR_PATH,
            java_bin=args.java or None,
            include_roots=include_roots,
        )
    case = SkillEvalCase(
        id=args.case_id,
        suite="manual",
        prompt="Manual validation",
        expected_diagram_type=args.expected_type,
        required_patterns=list(args.required),
        forbidden_patterns=list(args.forbidden),
        required_edges=_required_edges(args.required_edge),
        include_policy=include_policy,
        purpose=["manual"],
        difficulty="manual",
        tags=["manual"],
    )
    attempt = SkillAttempt(
        id=f"manual-{args.case_id}",
        run_id="manual",
        skill_version_id="manual",
        case_id=args.case_id,
        model_or_agent="manual",
        created_at="manual",
        raw_response_path=str(path),
        puml_text=puml_text,
    )
    result = evaluate_attempt(
        case,
        attempt,
        renderer=renderer,
        render_dir=Path(args.render_dir) if args.render_dir else None,
        include_roots=include_roots,
    )
    print(f"score={result.score:.3f}")
    print(f"render_status={result.render_status}")
    for failure in result.failures:
        print(f"{failure.code}: {failure.message}")
    if result.render_status == "skipped":
        print("note=Render validation was skipped.")
    return 0 if not result.failures else 1


def _render(args: argparse.Namespace, agents_root: Path) -> int:
    puml_text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8")
    renderer = PlantUMLRenderer(
        jar_path=args.jar or DEFAULT_JAR_PATH,
        java_bin=args.java or None,
        include_roots=_include_roots(args.include_root, args.c4, agents_root),
    )
    result = renderer.render_png(puml_text) if args.format == "png" else renderer.render_svg(puml_text)
    if not result.ok:
        print(result.stderr or f"PlantUML returned {result.returncode}", file=sys.stderr)
        return 1
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(result.output)
    print(f"Wrote {args.format}: {output}")
    return 0


def _doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(args.jar or DEFAULT_JAR_PATH, java_bin=args.java or None)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        for check in checks:
            status = "ok" if check.ok else "fail"
            print(f"[{status}] {check.name}: {check.message}")
            if check.details:
                print(f"  {check.details}")
    return 0 if all(check.ok for check in checks) else 1


def _init_assets(args: argparse.Namespace) -> int:
    asset_dir = Path(args.asset_dir) if args.asset_dir else DEFAULT_ASSET_DIR
    asset_dir.mkdir(parents=True, exist_ok=True)
    if args.offline_jar:
        source = Path(args.offline_jar)
        target = asset_dir / PLANTUML_JAR_NAME
        if target.exists() and not args.force:
            verify_asset(target)
            write_asset_metadata(asset_dir, target)
            print(f"PlantUML jar ready: {target}")
            return 0
        shutil.copyfile(source, target)
        verify_asset(target)
        write_asset_metadata(asset_dir, target)
        print(f"PlantUML jar ready: {target}")
        return 0
    jar = init_assets(asset_dir, force=args.force)
    print(f"PlantUML jar ready: {jar}")
    return 0


def _include_roots(values: list[str], c4: bool, agents_root: Path) -> list[Path]:
    roots = [Path(value) for value in values]
    if c4:
        roots.append(agents_root / "vendor" / "c4-plantuml")
    return roots


def _required_edges(values: list[str]) -> list[tuple[str, str]]:
    edges: list[tuple[str, str]] = []
    for value in values:
        if "->" not in value:
            raise ValueError(f"--required-edge must use A->B syntax: {value!r}")
        left, right = value.split("->", 1)
        left = left.strip()
        right = right.strip()
        if not left or not right:
            raise ValueError(f"--required-edge must include both endpoints: {value!r}")
        edges.append((left, right))
    return edges


def _discover_agents_root() -> Path:
    for parent in [Path.cwd(), *Path.cwd().parents]:
        candidate = parent / ".agents"
        if candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / ".agents").resolve()


if __name__ == "__main__":
    raise SystemExit(main())
