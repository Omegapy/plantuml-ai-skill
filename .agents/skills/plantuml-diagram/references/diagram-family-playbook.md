# Diagram Family Playbook

Use the user's intent, not just keywords.

- **Sequence**: time-ordered interactions between participants, requests, responses, errors, retries, callbacks. For larger traces, declare multi-word participants with aliases, then use balanced fragments such as `alt`/`else`/`end`, `loop`/`end`, `opt`/`end`, `par`/`else`/`end`, and `group`/`end`.
- **Class**: static structure, classes, interfaces, enums, attributes, methods, inheritance, composition, aggregation.
- **Activity**: workflow steps, branching, approvals, business processes, swimlanes. For larger workflows, combine block-balanced constructs such as `if`/`elseif`/`else`/`endif`, `switch`/`case`/`endswitch`, `repeat`/`repeat while`, `while`/`endwhile`, `fork`/`fork again`/`end fork`, and `split`/`split again`/`end split`.
- **State**: lifecycle states, transitions, guards, events. Prefer explicit `state` declarations or `[*]` start/end transitions so the lifecycle shape is unambiguous.
- **Use case**: actors and their goals against a system boundary.
- **Component**: deployable or logical components and dependencies.
- **Deployment**: nodes, environments, infrastructure placement.
- **Object**: concrete runtime instances and links.
- **Timing**: value/state changes over time.
- **Mindmap/WBS**: hierarchy and decomposition.
- **Gantt**: schedules, milestones, dependencies.
- **C4**: architecture context/container/component diagrams. Requires C4 macros and therefore an include policy decision; use a vendored include rather than redefining C4 macros inline.

If a request can fit multiple families, choose the one that makes relationships easiest to inspect and render.

For requests that explicitly mention large or complex diagrams, prefer readability over maximal density: introduce aliases, keep labels short, and close each nested block before starting a new peer block.
