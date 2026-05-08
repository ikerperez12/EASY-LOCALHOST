"""
Data models for Easy Localhost.
Defines the core data structures used throughout the application.
"""

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Optional


class PortStatus(Enum):
    """Status classification for a monitored port."""
    ACTIVE = "active"           # Port responds to HTTP requests
    LISTENING = "listening"     # Port open but no HTTP response (non-HTTP service)
    ZOMBIE = "zombie"           # Process exists but unresponsive
    UNKNOWN = "unknown"         # Could not determine status


class RefreshMode(Enum):
    """Available UI refresh modes for the desktop controller."""

    AUTO = "auto"
    FIXED_10S = "10s"
    FIXED_5S = "5s"
    MANUAL = "manual"


_REFRESH_MODE_ORDER = (
    RefreshMode.AUTO,
    RefreshMode.FIXED_10S,
    RefreshMode.FIXED_5S,
    RefreshMode.MANUAL,
)

_REFRESH_INTERVALS_MS = {
    RefreshMode.AUTO: 7000,
    RefreshMode.FIXED_10S: 10000,
    RefreshMode.FIXED_5S: 5000,
    RefreshMode.MANUAL: None,
}

_REFRESH_BUTTON_LABELS = {
    RefreshMode.AUTO: "Refresh: Auto",
    RefreshMode.FIXED_10S: "Refresh: 10s",
    RefreshMode.FIXED_5S: "Refresh: 5s",
    RefreshMode.MANUAL: "Refresh: Manual",
}

_REFRESH_STATUS_LABELS = {
    RefreshMode.AUTO: "Auto (7s)",
    RefreshMode.FIXED_10S: "10s",
    RefreshMode.FIXED_5S: "5s",
    RefreshMode.MANUAL: "Manual",
}


def next_refresh_mode(mode: RefreshMode) -> RefreshMode:
    """Cycles through the supported refresh modes in UI order."""
    index = _REFRESH_MODE_ORDER.index(mode)
    return _REFRESH_MODE_ORDER[(index + 1) % len(_REFRESH_MODE_ORDER)]


def refresh_interval_for_mode(mode: RefreshMode) -> Optional[int]:
    """Returns the effective refresh interval for the given mode."""
    return _REFRESH_INTERVALS_MS[mode]


def refresh_button_label(mode: RefreshMode) -> str:
    """Returns the button label shown in the header for the refresh mode."""
    return _REFRESH_BUTTON_LABELS[mode]


def refresh_status_label(mode: RefreshMode) -> str:
    """Returns the compact status text shown in footer/summary areas."""
    return _REFRESH_STATUS_LABELS[mode]


@dataclass
class PortInfo:
    """Represents a single monitored localhost port and its associated process."""
    port: int
    pid: int
    process_name: str
    exe_path: str
    cwd: str
    project_name: str
    status: PortStatus
    protocol: str = "TCP"
    project_root: str = ""
    command_line: Optional[str] = None
    command_args: tuple[str, ...] = field(default_factory=tuple)
    http_status_code: Optional[int] = None

    @property
    def url(self) -> str:
        """Returns the localhost URL for this port."""
        return f"http://localhost:{self.port}"

    @property
    def display_name(self) -> str:
        """Returns the best available display name for this port's project."""
        if self.project_name and self.project_name != "Unknown":
            return self.project_name
        return self.process_name

    @property
    def launch_path(self) -> str:
        """Returns the best available local path for project actions."""
        return self.project_root or self.cwd or self.exe_path

    @property
    def command_file_path(self) -> str:
        """Returns the first existing file referenced by the command line."""
        for raw_arg in self.command_args[1:]:
            if not raw_arg or raw_arg.startswith("-"):
                continue

            cleaned = raw_arg.strip('"')
            candidates = [cleaned]
            if self.cwd and not os.path.isabs(cleaned):
                candidates.append(os.path.join(self.cwd, cleaned))

            for candidate in candidates:
                normalized = os.path.normpath(candidate)
                if os.path.isfile(normalized):
                    return normalized

        return ""

    @property
    def source_display_path(self) -> str:
        """Returns the most precise path to show in the UI."""
        return self.command_file_path or self.project_root or self.cwd or self.exe_path

    @property
    def command_preview(self) -> str:
        """Returns a short command line preview for the UI."""
        if self.command_line:
            return self.command_line
        if self.command_args:
            return " ".join(self.command_args)
        return ""

    def __eq__(self, other):
        if not isinstance(other, PortInfo):
            return False
        return self.port == other.port and self.pid == other.pid

    def __hash__(self):
        return hash((self.port, self.pid))


@dataclass
class AppState:
    """Global application state."""
    ports: list[PortInfo] = field(default_factory=list)
    last_scan_time: Optional[float] = None
    refresh_mode: RefreshMode = RefreshMode.AUTO
    is_scanning: bool = False
    always_on_top: bool = True
    total_scans: int = 0

    @property
    def scan_interval_ms(self) -> Optional[int]:
        """Returns the active interval in milliseconds, if auto-refresh is enabled."""
        return refresh_interval_for_mode(self.refresh_mode)

    @property
    def refresh_button_text(self) -> str:
        """Returns the header button text for the active refresh mode."""
        return refresh_button_label(self.refresh_mode)

    @property
    def refresh_status_text(self) -> str:
        """Returns the compact footer/status text for the active refresh mode."""
        return refresh_status_label(self.refresh_mode)
