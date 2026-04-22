"""
Port scanner for Easy Localhost.

The scanner only reads local listening sockets and the metadata of their owning
processes. It never modifies files, processes, or network configuration.
"""

import logging
import os
from typing import Optional

import psutil

from models import PortInfo, PortStatus

logger = logging.getLogger(__name__)

LOCAL_BIND_IPV4 = ".".join(("0", "0", "0", "0"))
LOCAL_BIND_IPV6 = "::"
LOOPBACK_OR_LOCAL_BIND_ADDRESSES = (
    "127.0.0.1",
    "::1",
    LOCAL_BIND_IPV4,
    LOCAL_BIND_IPV6,
)


def scan_localhost_ports() -> list[PortInfo]:
    """
    Scan all listening localhost ports and resolve their owner process.

    The scan is read-only and intentionally limited to loopback or "bind all"
    addresses so it stays focused on local development servers.
    """
    ports_map: dict[int, PortInfo] = {}

    try:
        connections = psutil.net_connections(kind="inet")
    except psutil.AccessDenied:
        logger.warning("Access denied when scanning connections.")
        return []
    except Exception as exc:
        logger.error("Error scanning connections: %s", exc)
        return []

    for conn in connections:
        if conn.status != psutil.CONN_LISTEN:
            continue

        if not conn.laddr:
            continue

        local_ip = conn.laddr.ip
        if local_ip not in LOOPBACK_OR_LOCAL_BIND_ADDRESSES:
            continue

        port = conn.laddr.port
        pid = conn.pid

        # Avoid duplicate IPv4/IPv6 entries for the same port.
        if port in ports_map or pid in (None, 0):
            continue

        port_info = _resolve_process(port, pid)
        if port_info:
            ports_map[port] = port_info

    return sorted(ports_map.values(), key=lambda item: (item.port, item.pid))


def _resolve_process(port: int, pid: int) -> Optional[PortInfo]:
    """Resolve process details for a listening port."""
    try:
        proc = psutil.Process(pid)

        process_name = _safe_get(proc, "name", "Unknown")
        exe_path = _safe_get(proc, "exe", "")
        cwd = _safe_get(proc, "cwd", "")

        try:
            cmdline = proc.cmdline()
            command_args = tuple(cmdline) if cmdline else ()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            command_args = ()

        command_line = " ".join(command_args) if command_args else ""

        if not cwd:
            cwd = _infer_working_directory(command_args, exe_path)

        return PortInfo(
            port=port,
            pid=pid,
            process_name=process_name,
            exe_path=exe_path,
            cwd=cwd,
            project_name="",
            project_root="",
            status=PortStatus.LISTENING,
            protocol="TCP",
            command_line=command_line,
            command_args=command_args,
        )
    except psutil.NoSuchProcess:
        logger.debug("Process %s no longer exists (port %s).", pid, port)
        return None
    except psutil.AccessDenied:
        return PortInfo(
            port=port,
            pid=pid,
            process_name="[Access Denied]",
            exe_path="",
            cwd="",
            project_name="",
            project_root="",
            status=PortStatus.UNKNOWN,
            protocol="TCP",
            command_line="",
            command_args=(),
        )
    except Exception as exc:
        logger.error("Error resolving process %s on port %s: %s", pid, port, exc)
        return None


def _safe_get(proc: psutil.Process, attr: str, default: str = "") -> str:
    """Safely read a process attribute."""
    try:
        member = getattr(proc, attr)
        value = member() if callable(member) else member
        return str(value) if value else default
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return default


def _infer_working_directory(command_args: tuple[str, ...], exe_path: str) -> str:
    """
    Infer a usable working directory when psutil cannot expose cwd().

    The result is best-effort and always constrained to existing local paths.
    """
    for arg in command_args[1:]:
        if not arg or arg.startswith("-"):
            continue

        candidate = arg.strip('"')
        if not os.path.exists(candidate):
            continue

        if os.path.isdir(candidate):
            return candidate

        if os.path.isfile(candidate):
            return os.path.dirname(candidate)

    if exe_path:
        exe_dir = os.path.dirname(exe_path)
        if exe_dir and os.path.isdir(exe_dir):
            return exe_dir

    return ""
