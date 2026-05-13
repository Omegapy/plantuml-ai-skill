"""Evaluation suite creation and JSONL helpers."""

from __future__ import annotations

from pathlib import Path
import re

from plantuml_ai_skill.manifest import CorpusRecord, read_jsonl as read_manifest_jsonl

from .models import SkillEvalCase, read_jsonl, write_jsonl


def make_eval_suite_from_manifest(
    records: list[CorpusRecord],
    max_cases: int,
    include_hidden: bool = False,
) -> list[SkillEvalCase]:
    """Create a deterministic suite from hand-authored cases plus manifest signals."""

    cases = hand_authored_core_cases()
    cases.extend(_cases_from_manifest(records, include_hidden=include_hidden))
    deduped: dict[str, SkillEvalCase] = {}
    for case in cases:
        if case.hidden and not include_hidden:
            continue
        deduped.setdefault(case.id, case)
    ordered = [deduped[key] for key in sorted(deduped)]
    if max_cases > 0:
        return ordered[:max_cases]
    return ordered


def make_eval_suite_from_manifest_paths(paths: list[Path], max_cases: int) -> list[SkillEvalCase]:
    records: list[CorpusRecord] = []
    for path in paths:
        if Path(path).exists():
            records.extend(read_manifest_jsonl(path))
    return make_eval_suite_from_manifest(records, max_cases=max_cases)


def load_eval_cases(path: Path | str) -> list[SkillEvalCase]:
    return read_jsonl(path, SkillEvalCase)


def write_eval_cases(cases: list[SkillEvalCase], path: Path | str) -> Path:
    return write_jsonl(cases, path)


