# PlantUML Diagram Package Installation Guide

This guide is for people who want to download one PlantUML Diagram package from GitHub and install it into their own project on macOS or Linux.

These packages are for **Codex** and the **Codex app**. They are not Claude Code packages, and they do not install into Claude Code.

You do not need to understand the release system. The important idea is:

```text
download file -> unzipped installer folder -> your project's hidden .agents folder
```

Codex reads the installed files from the hidden `.agents` folder in your project.

## Choose One Download File

Open the GitHub release page:

```text
https://github.com/Omegapy/plantuml-ai-skill/releases/tag/v0.1.0
```

Download exactly one package for what you need.

| Download file | Plain-English use |
| --- | --- |
| `plantuml-diagram-core-0.1.0.tar.gz` | Skill instructions only. Choose this if you only want the AI guidance files. |
| `plantuml-diagram-validate-0.1.0.tar.gz` | Skill instructions plus a checker. Choose this if you want to check PlantUML text but not render diagrams. |
| `plantuml-diagram-render-0.1.0.tar.gz` | Checker plus diagram rendering. Choose this if you want to create SVG or PNG diagram files. |
| `plantuml-diagram-c4-0.1.0.tar.gz` | Rendering plus C4 diagram support. Choose this if you use C4-PlantUML diagrams. |
| `SHA256SUMS` | Optional safety check file. This is not an installer. |

Recommendation: if you are unsure, choose `plantuml-diagram-render-0.1.0.tar.gz`. Choose `plantuml-diagram-c4-0.1.0.tar.gz` only if you know you need C4 diagrams.

## What Happens When You Unzip It

Each `.tar.gz` download file opens into its own installer folder.

Example:

```text
plantuml-diagram-render-0.1.0.tar.gz
```

unzips into:

```text
plantuml-diagram-render-0.1.0/
  README.md
  install.sh
  manifest.json
  payload/
```

That folder is the installer folder. It is not the final installed location.

## Install On macOS Or Linux

These steps install the package into one project.

1. Download one package from the GitHub release page.
2. Unzip the `.tar.gz` file.
   - On macOS, you can usually double-click it.
   - On Linux, use `tar -xzf package-name.tar.gz`.
3. Open Terminal.
4. Go to your project folder. Replace the path below with your real project folder:

```bash
cd /path/to/your-project
```

5. Run the package installer. Replace the folder name if you chose a different package:

```bash
bash /path/to/plantuml-diagram-render-0.1.0/install.sh
```

The installer copies the useful files into your project's hidden `.agents` folder.

After install, your project will look like this:

```text
your-project/
  .agents/
    skills/
      plantuml-diagram/
    bin/
      plantuml-ai
    tools/
      plantuml-ai-skill/
```

The `.agents` folder is hidden because its name starts with a dot.

## Use The Installed Tool

If you installed `validate`, `render`, or `c4`, the command is:

```bash
.agents/bin/plantuml-ai
```

Check a PlantUML file:

```bash
.agents/bin/plantuml-ai validate diagram.puml
```

Render a diagram to SVG:

```bash
.agents/bin/plantuml-ai render diagram.puml --output diagram.svg
```

Check the renderer setup:

```bash
.agents/bin/plantuml-ai doctor
```

Use C4 support:

```bash
.agents/bin/plantuml-ai render c4-diagram.puml --c4 --output c4-diagram.svg
```

## macOS And Linux Requirements For Rendering

The `core` and `validate` packages are lightweight.

The `render` and `c4` packages need:

- Python 3.11 or newer
- Java 11 or newer
- Graphviz

On macOS with Homebrew:

```bash
brew install python@3.12 openjdk graphviz
```

On Ubuntu or Debian Linux:

```bash
sudo apt update
sudo apt install python3 openjdk-17-jre graphviz curl
```

Then run:

```bash
.agents/bin/plantuml-ai init-assets
.agents/bin/plantuml-ai doctor
```

`init-assets` downloads the PlantUML jar used for rendering. `doctor` checks whether Java, Graphviz, and PlantUML are ready.

## Optional Safety Check

`SHA256SUMS` lets you verify that the downloaded package was not corrupted or changed.

Example for the render package:

On macOS:

```bash
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/SHA256SUMS
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/plantuml-diagram-render-0.1.0.tar.gz
grep ' plantuml-diagram-render-0.1.0.tar.gz$' SHA256SUMS | shasum -a 256 -c -
```

On Linux:

```bash
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/SHA256SUMS
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/plantuml-diagram-render-0.1.0.tar.gz
grep ' plantuml-diagram-render-0.1.0.tar.gz$' SHA256SUMS | sha256sum -c -
```

If the check prints `OK`, the download matches the published release.

## Important Notes

- Install from the root of the project that should receive the skill.
- Download only one package unless you are comparing package tiers.
- To change packages later, install the new package into the same project.
- Do not edit files inside `payload/` by hand. Let `install.sh` copy them.
