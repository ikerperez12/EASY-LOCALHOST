# 00 - Audit

## Project classification

- Pattern: local-first desktop utility.
- Product: Easy Localhost, a Windows localhost controller.
- Deploy provider: GitHub Releases, not Vercel.
- Vercel files: No encontrado.
- Backend: No remote backend. Local core only.

## Evidence checked

- `git status -sb`
- `git branch --show-current`
- `git remote -v`
- `src/app.py`
- `src/models.py`
- `src/project_mapper.py`
- `src/presentation_state.py`
- `tests/*`
- `README.md`
- `CHANGELOG.md`
- `file_version_info.txt`

## Current iteration risks

- Dense localhost sessions must stay collapsed by default.
- Source path display must avoid stopping at a generic user/root folder when a real command file is available.
- Canvas rows improve performance but remain a desktop UI accessibility area to review manually.
