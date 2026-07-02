---
name: plantuml-diagram
description: Generate, validate, and repair PlantUML diagrams from natural-language requests. Use for sequence, class, activity, state, use case, component, deployment, C4, mindmap, gantt, and other PlantUML diagram tasks.
---

# PlantUML Diagram

## When To Use

Use this skill whenever the user asks for PlantUML, UML-as-code, diagram source, diagram repair, or a rendered/checkable diagram that should be expressed as PlantUML.

## Output Contract

- Emit exactly one complete PlantUML document unless the user explicitly asks for multiple diagrams.
- Put the diagram in one fenced `plantuml` block or provide only the raw PlantUML when the surrounding workflow requires raw text.
- Include a matching `@start...` and `@end...` pair.
- Use the AEther dark PlantUML palette by default unless the user explicitly requests another style.
- Preserve the user's named actors, systems, entities, relationships, labels, constraints, and requested diagram family.
- Do not leave TODOs, placeholders, or prose-only answers when a diagram is requested.

Read `references/output-contract.md` when the user needs a strict machine-readable response.
Read `references/palette-contract.md` before writing the style block.

## Generation Workflow

1. Choose the diagram family from the user's intent. Read `references/diagram-family-playbook.md` when the request is ambiguous or uses a less common PlantUML family.
2. Add the matching AEther dark family style block from `references/palette-contract.md` immediately after `@start...` unless the user explicitly asks for another style.
3. Draft self-contained PlantUML first.
4. Add every required participant/entity before drawing relationships.
5. Use clear labels on important edges, especially outcomes, errors, retries, ownership, and direction.
6. For strict AEther activity/state diagrams, prefer explicit styled Start/End nodes over unstyleable pseudo-nodes such as `start`, `stop`, and `[*]`.
7. For large activity or sequence diagrams, plan nested blocks before writing them and close every `if`, `switch`, `repeat`, `while`, `fork`, `split`, `alt`, `loop`, `opt`, `par`, and `group` block in order.
8. Validate syntax and palette shape locally before claiming success.
9. When working in this repository, run `.agents/skills/plantuml-diagram/scripts/validate_plantuml_attempt.py --palette-policy aether-dark-rendered --render` or `plantuml-skill improve evaluate` if an eval run exists.

## Include Policy

- Prefer self-contained PlantUML.
- Do not use arbitrary remote `!includeurl`.
- Use local or vendored includes only when the user asks for a notation that requires them, such as C4 macros.
- If a C4 diagram uses macros, include an auditable C4 include that can render outside this repository.
- Use `!include <C4/C4_Container.puml>` for C4 container diagrams; local validation maps it to the repo-vendored C4 snapshot. Do not hand-write replacement `Person`, `Container`, `System_Boundary`, or `Rel` procedures.

Read `references/include-policy.md` before adding includes.

## Failure Patterns To Avoid

- Returning Markdown explanation without a PlantUML block.
- Emitting more than one PlantUML block for a single-diagram request.
- Choosing the wrong diagram family because a word like "flow" could mean sequence or activity.
- Using C4 macros without a C4 include.
- Omitting dashed return messages in sequence diagrams when the user asks for a response, error, or outcome.
- Losing block balance in large workflows or traces, especially nested `split`/`fork` activity branches and `par`/`alt` sequence fragments.
- Using remote includes, TODO placeholders, or fake entities not present in the prompt.

## Examples

Read `references/examples.md` for concise examples of sequence, class, activity, state, component, use case, C4, and include-policy-safe diagrams.

Read `references/large-diagram-patterns.md` when a request asks for a large, complex, parallel, branching, or stress-test activity/sequence diagram.
