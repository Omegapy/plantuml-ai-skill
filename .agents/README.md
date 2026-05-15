# Agent Skill Sources

This directory contains tracked Codex skill sources that are part of the
repository, not generated local state.

## Skills

- `skills/plantuml-diagram/`: the canonical packaged skill source. Release
  packages copy this skill into a consumer project's `.agents/` tree.
- `skills/plantuml-skill-improver/`: a helper skill for resuming and improving
  the PlantUML skill through the repository's deterministic evaluation loop.

Do not rename skill directories or change package-facing paths casually. The
release builder and tests expect these locations.
