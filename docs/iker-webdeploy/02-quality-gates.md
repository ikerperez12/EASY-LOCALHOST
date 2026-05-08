# 02 - Quality Gates

| Gate | Command | Status |
|---|---|---|
| Unit tests | `python -m unittest discover -s tests -v` | Passed: 12 tests OK |
| Static security | `python -m bandit -r src -q` | Passed |
| Dependency audit | `python -m pip_audit -r requirements.txt` | Passed: no known vulnerabilities found |
| Build | `.\build.ps1` | Passed |
| EXE smoke test | `Start-Process .\dist\EasyLocalhost.exe` | Passed |

## Manual QA checklist

- Fresh scan renders folders collapsed: Passed by scripted check.
- Expand and Collapse buttons still work: No verificado manually in this document.
- Opening a single folder works: No verificado manually in this document.
- Rows show `File:` when a real command file is detected: Covered by unit test at model level.
- Rows show `Path:` when only a folder/process path is available: No verificado manually in this document.
- Default window is taller than the previous `560x720` layout: Passed by code inspection and preview.
