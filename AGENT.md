# Agent Guidance

This repository is for a Python AI skill that generates, validates, and renders PlantUML diagrams from natural-language prompts.

## Working Rules

- Use Python and the repo-local virtual environment at `.venv/`.
- Keep generated PlantUML source inspectable before rendering.
- Validate PlantUML code before rendering diagrams.
- Use the pinned Java PlantUML jar as the primary renderer.
- Keep Graphviz available and verified with `java -jar plantuml.jar -testdot`.
- Keep corpus records manifest-first and preserve row-level source/license provenance.
- Avoid committing secrets, local caches, virtual environments, or throwaway rendered artifacts unless they are intentionally part of the repository.
- Keep changes focused on the requested skill behavior and follow the existing project structure as it grows.
