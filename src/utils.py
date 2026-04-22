"""
Utility functions for Easy Localhost.
Handles resource paths for PyInstaller compatibility and app constants.
"""

import os
import sys


# Application metadata
APP_NAME = "Easy Localhost"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Iker"

# Default scan interval in milliseconds
DEFAULT_SCAN_INTERVAL = 2000

# HTTP health check timeout in seconds
HEALTH_CHECK_TIMEOUT = 1.0

# Maximum concurrent health checks
MAX_CONCURRENT_CHECKS = 10


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource, works for both development and PyInstaller builds.
    
    When packaged with PyInstaller --onefile, resources are extracted to a temp folder
    referenced by sys._MEIPASS. In development, uses the project root.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # Running in development - go up one level from src/
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def get_assets_path() -> str:
    """Returns the path to the assets directory."""
    return resource_path("assets")


def get_icon_path(ext: str = "ico") -> str:
    """Returns the path to the app icon file."""
    return os.path.join(get_assets_path(), f"icon.{ext}")


def truncate_path(path: str, max_length: int = 40) -> str:
    """
    Truncates a file path for display, keeping the most relevant parts.
    Example: drive\\workspace\\...\\project\\src
    """
    if len(path) <= max_length:
        return path
    
    parts = path.replace("/", "\\").split("\\")
    if len(parts) <= 3:
        return path[:max_length - 3] + "..."
    
    # Keep drive + first dir + ... + last 2 dirs
    return f"{parts[0]}\\{parts[1]}\\...\\{parts[-2]}\\{parts[-1]}"


def format_port(port: int) -> str:
    """Formats port number for display with colon prefix."""
    return f":{port}"
