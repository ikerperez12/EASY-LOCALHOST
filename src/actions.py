"""
User-triggered actions for Easy Localhost.

Every action is intentionally narrow:
- open localhost URLs
- open a local folder
- terminate a process tree

No action edits project files or reaches external hosts.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import webbrowser
from typing import Optional

import psutil

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ActionResult:
    """Result of a user action."""

    success: bool
    message: str = ""


def open_in_browser(port: int) -> ActionResult:
    """Open ``http://localhost:{port}`` in Chrome when available."""
    if not isinstance(port, int) or not 1 <= port <= 65535:
        return ActionResult(False, f"Invalid port number: {port}")

    url = f"http://localhost:{port}"

    try:
        chrome_path = _find_chrome()
        if chrome_path:
            webbrowser.register(
                "chrome",
                None,
                webbrowser.BackgroundBrowser(chrome_path),
                preferred=True,
            )
            webbrowser.get("chrome").open(url)
        else:
            webbrowser.open(url)
        logger.info("Opened %s", url)
        return ActionResult(True, f"Opened {url}")
    except Exception as exc:
        logger.error("Failed to open browser for port %s: %s", port, exc)
        return ActionResult(False, f"Failed to open browser: {exc}")


def open_in_folder(path: str) -> ActionResult:
    """Open a local folder in Windows Explorer."""
    if not path:
        return ActionResult(False, "No project folder was resolved for this process.")

    target = path if os.path.isdir(path) else os.path.dirname(path)
    if not target or not os.path.isdir(target):
        return ActionResult(False, "The resolved project folder no longer exists.")

    try:
        # The target is validated as an existing local directory above.
        os.startfile(target)  # nosec B606
        return ActionResult(True, f"Opened {target}")
    except Exception as exc:
        logger.error("Failed to open folder %s: %s", target, exc)
        return ActionResult(False, f"Failed to open folder: {exc}")


def kill_process_tree(pid: int) -> ActionResult:
    """Terminate a process and every child process it spawned."""
    if not isinstance(pid, int) or pid <= 0:
        return ActionResult(False, f"Invalid PID: {pid}")

    try:
        parent = psutil.Process(pid)
        process_name = parent.name()
        children = parent.children(recursive=True)

        for child in children:
            _terminate_softly(child)

        _terminate_softly(parent)

        tracked = children + [parent]
        _, alive = psutil.wait_procs(tracked, timeout=3)

        for proc in alive:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return ActionResult(True, f"Closed {process_name}")
    except psutil.NoSuchProcess:
        return ActionResult(True, "Process already terminated.")
    except psutil.AccessDenied:
        return ActionResult(
            False,
            "Access denied. Try running Easy Localhost as administrator for this process.",
        )
    except Exception as exc:
        logger.error("Failed to kill process tree %s: %s", pid, exc)
        return ActionResult(False, f"Failed to close process: {exc}")


def _terminate_softly(process: psutil.Process) -> None:
    """Try graceful termination and ignore expected race conditions."""
    try:
        process.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return


def _find_chrome() -> Optional[str]:
    """Best-effort Chrome discovery on Windows."""
    candidates = [
        os.path.join(
            os.environ.get("ProgramFiles", ""),
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
        ),
        os.path.join(
            os.environ.get("ProgramFiles(x86)", ""),
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
        ),
        os.path.join(
            os.environ.get("LocalAppData", ""),
            "Google",
            "Chrome",
            "Application",
            "chrome.exe",
        ),
    ]

    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate

    return None
