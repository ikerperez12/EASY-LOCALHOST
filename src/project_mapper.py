"""
Project mapping helpers for Easy Localhost.

These helpers are strictly read-only. They inspect local directories to infer
which repository or project likely owns a listening localhost process.
"""

import configparser
import json
import logging
import os
from functools import lru_cache
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

IGNORED_PATH_SEGMENTS = {
    "node_modules",
    ".venv",
    "venv",
    "site-packages",
    "dist",
    "build",
    "__pycache__",
}

PROJECT_MARKERS = (
    ".git",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "docker-compose.yml",
    "Dockerfile",
)


def identify_project_from_process(
    cwd: str, command_args: tuple[str, ...] = (), exe_path: str = ""
) -> tuple[str, str]:
    """
    Return ``(project_name, project_root)`` for a process.

    ``cwd`` is trusted first because it is the most reliable origin for dev
    servers. Command-line paths are only used as a fallback when cwd is absent
    or points to a transient runtime folder.
    """
    for candidate in _candidate_roots(cwd, command_args, exe_path):
        project_root = find_project_root(candidate)
        if not project_root:
            continue
        return identify_project(project_root), project_root

    fallback = _normalize_existing_dir(cwd) or _normalize_existing_dir(exe_path)
    if fallback:
        return identify_project(fallback), fallback

    return "Unknown", ""


@lru_cache(maxsize=512)
def find_project_root(start_path: str) -> str:
    """Walk up from a path until a recognizable project root is found."""
    current = _normalize_existing_dir(start_path)
    if not current:
        return ""

    max_depth = 12
    for _ in range(max_depth):
        if _looks_like_project_root(current):
            return current

        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    return _normalize_existing_dir(start_path) or ""


@lru_cache(maxsize=512)
def identify_project(path: str) -> str:
    """Return the best available project name for an already resolved root."""
    root = find_project_root(path)
    if not root:
        return "Unknown"

    git_name = _check_git_repo(root)
    if git_name:
        return git_name

    package_name = _check_package_json(root)
    if package_name:
        return package_name

    return os.path.basename(root) or "Unknown"


def _candidate_roots(
    cwd: str, command_args: tuple[str, ...], exe_path: str
) -> Iterable[str]:
    """Yield possible project roots in descending reliability order."""
    seen: set[str] = set()

    for raw in (cwd,):
        normalized = _normalize_existing_dir(raw)
        if normalized and normalized not in seen:
            seen.add(normalized)
            yield normalized

    for raw in command_args[1:]:
        candidate = _normalize_existing_dir(raw)
        if not candidate:
            candidate = _normalize_existing_dir(os.path.dirname(raw.strip('"')))
        if not candidate or _is_ignored_runtime_path(candidate) or candidate in seen:
            continue
        seen.add(candidate)
        yield candidate

    exe_dir = _normalize_existing_dir(exe_path)
    if exe_dir and not _is_ignored_runtime_path(exe_dir) and exe_dir not in seen:
        yield exe_dir


def _normalize_existing_dir(path: str) -> str:
    """Normalize a path to an existing directory."""
    if not path:
        return ""

    cleaned = os.path.normpath(path.strip('"'))
    if os.path.isdir(cleaned):
        return cleaned
    if os.path.isfile(cleaned):
        return os.path.dirname(cleaned)
    return ""


def _is_ignored_runtime_path(path: str) -> bool:
    """Skip package caches and runtime folders that are not project roots."""
    parts = {segment.lower() for segment in path.replace("/", "\\").split("\\")}
    return any(segment in parts for segment in IGNORED_PATH_SEGMENTS)


def _looks_like_project_root(directory: str) -> bool:
    """Check whether a directory contains common project markers."""
    for marker in PROJECT_MARKERS:
        if os.path.exists(os.path.join(directory, marker)):
            return True

    try:
        for entry in os.scandir(directory):
            if entry.is_file() and entry.name.endswith(".sln"):
                return True
    except OSError:
        return False

    return False


def _check_git_repo(directory: str) -> Optional[str]:
    """Extract a readable repository name from a local Git root."""
    git_dir = os.path.join(directory, ".git")
    if not os.path.isdir(git_dir):
        return None

    config_path = os.path.join(git_dir, "config")
    if os.path.isfile(config_path):
        try:
            config = configparser.ConfigParser()
            config.read(config_path, encoding="utf-8")
            if config.has_section('remote "origin"'):
                url = config.get('remote "origin"', "url", fallback="")
                repo_name = _extract_repo_name_from_url(url)
                if repo_name:
                    return repo_name
        except Exception as exc:
            logger.debug("Failed to read Git config from %s: %s", config_path, exc)

    return os.path.basename(directory)


def _extract_repo_name_from_url(url: str) -> Optional[str]:
    """Extract the repository segment from a Git remote URL."""
    if not url:
        return None

    value = url.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]

    if "/" in value:
        tail = value.rsplit("/", 1)[-1]
        if tail:
            return tail

    if ":" in value:
        tail = value.rsplit(":", 1)[-1]
        if tail:
            return tail

    return None


def _check_package_json(directory: str) -> Optional[str]:
    """Read the ``name`` field from ``package.json`` when present."""
    package_path = os.path.join(directory, "package.json")
    if not os.path.isfile(package_path):
        return None

    try:
        with open(package_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None

    name = str(data.get("name") or "").strip()
    if not name:
        return None
    if "/" in name:
        return name.split("/")[-1]
    return name


def clear_cache() -> None:
    """Reset cached project resolution results."""
    find_project_root.cache_clear()
    identify_project.cache_clear()
