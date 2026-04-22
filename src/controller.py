"""
Application controller for Easy Localhost.

This module orchestrates the read-only scan pipeline:
1. scan listening localhost ports
2. map each port to a project root/name
3. probe the port health
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from health_checker import check_ports_health
from models import PortInfo
from project_mapper import identify_project_from_process
from scanner import scan_localhost_ports


@dataclass(slots=True)
class ScanResult:
    """Snapshot produced by a single monitor cycle."""

    ports: list[PortInfo]
    elapsed_ms: float
    scanned_at: float


class LocalhostController:
    """High-level orchestration for localhost monitoring."""

    def refresh(self) -> ScanResult:
        started_at = time.perf_counter()
        timestamp = time.time()

        ports = scan_localhost_ports()
        for port_info in ports:
            project_name, project_root = identify_project_from_process(
                port_info.cwd,
                port_info.command_args,
                port_info.exe_path,
            )
            port_info.project_name = project_name
            port_info.project_root = project_root

        ports = check_ports_health(ports)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        return ScanResult(ports=ports, elapsed_ms=elapsed_ms, scanned_at=timestamp)
