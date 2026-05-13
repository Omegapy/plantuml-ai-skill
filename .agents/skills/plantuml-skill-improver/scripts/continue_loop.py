#!/usr/bin/env python3
"""Print the latest improvement-loop handoff path and status."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> int:
    repo = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(repo / "src"))
    from plantuml_ai_skill.improvement.state import load_index, resolve_run_dir

    index = load_index()
    latest = index.get("latest_run_id", "")
    if not latest:
        print("No improvement run recorded yet.")
        return 1
    try:
        run_dir = resolve_run_dir("latest")
    except FileNotFoundError as exc:
        print(f"Latest run is recorded but missing: {latest}")
        print(exc)
        return 1
    prompt = run_dir / "codex-next-prompt.md"
    print(f"latest_run_id={latest}")
    print(f"run_dir={run_dir}")
    print(f"handoff={prompt}")
    return 0 if prompt.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
