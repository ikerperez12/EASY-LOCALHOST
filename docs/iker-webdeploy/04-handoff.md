# 04 - Handoff

## Changes in this iteration

- Folders are collapsed by default.
- Default window geometry is larger and taller.
- Source display prefers exact command files when available.
- Project mapping avoids generic folders when command arguments point into a real project.

## Verification

- `python -m unittest discover -s tests -v`: passed, 12 tests.
- `python -m bandit -r src -q`: passed.
- `python -m pip_audit -r requirements.txt`: passed, no known vulnerabilities found.
- `.\build.ps1`: passed.
- `dist\EasyLocalhost.exe`: starts and stays open in smoke test.
- Temporary `127.0.0.1:8765` server: detected as active with HTTP 204.
- SHA256: `7149D02A48805B522E85CD7C631B8D713493BC16B3D03BAD225555F4ED4BC1C3`.

## Remaining risks

- Accessibility of canvas-based rows remains manually verified only.
- Unsigned Windows executable can still trigger SmartScreen.
- Branch protection is not part of this iteration.
