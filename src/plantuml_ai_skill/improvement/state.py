"""Persistent paths and run state helpers for improvement runs."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess

from plantuml_ai_skill.constants import PROJECT_ROOT

from .models import ImprovementRun, read_json, write_json


IMPROVEMENT_ROOT = PROJECT_ROOT / "data" / "improvement"
RUNS_ROOT = IMPROVEMENT_ROOT / "runs"
SUITES_ROOT = IMPROVEMENT_ROOT / "suites"
APPROVALS_ROOT = IMPROVEMENT_ROOT / "approvals"
INDEX_PATH = IMPROVEMENT_ROOT / "index.json"
DIAGRAM_SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "plantuml-diagram"
IMPROVER_SKILL_DIR = PROJECT_ROOT / ".agents" / "skills" / "plantuml-skill-improver"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return "unknown"
    return proc.stdout.strip() or "unknown"


def ensure_improvement_dirs(root: Path = IMPROVEMENT_ROOT) -> None:
    for path in (root, root / "runs", root / "suites", root / "approvals"):
        path.mkdir(parents=True, exist_ok=True)


def load_index(root: Path = IMPROVEMENT_ROOT) -> dict[str, str]:
    path = root / "index.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_index(index: dict[str, str], root: Path = IMPROVEMENT_ROOT) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "index.json"
    path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def update_latest_run(run_id: str, root: Path = IMPROVEMENT_ROOT) -> None:
    index = load_index(root)
    index["latest_run_id"] = run_id
    save_index(index, root)


def resolve_run_id(run_id: str, root: Path = IMPROVEMENT_ROOT) -> str:
    if run_id != "latest":
        return run_id
    latest = load_index(root).get("latest_run_id", "")
    if not latest:
        raise ValueError("no latest improvement run is recorded")
    return latest


def resolve_run_dir(run_id: str, root: Path = IMPROVEMENT_ROOT) -> Path:
    resolved = resolve_run_id(run_id, root)
    path = root / "runs" / resolved
    if not path.exists():
        raise FileNotFoundError(f"run directory not found: {path}")
    return path


def load_run(run_id: str, root: Path = IMPROVEMENT_ROOT) -> ImprovementRun:
    return read_json(resolve_run_dir(run_id, root) / "run.json", ImprovementRun)


def save_run(run: ImprovementRun, root: Path = IMPROVEMENT_ROOT) -> Path:
    run_dir = root / "runs" / run.id
    return write_json(run, run_dir / "run.json")


def relative_to_project(path: Path | str) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()
