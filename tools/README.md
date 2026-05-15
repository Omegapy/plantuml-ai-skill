# Local Tool Assets

This directory is for local tool assets that should not be committed.

The main current use is `tools/plantuml/`, where `plantuml-skill init-assets`
stores the pinned PlantUML jar and metadata used for rendering.

Do not commit downloaded jars, caches, or machine-local tools. The release
packages install source files and fetch the PlantUML jar with
`plantuml-ai init-assets` when rendering support is needed.
