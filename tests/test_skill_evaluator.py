from pathlib import Path
import tempfile
import unittest

from plantuml_ai_skill.improvement.evaluator import evaluate_attempt
from plantuml_ai_skill.improvement.models import SkillAttempt, SkillEvalCase
from plantuml_ai_skill.improvement.palette import AETHER_DARK_STYLE_BLOCK, aether_dark_style_block
from plantuml_ai_skill.renderer import RenderResult


class FakeRenderer:
    def render_svg(self, puml_text: str) -> RenderResult:
        return RenderResult(
            ok=True,
            output=b'<svg xmlns="http://www.w3.org/2000/svg"><text>ok</text></svg>',
            stderr="",
            command=["fake"],
            returncode=0,
        )


class AetherRenderer:
    def __init__(self, output: bytes | None = None) -> None:
        self.output = output or (
            b'<svg xmlns="http://www.w3.org/2000/svg" style="background:#000000">'
            b'<rect fill="#050403" stroke="#d6c3b4"/>'
            b'<text fill="#fff8ef">ok</text>'
            b'<circle fill="#0f364d" stroke="#d6c3b4"/>'
            b'<path fill="#080401" stroke="#f4d6a1"/>'
            b"</svg>"
        )

    def render_svg(self, puml_text: str) -> RenderResult:
        return RenderResult(True, self.output, "", ["fake"], 0)


class FailingRenderer:
    def render_svg(self, puml_text: str) -> RenderResult:
        return RenderResult(False, b"", "render_timeout", ["fake"], 124)


