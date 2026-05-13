# Include Policy

Default to self-contained diagrams.

Allowed:

- No includes.
- Local/vendored includes already present in the repository.
- C4 includes when the user explicitly asks for C4 notation or the repo has configured vendored C4 support.

Blocked:

- Arbitrary `!includeurl`.
- HTTP or HTTPS includes that are not mirrored through the repo's trusted include logic.
- Includes needed only for decorative icons unless the user explicitly asks for those icons.

When a notation needs an include, make the dependency visible and auditable. Do not silently rely on network access.
