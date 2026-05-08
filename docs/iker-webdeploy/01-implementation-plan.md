# 01 - Implementation Plan

## Objective

Improve usability without expanding product scope:

- Start all localhost folders collapsed by default.
- Increase the default window height and slightly increase width.
- Show more precise source file paths when command arguments reference a real file.
- Improve project mapping when `cwd` is too generic.

## Files likely touched

- `src/app.py`
- `src/models.py`
- `src/project_mapper.py`
- `src/presentation_state.py`
- `tests/test_project_mapper.py`
- `tests/test_refresh_modes.py`
- `README.md`
- `CHANGELOG.md`
- `file_version_info.txt`
- `src/utils.py`

## Gates

- Unit tests pass.
- Bandit passes.
- pip-audit passes.
- Portable EXE builds.
- EXE starts and stays open.

## Rollback

- Revert this iteration commit.
- If source path mapping over-prioritizes command files, restore prior `cwd`-first mapper behavior.