class SkillEvaluatorTests(unittest.TestCase):
    def test_valid_sequence_diagram_passes(self) -> None:
        case = _case()
        attempt = _attempt(
            "@startuml\nClient -> API: request\nAPI -> Database: query\nDatabase --> API: timeout\nAPI --> Client: error\n@enduml"
        )
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate_attempt(case, attempt, FakeRenderer(), Path(tmp))
        self.assertEqual(1.0, result.score)
        self.assertEqual([], result.failures)
        self.assertEqual("ok", result.render_status)
        self.assertTrue(result.render_hash_svg)

    def test_aether_palette_policy_accepts_styled_diagram(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_required"),
            _attempt(
                f"@startuml\n{AETHER_DARK_STYLE_BLOCK}\nClient -> API: request\nAPI -> Database: query\n"
                "Database --> API: timeout\nAPI --> Client: error\n@enduml"
            ),
            FakeRenderer(),
        )
        self.assertEqual([], result.failures)
        self.assertEqual("ok", result.output_contract_status)

    def test_aether_palette_policy_rejects_unstyled_diagram(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_required"),
            _attempt("@startuml\nClient -> API: request\nAPI -> Database: timeout\n@enduml"),
            FakeRenderer(),
        )
        self.assertIn("palette_policy_violation", {failure.code for failure in result.failures})
        self.assertEqual("failed", result.output_contract_status)

    def test_aether_palette_policy_rejects_off_palette_hex(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_required"),
            _attempt(
                f"@startuml\n{AETHER_DARK_STYLE_BLOCK}\nskinparam ParticipantBackgroundColor #ff0000\n"
                "Client -> API: request\nAPI -> Database: timeout\n@enduml"
            ),
            FakeRenderer(),
        )
        failures = {failure.code: failure for failure in result.failures}
        self.assertIn("palette_policy_violation", failures)
        self.assertIn("#ff0000", failures["palette_policy_violation"].details["unapproved_colors"])

    def test_aether_rendered_policy_accepts_clean_rendered_svg(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_rendered_required"),
            _attempt(
                f"@startuml\n{aether_dark_style_block('sequence')}\nactor Client\nparticipant API\n"
                "database Database\nClient -> API: request\nAPI -> Database: timeout\n@enduml"
            ),
            AetherRenderer(),
        )
        self.assertEqual([], result.failures)
        self.assertEqual("ok", result.render_status)

    def test_aether_rendered_policy_requires_renderer(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_rendered_required"),
            _attempt(
                f"@startuml\n{aether_dark_style_block('sequence')}\nactor Client\nparticipant API\n"
                "database Database\nClient -> API: request\nAPI -> Database: timeout\n@enduml"
            ),
            None,
        )
        self.assertEqual("failed", result.render_status)
        self.assertIn("render_palette_check_skipped", {failure.code for failure in result.failures})

    def test_aether_rendered_policy_rejects_fallback_color(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_rendered_required"),
            _attempt(
                f"@startuml\n{aether_dark_style_block('sequence')}\nactor Client\nparticipant API\n"
                "database Database\nClient -> API: request\nAPI -> Database: timeout\n@enduml"
            ),
            AetherRenderer(
                b'<svg xmlns="http://www.w3.org/2000/svg" style="background:#000000">'
                b'<rect fill="#050403" stroke="#181818"/>'
                b'<text fill="#fff8ef">ok</text>'
                b"</svg>"
            ),
        )
        failures = {failure.code: failure for failure in result.failures}
        self.assertIn("render_palette_policy_violation", failures)
        self.assertIn("#181818", failures["render_palette_policy_violation"].details["unapproved_colors"])

    def test_aether_rendered_policy_rejects_warning_banner(self) -> None:
        result = evaluate_attempt(
            _case(palette_policy="aether_dark_rendered_required"),
            _attempt(
                f"@startuml\n{aether_dark_style_block('sequence')}\nactor Client\nparticipant API\n"
                "database Database\nClient -> API: request\nAPI -> Database: timeout\n@enduml"
            ),
            AetherRenderer(
                b'<svg xmlns="http://www.w3.org/2000/svg" style="background:#000000">'
                b'<rect fill="#050403" stroke="#d6c3b4"/>'
                b'<text fill="#fff8ef">Please&#160;use&#160;'
                b"'!option&#160;handwritten&#160;true'&#160;to&#160;enable&#160;handwritten</text>"
                b'<circle fill="#0f364d" stroke="#d6c3b4"/>'
                b'<path fill="#080401" stroke="#f4d6a1"/>'
                b"</svg>"
            ),
        )
        failures = {failure.code: failure for failure in result.failures}
        self.assertIn("render_palette_policy_violation", failures)
        self.assertIn(
            "Please use '!option handwritten true' to enable handwritten",
            failures["render_palette_policy_violation"].details["forbidden_texts"],
        )

    def test_wrong_diagram_type_fails(self) -> None:
        result = evaluate_attempt(
            _case(),
            _attempt("@startuml\nclass Client\nclass API\nClient --> API\n@enduml"),
            FakeRenderer(),
        )
        self.assertIn("wrong_diagram_family", {failure.code for failure in result.failures})

    def test_missing_required_actor_fails(self) -> None:
        result = evaluate_attempt(
            _case(),
            _attempt("@startuml\nClient -> API: request\nAPI --> Client: ok\n@enduml"),
            FakeRenderer(),
        )
        self.assertIn("missing_required_pattern", {failure.code for failure in result.failures})

    def test_remote_include_fails_policy(self) -> None:
        result = evaluate_attempt(
            _case(),
            _attempt("@startuml\n!includeurl https://example.com/c4.puml\nClient -> API\nAPI -> Database\n@enduml"),
            FakeRenderer(),
        )
        self.assertIn("remote_include_policy_violation", {failure.code for failure in result.failures})

    def test_no_plantuml_block_fails(self) -> None:
        result = evaluate_attempt(_case(), _attempt("Here is the diagram in prose."), FakeRenderer())
        self.assertIn("no_plantuml_block", {failure.code for failure in result.failures})

    def test_multiple_blocks_fail_by_default(self) -> None:
        result = evaluate_attempt(
            _case(),
            _attempt("@startuml\nClient -> API\n@enduml\n@startuml\nAPI -> Database\n@enduml"),
            FakeRenderer(),
        )
        self.assertIn("multiple_plantuml_blocks", {failure.code for failure in result.failures})

    def test_renderer_failure_is_structured(self) -> None:
        result = evaluate_attempt(
            _case(),
            _attempt("@startuml\nClient -> API\nAPI -> Database\nDatabase --> API: timeout\n@enduml"),
            FailingRenderer(),
        )
        self.assertEqual("failed", result.render_status)
        self.assertIn("render_timeout", {failure.code for failure in result.failures})

    def test_required_edges_match_declared_aliases(self) -> None:
        case = SkillEvalCase(
            id="component-web-api-database",
            suite="core",
            prompt="Create a component diagram showing Web App calling API and API sending email through Notification Service.",
            expected_diagram_type="component",
            required_patterns=["Web App", "API", "Notification Service"],
            forbidden_patterns=["!includeurl", "TODO", "placeholder"],
            required_edges=[("Web App", "API"), ("API", "Notification Service")],
            include_policy="self_contained_only",
            purpose=["skill_eval"],
            difficulty="easy",
            tags=["component"],
        )
        attempt = _attempt(
            "\n".join(
                [
                    "@startuml",
                    'component "Web App" as WebApp',
                    "component API",
                    'component "Notification Service" as NotificationService',
                    "WebApp --> API : calls",
                    "API --> NotificationService : sends email",
                    "@enduml",
                ]
            )
        )
        result = evaluate_attempt(case, attempt, FakeRenderer())
        self.assertEqual([], result.failures)

    def test_required_edges_match_usecase_aliases(self) -> None:
        case = SkillEvalCase(
            id="usecase-customer-support",
            suite="core",
            prompt="Create a use case diagram with Customer and Support Agent.",
            expected_diagram_type="usecase",
            required_patterns=["Customer", "Support Agent", "Submit Ticket", "Resolve Ticket"],
            forbidden_patterns=["!includeurl", "TODO", "placeholder"],
            required_edges=[("Customer", "Submit Ticket"), ("Support Agent", "Resolve Ticket")],
            include_policy="self_contained_only",
            purpose=["skill_eval"],
            difficulty="easy",
            tags=["usecase"],
        )
        attempt = _attempt(
            "\n".join(
                [
                    "@startuml",
                    "actor Customer",
                    'actor "Support Agent" as SupportAgent',
                    'usecase "Submit Ticket" as SubmitTicket',
                    'usecase "Resolve Ticket" as ResolveTicket',
                    "Customer --> SubmitTicket",
                    "SupportAgent --> ResolveTicket",
                    "@enduml",
                ]
            )
        )
        result = evaluate_attempt(case, attempt, FakeRenderer())
        self.assertEqual([], result.failures)


def _case(palette_policy: str = "none") -> SkillEvalCase:
    return SkillEvalCase(
        id="sequence-basic-api-timeout",
        suite="core",
        prompt="Create a sequence diagram showing Client calling API, API calling Database, and Database returning a timeout error.",
        expected_diagram_type="sequence",
        required_patterns=["Client", "API", "Database", "timeout"],
        forbidden_patterns=["!includeurl", "TODO", "placeholder"],
        required_edges=[("Client", "API"), ("API", "Database")],
        include_policy="self_contained_only",
        palette_policy=palette_policy,
        purpose=["skill_eval"],
        difficulty="easy",
        tags=["sequence"],
    )


def _attempt(text: str) -> SkillAttempt:
    return SkillAttempt(
        id="attempt-001",
        run_id="run-001",
        skill_version_id="skill-001",
        case_id="sequence-basic-api-timeout",
        model_or_agent="test",
        created_at="2026-05-13T12:00:00Z",
        raw_response_path="attempt.md",
        puml_text=text,
    )


if __name__ == "__main__":
    unittest.main()
