"""Helpers for storing and loading Codex-generated PlantUML attempts."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from plantuml_ai_skill.extraction import extract_plantuml_blocks

from .models import SkillAttempt, read_jsonl, write_jsonl
from .state import utc_now


def load_attempts(path: Path | str) -> list[SkillAttempt]:
    return read_jsonl(path, SkillAttempt)


def write_attempts(attempts: list[SkillAttempt], path: Path | str) -> Path:
    return write_jsonl(attempts, path)


def attempt_text(attempt: SkillAttempt) -> str:
    if attempt.puml_text:
        return attempt.puml_text
    path = Path(attempt.raw_response_path)
    if path.exists():
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def plantuml_text_from_response(response: str) -> str:
    blocks = extract_plantuml_blocks(response)
    if len(blocks) == 1:
        return blocks[0]
    return response.strip()


def make_attempt(
    run_id: str,
    skill_version_id: str,
    case_id: str,
    response_path: Path,
    model_or_agent: str = "codex-app",
) -> SkillAttempt:
    text = response_path.read_text(encoding="utf-8", errors="replace")
    return SkillAttempt(
        id=attempt_id(run_id, case_id, text),
        run_id=run_id,
        skill_version_id=skill_version_id,
        case_id=case_id,
        model_or_agent=model_or_agent,
        created_at=utc_now(),
        raw_response_path=str(response_path),
        puml_text=plantuml_text_from_response(text),
    )


def record_attempt_file(
    existing: list[SkillAttempt],
    attempts_dir: Path,
    run_id: str,
    skill_version_id: str,
    case_id: str,
    response_file: Path,
    model_or_agent: str = "codex-app",
) -> list[SkillAttempt]:
    attempts_dir.mkdir(parents=True, exist_ok=True)
    stored_path = attempts_dir / f"{case_id}{response_file.suffix or '.md'}"
    if response_file.resolve() != stored_path.resolve():
        shutil.copyfile(response_file, stored_path)
    attempt = make_attempt(run_id, skill_version_id, case_id, stored_path, model_or_agent=model_or_agent)
    return [item for item in existing if item.case_id != case_id] + [attempt]


def attempt_id(run_id: str, case_id: str, response: str) -> str:
    digest = hashlib.sha1(f"{run_id}\n{case_id}\n{response}".encode("utf-8")).hexdigest()[:12]
    return f"attempt-{case_id}-{digest}"
