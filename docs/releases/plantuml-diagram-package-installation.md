# PlantUML Diagram Package Installation Guide

This guide is for people who want to download one PlantUML Diagram package from GitHub and install it into their own Codex project on macOS, Linux, or Windows 11.

These packages are for **Codex** and the **Codex app**. They are not Claude Code packages, and they do not install into Claude Code.

These packages are for creating, checking, and rendering PlantUML diagrams in Codex projects. They are not for training, fine-tuning, or improving the skill.

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

Download exactly one package for your operating system and use case.

| Use case | macOS or Linux download | Windows 11 download |
| --- | --- | --- |
| Skill instructions only | `plantuml-diagram-core-0.1.0.tar.gz` | `plantuml-diagram-core-0.1.0-windows.zip` |
| Skill plus PlantUML text checker | `plantuml-diagram-validate-0.1.0.tar.gz` | `plantuml-diagram-validate-0.1.0-windows.zip` |
| Checker plus SVG/PNG rendering | `plantuml-diagram-render-0.1.0.tar.gz` | `plantuml-diagram-render-0.1.0-windows.zip` |
| Rendering plus C4-PlantUML includes | `plantuml-diagram-c4-0.1.0.tar.gz` | `plantuml-diagram-c4-0.1.0-windows.zip` |
| Optional safety check file | `SHA256SUMS` | `SHA256SUMS` |

Recommendation: if you are unsure, choose the `render` package for your operating system. Choose the `c4` package only if you know you need C4 diagrams.

## What Happens When You Extract It

Each download file opens into its own installer folder.

Example on macOS or Linux:

```text
plantuml-diagram-render-0.1.0.tar.gz
```

extracts into:

```text
plantuml-diagram-render-0.1.0/
  README.md
  install.sh
  manifest.json
  payload/
```

Example on Windows 11:

```text
plantuml-diagram-render-0.1.0-windows.zip
```

extracts into:

```text
plantuml-diagram-render-0.1.0-windows/
  README.md
  install.ps1
  install.cmd
  manifest.json
  payload/
```

That folder is the installer folder. It is not the final installed location.

## Install On macOS Or Linux

These steps install the package into one project.

1. Download one `.tar.gz` package from the GitHub release page.
2. Extract the `.tar.gz` file.
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

## Install On Windows 11

These steps install the package into one project.

1. Download one `-windows.zip` package from the GitHub release page.
2. Extract the `.zip` file with Windows Explorer or PowerShell.
3. Open PowerShell.
4. Go to your project folder. Replace the path below with your real project folder:

```powershell
Set-Location C:\path\to\your-project
```

5. Run the package installer. Replace the folder name if you chose a different package:

```powershell
.\plantuml-diagram-render-0.1.0-windows\install.cmd
```

You can also run the PowerShell installer directly:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\path\to\plantuml-diagram-render-0.1.0-windows\install.ps1
```

The installer copies the useful files into your project's hidden `.agents` folder.

After install, a render or C4 package will look like this:

```text
your-project/
  .agents/
    skills/
      plantuml-diagram/
    bin/
      plantuml-ai.cmd
      plantuml-ai.ps1
    tools/
      plantuml-ai-skill/
```

The `.agents` folder is hidden because its name starts with a dot.

## Use The Installed Tool

On macOS or Linux, if you installed `validate`, `render`, or `c4`, the command is:

```bash
.agents/bin/plantuml-ai
```

On Windows 11, if you installed `validate`, `render`, or `c4`, the command is:

```powershell
.\.agents\bin\plantuml-ai.cmd
```

Check a PlantUML file:

```bash
.agents/bin/plantuml-ai validate diagram.puml
```

```powershell
.\.agents\bin\plantuml-ai.cmd validate diagram.puml
```

Render a diagram to SVG:

```bash
.agents/bin/plantuml-ai render diagram.puml --output diagram.svg
```

```powershell
.\.agents\bin\plantuml-ai.cmd render diagram.puml --output diagram.svg
```

Check the renderer setup:

```bash
.agents/bin/plantuml-ai doctor
```

```powershell
.\.agents\bin\plantuml-ai.cmd doctor
```

Use C4 support:

```bash
.agents/bin/plantuml-ai render c4-diagram.puml --c4 --output c4-diagram.svg
```

```powershell
.\.agents\bin\plantuml-ai.cmd render c4-diagram.puml --c4 --output c4-diagram.svg
```

## Requirements For Rendering

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

On Windows 11:

- Install Python 3.11 or newer.
- Install Java 11 or newer and make `java.exe` available on `PATH`.
- Install Graphviz and make `dot.exe` available on `PATH`.

Then initialize and check the renderer:

```bash
.agents/bin/plantuml-ai init-assets
.agents/bin/plantuml-ai doctor
```

```powershell
.\.agents\bin\plantuml-ai.cmd init-assets
.\.agents\bin\plantuml-ai.cmd doctor
```

`init-assets` downloads the PlantUML jar used for rendering. `doctor` checks whether Java, Graphviz, and PlantUML are ready.

## Optional Safety Check

`SHA256SUMS` lets you verify that the downloaded package was not corrupted or changed.

Example for the render package on macOS:

```bash
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/SHA256SUMS
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/plantuml-diagram-render-0.1.0.tar.gz
grep ' plantuml-diagram-render-0.1.0.tar.gz$' SHA256SUMS | shasum -a 256 -c -
```

Example for the render package on Linux:

```bash
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/SHA256SUMS
curl -L -O https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/plantuml-diagram-render-0.1.0.tar.gz
grep ' plantuml-diagram-render-0.1.0.tar.gz$' SHA256SUMS | sha256sum -c -
```

Example for the render package on Windows 11:

```powershell
Invoke-WebRequest https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/SHA256SUMS -OutFile SHA256SUMS
Invoke-WebRequest https://github.com/Omegapy/plantuml-ai-skill/releases/download/v0.1.0/plantuml-diagram-render-0.1.0-windows.zip -OutFile plantuml-diagram-render-0.1.0-windows.zip
$expected = (Select-String -Path SHA256SUMS -Pattern ' plantuml-diagram-render-0.1.0-windows.zip$').Line.Split()[0].ToUpperInvariant()
$actual = (Get-FileHash -Algorithm SHA256 .\plantuml-diagram-render-0.1.0-windows.zip).Hash
if ($expected -ne $actual) { throw "Checksum mismatch" }
```

If the check completes without an error, the download matches the published release.

## Important Notes

- Install from the root of the project that should receive the skill.
- Download only one package unless you are comparing package tiers.
- Use `.tar.gz` packages on macOS or Linux.
- Use `-windows.zip` packages on Windows 11.
- To change packages later, install the new package into the same project.
- Do not edit files inside `payload/` by hand. Let the installer copy them.
