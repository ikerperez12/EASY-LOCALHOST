# Easy Localhost

Easy Localhost is a compact Windows desktop controller for local development servers.
It keeps a live view of the localhost ports you actually care about, shows which project they belong to, and lets you act on them without dropping to terminal commands.

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

## Tests

```powershell
python -m unittest discover -s tests -v
```

## Release Automation

This repo includes a GitHub Actions workflow that can be triggered manually to:

- runs tests on Windows
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
