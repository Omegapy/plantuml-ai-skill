"""Dataclasses and JSON helpers for the skill improvement loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Iterable, TypeVar

from .palette import PALETTE_POLICY_NONE, normalize_palette_policy


JsonObject = dict[str, Any]
T = TypeVar("T")


@dataclass
class SkillVersion:
    id: str
    created_at: str
    git_commit: str
    skill_path: str
    skill_sha256: str
    builder_version: str
    source_manifests: list[str]
    notes: str = ""

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "SkillVersion":
        _reject_unknown(data, _field_names(cls))
        _require(data, ["id", "created_at", "git_commit", "skill_path", "skill_sha256", "builder_version"])
        return cls(
            id=_as_str(data, "id"),
            created_at=_as_str(data, "created_at"),
            git_commit=_as_str(data, "git_commit"),
            skill_path=_as_str(data, "skill_path"),
            skill_sha256=_as_str(data, "skill_sha256"),
            builder_version=_as_str(data, "builder_version"),
            source_manifests=_as_str_list(data.get("source_manifests", []), "source_manifests"),
            notes=str(data.get("notes", "")),
        )

    def to_mapping(self) -> JsonObject:
        return asdict(self)


@dataclass
class SkillEvalCase:
    id: str
    suite: str
    prompt: str
    expected_diagram_type: str
    required_patterns: list[str]
    forbidden_patterns: list[str]
    required_edges: list[tuple[str, str]]
    include_policy: str
    reference_record_id: str = ""
    purpose: list[str] = field(default_factory=list)
    difficulty: str = "easy"
    tags: list[str] = field(default_factory=list)
    allow_multiple_blocks: bool = False
    hidden: bool = False
    source_context: str = ""
    palette_policy: str = PALETTE_POLICY_NONE

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "SkillEvalCase":
        _reject_unknown(data, _field_names(cls))
        _require(data, ["id", "suite", "prompt", "expected_diagram_type", "include_policy"])
        required_edges = []
        for index, edge in enumerate(data.get("required_edges", [])):
            if not isinstance(edge, list | tuple) or len(edge) != 2:
                raise TypeError(f"required_edges[{index}] must be a two-item list")
            required_edges.append((str(edge[0]), str(edge[1])))
        return cls(
            id=_as_str(data, "id"),
            suite=_as_str(data, "suite"),
            prompt=_as_str(data, "prompt"),
            expected_diagram_type=_as_str(data, "expected_diagram_type"),
            required_patterns=_as_str_list(data.get("required_patterns", []), "required_patterns"),
            forbidden_patterns=_as_str_list(data.get("forbidden_patterns", []), "forbidden_patterns"),
            required_edges=required_edges,
            include_policy=_as_str(data, "include_policy"),
            reference_record_id=str(data.get("reference_record_id", "")),
            purpose=_as_str_list(data.get("purpose", []), "purpose"),
            difficulty=str(data.get("difficulty", "easy")),
            tags=_as_str_list(data.get("tags", []), "tags"),
            allow_multiple_blocks=bool(data.get("allow_multiple_blocks", False)),
            hidden=bool(data.get("hidden", False)),
            source_context=str(data.get("source_context", "")),
            palette_policy=normalize_palette_policy(str(data.get("palette_policy", PALETTE_POLICY_NONE))),
        )

    def to_mapping(self) -> JsonObject:
        payload = asdict(self)
        payload["required_edges"] = [list(edge) for edge in self.required_edges]
        return payload


@dataclass
class SkillAttempt:
    id: str
    run_id: str
    skill_version_id: str
    case_id: str
    model_or_agent: str
    created_at: str
    raw_response_path: str
    puml_text: str = ""
    extra: JsonObject = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "SkillAttempt":
        known = _field_names(cls)
        _require(
            data,
            [
                "id",
                "run_id",
                "skill_version_id",
                "case_id",
                "model_or_agent",
                "created_at",
                "raw_response_path",
            ],
        )
        extra = dict(data.get("extra") or {})
        extra.update({key: value for key, value in data.items() if key not in known})
        return cls(
            id=_as_str(data, "id"),
            run_id=_as_str(data, "run_id"),
            skill_version_id=_as_str(data, "skill_version_id"),
            case_id=_as_str(data, "case_id"),
            model_or_agent=_as_str(data, "model_or_agent"),
            created_at=_as_str(data, "created_at"),
            raw_response_path=_as_str(data, "raw_response_path"),
            puml_text=str(data.get("puml_text", "")),
            extra=extra,
        )

    def to_mapping(self) -> JsonObject:
        payload = asdict(self)
        extra = payload.pop("extra", {})
        payload.update(extra)
        return payload


@dataclass
class Failure:
    code: str
    message: str
    severity: str = "error"
    details: JsonObject = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "Failure":
        _reject_unknown(data, _field_names(cls))
        _require(data, ["code", "message"])
        return cls(
            code=_as_str(data, "code"),
            message=_as_str(data, "message"),
            severity=str(data.get("severity", "error")),
            details=dict(data.get("details") or {}),
        )

    def to_mapping(self) -> JsonObject:
        return asdict(self)


@dataclass
class SkillEvaluationResult:
    attempt_id: str
    case_id: str
    extract_status: str
    syntax_status: str
    diagram_type_status: str
    include_policy_status: str
    render_status: str
    semantic_status: str
    output_contract_status: str
    score: float
    failures: list[Failure]
    render_hash_svg: str = ""
    rendered_svg_path: str = ""

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "SkillEvaluationResult":
        _reject_unknown(data, _field_names(cls))
        _require(
            data,
            [
                "attempt_id",
                "case_id",
                "extract_status",
                "syntax_status",
                "diagram_type_status",
                "include_policy_status",
                "render_status",
                "semantic_status",
                "output_contract_status",
                "score",
            ],
        )
        failures = [Failure.from_mapping(item) for item in data.get("failures", [])]
        return cls(
            attempt_id=_as_str(data, "attempt_id"),
            case_id=_as_str(data, "case_id"),
            extract_status=_as_str(data, "extract_status"),
            syntax_status=_as_str(data, "syntax_status"),
            diagram_type_status=_as_str(data, "diagram_type_status"),
            include_policy_status=_as_str(data, "include_policy_status"),
            render_status=_as_str(data, "render_status"),
            semantic_status=_as_str(data, "semantic_status"),
            output_contract_status=_as_str(data, "output_contract_status"),
            score=float(data["score"]),
            failures=failures,
            render_hash_svg=str(data.get("render_hash_svg", "")),
            rendered_svg_path=str(data.get("rendered_svg_path", "")),
        )

    def to_mapping(self) -> JsonObject:
        payload = asdict(self)
        payload["failures"] = [failure.to_mapping() for failure in self.failures]
        return payload


@dataclass
class ImprovementRun:
    id: str
    created_at: str
    status: str
    baseline_skill_version_id: str
    candidate_skill_version_id: str
    suite_path: str
    attempts_path: str
    results_path: str
    report_path: str
    next_handoff_path: str
    metrics: JsonObject = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "ImprovementRun":
        _reject_unknown(data, _field_names(cls))
        _require(data, ["id", "created_at", "status", "suite_path", "attempts_path", "results_path"])
        return cls(
            id=_as_str(data, "id"),
            created_at=_as_str(data, "created_at"),
            status=_as_str(data, "status"),
            baseline_skill_version_id=str(data.get("baseline_skill_version_id", "")),
            candidate_skill_version_id=str(data.get("candidate_skill_version_id", "")),
            suite_path=_as_str(data, "suite_path"),
            attempts_path=_as_str(data, "attempts_path"),
            results_path=_as_str(data, "results_path"),
            report_path=str(data.get("report_path", "")),
            next_handoff_path=str(data.get("next_handoff_path", "")),
            metrics=dict(data.get("metrics") or {}),
        )

    def to_mapping(self) -> JsonObject:
        return asdict(self)


@dataclass
class FailureCluster:
    id: str
    count: int
    severity: str
    evidence_case_ids: list[str]
    messages: list[str] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: JsonObject) -> "FailureCluster":
        _reject_unknown(data, _field_names(cls))
        _require(data, ["id", "count", "severity", "evidence_case_ids"])
        return cls(
            id=_as_str(data, "id"),
            count=int(data["count"]),
            severity=_as_str(data, "severity"),
            evidence_case_ids=_as_str_list(data["evidence_case_ids"], "evidence_case_ids"),
            messages=_as_str_list(data.get("messages", []), "messages"),
        )

    def to_mapping(self) -> JsonObject:
        return asdict(self)


@dataclass
class SkillLesson:
    id: str
    trigger: str
    instruction: str
    evidence_case_ids: list[str]

    def to_mapping(self) -> JsonObject:
        return asdict(self)


@dataclass
class PromotionDecision:
    run_id: str
    promote: bool
    reasons: list[str]
    metrics: JsonObject

    def to_mapping(self) -> JsonObject:
        return asdict(self)


def read_json(path: Path | str, loader: type[T]) -> T:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return loader.from_mapping(data)  # type: ignore[attr-defined]


def write_json(item: Any, path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = item.to_mapping() if hasattr(item, "to_mapping") else item
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def read_jsonl(path: Path | str, loader: type[T]) -> list[T]:
    jsonl_path = Path(path)
    if not jsonl_path.exists():
        return []
    rows: list[T] = []
    for line_number, line in enumerate(jsonl_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(loader.from_mapping(json.loads(line)))  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - useful message is the behavior
            raise ValueError(f"{jsonl_path}:{line_number}: invalid row: {exc}") from exc
    return rows


def write_jsonl(items: Iterable[Any], path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for item in items:
        payload = item.to_mapping() if hasattr(item, "to_mapping") else item
        lines.append(json.dumps(payload, sort_keys=True))
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return output_path


def _field_names(cls: type[Any]) -> set[str]:
    return set(cls.__dataclass_fields__)  # type: ignore[attr-defined]


def _reject_unknown(data: JsonObject, known: set[str]) -> None:
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")


def _require(data: JsonObject, fields: list[str]) -> None:
    missing = [name for name in fields if name not in data]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _as_str(data: JsonObject, key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise TypeError(f"{key} must be a string")
    return value


def _as_str_list(value: Any, key: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise TypeError(f"{key}[{index}] must be a string")
    return list(value)
