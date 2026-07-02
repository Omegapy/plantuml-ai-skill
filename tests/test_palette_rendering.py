from __future__ import annotations

from pathlib import Path
import shutil
import unittest

from plantuml_ai_skill.constants import DEFAULT_JAR_PATH
from plantuml_ai_skill.includes import inline_resolved_includes, parse_include_deps, resolve_include_deps
from plantuml_ai_skill.improvement.palette import (
    C4_CONTAINER_INCLUDE,
    aether_dark_rendered_palette_issues,
    aether_dark_style_block,
    has_rendered_palette_issues,
)
from plantuml_ai_skill.renderer import PlantUMLRenderer, default_java_bin


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(DEFAULT_JAR_PATH.exists(), "PlantUML jar is not initialized")
@unittest.skipUnless(Path(default_java_bin()).exists() or shutil.which(default_java_bin()), "Java runtime is unavailable")
class PaletteRenderingTests(unittest.TestCase):
    def test_certified_family_style_blocks_render_without_palette_issues(self) -> None:
        samples = {
            "sequence": f"""@startuml
{aether_dark_style_block("sequence")}
actor Client
participant API
database Database
Client -> API: request
API -> Database: query
Database --> API: timeout
API --> Client: error response
@enduml
""",
            "class": f"""@startuml
{aether_dark_style_block("class")}
class User {{
  id: UUID
  email: str
}}
class Account {{
  status: str
}}
User "1" *-- "1..*" Account : owns
@enduml
""",
            "activity": f"""@startuml
{aether_dark_style_block("activity")}
:Start;
:Receive order;
if (Inventory available?) then (approve)
  :Approve order;
else (reject)
  :Reject order;
endif
:Notify customer;
:End;
@enduml
""",
            "state": f"""@startuml
{aether_dark_style_block("state")}
state "Start" as Start
state Draft
state Submitted
state Approved
state Rejected
state "End" as End
Start --> Draft
Draft --> Submitted : submit
Submitted --> Approved : approve
Submitted --> Rejected : reject
Rejected --> Draft : revise
Approved --> End
@enduml
""",
            "component": f"""@startuml
{aether_dark_style_block("component")}
component "Web App" as Web
component "API" as API
database "Database" as DB
component "Notification Service" as Notify
Web --> API : HTTPS
API --> DB : SQL
API --> Notify : send email
@enduml
""",
            "usecase": f"""@startuml
{aether_dark_style_block("usecase")}
left to right direction
actor Customer
actor "Support Agent" as SupportAgent
rectangle "Help Desk" {{
  usecase "Submit Ticket" as SubmitTicket
  usecase "View Ticket Status" as ViewTicketStatus
  usecase "Resolve Ticket" as ResolveTicket
}}
Customer --> SubmitTicket
Customer --> ViewTicketStatus
SupportAgent --> ResolveTicket
@enduml
""",
        }
        c4 = _c4_sample()
        if c4:
            samples["c4"] = c4

        renderer = PlantUMLRenderer()
        for diagram_type, puml in samples.items():
            with self.subTest(diagram_type=diagram_type):
                render_text = _render_text(puml)
                result = renderer.render_svg(render_text)
                self.assertTrue(result.ok, result.stderr)
                issues = aether_dark_rendered_palette_issues(result.output, puml=puml, diagram_type=diagram_type)
                self.assertFalse(has_rendered_palette_issues(issues), issues)

    def test_c4_container_include_renders_without_custom_include_root(self) -> None:
        puml = f"""@startuml
{C4_CONTAINER_INCLUDE}
{aether_dark_style_block("c4")}
Person(user, "User")
System_Boundary(system, "Diagram Service") {{
  Container(api, "API", "Python/FastAPI")
  ContainerDb(db, "Database", "PostgreSQL")
}}
Rel(user, api, "Uses")
Rel(api, db, "Reads/Writes", "SQL", $tags="risk")
@enduml
"""
        result = PlantUMLRenderer().render_svg(puml)
        self.assertTrue(result.ok, result.stderr)
        issues = aether_dark_rendered_palette_issues(result.output, puml=puml, diagram_type="c4")
        self.assertFalse(has_rendered_palette_issues(issues), issues)


def _c4_sample() -> str:
    include_root = ROOT / "data" / "vendor" / "c4-plantuml"
    if not (include_root / "C4_Container.puml").exists():
        return ""
    return f"""@startuml
{C4_CONTAINER_INCLUDE}
{aether_dark_style_block("c4")}
Person(user, "User")
System_Boundary(system, "Diagram Service") {{
  Container(api, "API", "Python/FastAPI")
  ContainerDb(db, "Database", "PostgreSQL")
}}
Rel(user, api, "Uses")
Rel(api, db, "Reads/Writes", "SQL", $tags="risk")
@enduml
"""


def _render_text(puml: str) -> str:
    include_root = ROOT / "data" / "vendor" / "c4-plantuml"
    includes = parse_include_deps(puml)
    if not includes:
        return puml
    return inline_resolved_includes(puml, resolve_include_deps(includes, [include_root]))


if __name__ == "__main__":
    unittest.main()
