"""
Data models for Easy Localhost.
Defines the core data structures used throughout the application.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PortStatus(Enum):
    """Status classification for a monitored port."""
    ACTIVE = "active"           # Port responds to HTTP requests
    LISTENING = "listening"     # Port open but no HTTP response (non-HTTP service)
    ZOMBIE = "zombie"           # Process exists but unresponsive
    UNKNOWN = "unknown"         # Could not determine status


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
    scan_interval_ms: int = 2000  # 2 seconds default
    is_scanning: bool = False
    always_on_top: bool = True
    total_scans: int = 0