def hand_authored_core_cases() -> list[SkillEvalCase]:
    """Return stable public development eval cases that need no network."""

    common_forbidden = ["!includeurl", "TODO", "placeholder"]
    return [
        SkillEvalCase(
            id="activity-order-approval",
            suite="core",
            prompt="Create an activity diagram for an order approval workflow: receive order, validate inventory, branch to approve or reject, then notify the customer.",
            expected_diagram_type="activity",
            required_patterns=["Receive order", "Validate inventory", "Notify customer"],
            forbidden_patterns=common_forbidden,
            required_edges=[],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["activity", "branching", "self-contained"],
        ),
        SkillEvalCase(
            id="class-user-account-ownership",
            suite="core",
            prompt="Create a class diagram with User, Account, and Subscription. User owns accounts, and Account has one Subscription.",
            expected_diagram_type="class",
            required_patterns=["User", "Account", "Subscription"],
            forbidden_patterns=common_forbidden,
            required_edges=[("User", "Account"), ("Account", "Subscription")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["class", "relationships"],
        ),
        SkillEvalCase(
            id="component-web-api-database",
            suite="core",
            prompt="Create a component diagram showing Web App calling API, API using Database, and API sending email through Notification Service.",
            expected_diagram_type="component",
            required_patterns=["Web App", "API", "Database", "Notification Service"],
            forbidden_patterns=common_forbidden,
            required_edges=[("Web App", "API"), ("API", "Database"), ("API", "Notification Service")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["component", "dependency"],
        ),
        SkillEvalCase(
            id="include-policy-block-remote",
            suite="include_policy",
            prompt="Create a self-contained PlantUML diagram of Service A calling Service B. Do not use includes or remote URLs.",
            expected_diagram_type="sequence",
            required_patterns=["Service A", "Service B"],
            forbidden_patterns=common_forbidden + ["https://", "http://"],
            required_edges=[("Service A", "Service B")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "include_policy"],
            difficulty="easy",
            tags=["include-policy", "sequence", "self-contained"],
        ),
        SkillEvalCase(
            id="sequence-basic-api-timeout",
            suite="core",
            prompt="Create a sequence diagram showing Client calling API, API calling Database, and Database returning a timeout error.",
            expected_diagram_type="sequence",
            required_patterns=["Client", "API", "Database", "timeout"],
            forbidden_patterns=common_forbidden,
            required_edges=[("Client", "API"), ("API", "Database")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["sequence", "error-path"],
        ),
        SkillEvalCase(
            id="state-document-review",
            suite="core",
            prompt="Create a state diagram for a document lifecycle: Draft, Submitted, Approved, Rejected, with revise returning Rejected to Draft.",
            expected_diagram_type="state",
            required_patterns=["Draft", "Submitted", "Approved", "Rejected", "revise"],
            forbidden_patterns=common_forbidden,
            required_edges=[("Draft", "Submitted"), ("Submitted", "Approved"), ("Submitted", "Rejected"), ("Rejected", "Draft")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["state", "lifecycle"],
        ),
        SkillEvalCase(
            id="usecase-customer-support",
            suite="core",
            prompt="Create a use case diagram with Customer and Support Agent using a Help Desk system. Include Submit Ticket, View Ticket Status, and Resolve Ticket.",
            expected_diagram_type="usecase",
            required_patterns=["Customer", "Support Agent", "Submit Ticket", "View Ticket Status", "Resolve Ticket"],
            forbidden_patterns=common_forbidden,
            required_edges=[("Customer", "Submit Ticket"), ("Support Agent", "Resolve Ticket")],
            include_policy="self_contained_only",
            purpose=["skill_eval", "regression"],
            difficulty="easy",
            tags=["usecase", "actors"],
        ),
    ]


def _cases_from_manifest(records: list[CorpusRecord], include_hidden: bool = False) -> list[SkillEvalCase]:
    cases: list[SkillEvalCase] = []
    selected_by_type: dict[str, CorpusRecord] = {}
    for record in sorted(records, key=lambda item: item.id):
        if record.diagram_type not in selected_by_type:
            selected_by_type[record.diagram_type] = record
    for diagram_type, record in sorted(selected_by_type.items()):
        if diagram_type == "uml":
            continue
        cases.append(_case_from_record(record))
    source_record = next((record for record in sorted(records, key=lambda item: item.id) if record.python_source_paths), None)
    if source_record:
        cases.append(
            SkillEvalCase(
                id=f"source-conditioned-{_safe_id(source_record.id)}",
                suite="source_conditioned",
                prompt=(
                    "Create a PlantUML class diagram from the provided Python source context. "
                    "Preserve class names and relationships visible in the source."
                ),
                expected_diagram_type="class",
                required_patterns=_required_from_record(source_record),
                forbidden_patterns=["!includeurl", "TODO", "placeholder"],
                required_edges=[],
                include_policy="self_contained_only",
                reference_record_id=source_record.id,
                purpose=["source_conditioned_eval"],
                difficulty="medium",
                tags=["source-conditioned", "class"],
                hidden=not include_hidden and "hidden_acceptance_eval" in source_record.purpose,
            )
        )
    return cases


def _case_from_record(record: CorpusRecord) -> SkillEvalCase:
    include_policy = "local_includes_allowed" if record.include_deps else "self_contained_only"
    return SkillEvalCase(
        id=f"manifest-{_safe_id(record.id)}",
        suite="manifest",
        prompt=(
            f"Create a {record.diagram_type} PlantUML diagram inspired by verified record "
            f"{record.id}. Preserve the same broad diagram family and keep it renderable."
        ),
        expected_diagram_type=record.diagram_type,
        required_patterns=_required_from_record(record),
        forbidden_patterns=["!includeurl", "TODO", "placeholder"],
        required_edges=[],
        include_policy=include_policy,
        reference_record_id=record.id,
        purpose=["skill_eval", "manifest_regression"],
        difficulty="medium",
        tags=["manifest", record.diagram_type],
        hidden="hidden_acceptance_eval" in record.purpose,
    )


def _required_from_record(record: CorpusRecord) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_ -]{2,}", record.id.replace("-", " "))
    return sorted({token.strip() for token in tokens if len(token.strip()) >= 3})[:3]


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "case"
