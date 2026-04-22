# Easy Localhost

Easy Localhost is a compact Windows desktop controller for local development servers.
It keeps a live view of the localhost ports you actually care about, shows which project they belong to, and lets you act on them without dropping to terminal commands.

The interface is intentionally small, dark, and premium: pure black background, cacao/arena earth tones, rounded panels, high-contrast process rows, and one consistent app icon across the window, executable, and release asset.

## What It Solves

When you work with multiple repos, AI coding tools, IIS Express, `npm run dev`, `dotnet`, Python dev servers, or several versions of the same app, localhost becomes noisy fast. It is common to end up with many listening ports and very little context about:

- which port belongs to which project
- whether the port is responding over HTTP
- where the process came from
- how to open it quickly
- how to close it cleanly

Easy Localhost gives you a small always-on-top panel focused only on that.

## Features

- Live localhost monitoring with low overhead
- Compact floating Windows UI designed to stay visible in a screen corner
- Premium black visual system with cacao, sand, warm brown, and soft aqua accents
- Shared app icon embedded in the executable and used inside the UI
- Collapsible grouping by project/folder so large localhost sessions stay manageable
- High-contrast process rows with large port labels and visible status bars
- Stable scroll behavior during refreshes
- Manual reload plus configurable auto-refresh presets of 5s and 10s
- Automatic project detection from Git roots, `package.json`, and common project markers
- HTTP health probing to distinguish active servers from plain listeners
- One-click actions per entry:
  - `Open` in Chrome when available
  - `Copy` localhost URL
  - `Source` open the project folder in Explorer
  - `Close` terminate the owning process tree
- No backend service
- No installation required for the built app
- No external network calls
- No file edits inside your projects

## Safety Model

This repository is intentionally narrow in scope.

- It reads only local process and socket metadata from Windows.
- It inspects only local folders to infer project names.
- It never modifies source code in detected projects.
- It never connects to external hosts.
- It does not collect telemetry.
- It does not store secrets, tokens, or credentials.
- It does not commit or require machine-specific absolute paths.
- It does not require admin rights unless you try to close a process that Windows protects.

## Stack

- Python
- `customtkinter` for the desktop UI
- `psutil` for socket and process inspection
- `PyInstaller` for a portable `EasyLocalhost.exe`

## Run In Development

```powershell
python -m pip install -r requirements.txt
python src\main.py
```

## Build The Portable EXE

```powershell
.\build.ps1
```

The generated binary is:

```text
dist\EasyLocalhost.exe
```

## Windows SmartScreen

The portable EXE is unsigned. Microsoft SmartScreen may show a warning for new unsigned apps until the file builds reputation or is code-signed with a paid certificate. This is normal for independent open-source Windows binaries and cannot be fully eliminated from code alone.

For verification, compare the SHA256 hash published in each GitHub Release with the downloaded file:

```powershell
Get-FileHash .\EasyLocalhost.exe -Algorithm SHA256
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Security Checks

```powershell
python -m pip install -r requirements-dev.txt
python -m bandit -r src -q
python -m pip_audit -r requirements.txt
```

## Release Automation

This repo includes a GitHub Actions workflow that can be triggered manually to:

- runs tests on Windows
- runs static security checks
- audits Python dependencies
- builds the portable executable
- uploads the executable as an artifact
- can publish the executable to a GitHub Release when you run it against a tagged commit

## Project Structure

```text
assets/                  App icon assets
src/
  actions.py            Safe user actions for localhost entries
  app.py                Desktop UI
  controller.py         Monitor orchestration
  health_checker.py     HTTP probing
  models.py             Core data models
  project_mapper.py     Project/repository detection
  scanner.py            Port and process discovery
  utils.py              Shared constants and helpers
tests/                  Unit tests for core logic
build.ps1               Local build script
EasyLocalhost.spec      PyInstaller build definition
```

## Current Scope

This project is intentionally only a localhost controller.

It is not:

- a reverse proxy
- a local tunnel
- a traffic inspector
- a port scanner for external networks
- a project launcher/orchestrator
- a telemetry collector

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
