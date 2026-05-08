# 02 - Quality Gates

| Gate | Command | Status |
|---|---|---|
| Unit tests | `python -m unittest discover -s tests -v` | Passed: 12 tests OK |
| Static security | `python -m bandit -r src -q` | Passed |
| Dependency audit | `python -m pip_audit -r requirements.txt` | Passed: no known vulnerabilities found |
| Build | `.\build.ps1` | Passed for `3.0.3` |
| EXE smoke test | `Start-Process .\dist\EasyLocalhost.exe` | Passed |

## Manual QA checklist

- Fresh scan renders folders collapsed: Passed by preview capture and existing unit coverage.
- Header and controls are less invasive than `3.0.2`: Passed by preview capture.
- Expand and Collapse buttons remain available from the summary bar: Passed by code inspection and preview capture.
- Opening a single folder works: No verificado manually in this document.
- Rows show `File:` when a real command file is detected: Covered by unit test at model level.
- Rows show `Path:` when only a folder/process path is available: No verificado manually in this document.
- Default window is smaller than `3.0.2` while preserving vertical scroll space: Passed by code inspection and preview.
- Portable EXE SHA256 for local `3.0.3` build: `EC2A93F20AB0779F810C08706E430507DFED3A05F4D4D8A3895E95ECCC5A2CBA`.
