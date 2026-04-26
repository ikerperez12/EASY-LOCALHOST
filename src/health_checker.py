"""
Health checker for Easy Localhost.

The checker only connects to 127.0.0.1 and never probes external hosts.
"""

import http.client
import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from models import PortInfo, PortStatus
from utils import APP_VERSION, HEALTH_CHECK_TIMEOUT, MAX_CONCURRENT_CHECKS

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_CHECKS,
    thread_name_prefix="health",
)


def check_ports_health(ports: list[PortInfo]) -> list[PortInfo]:
    """
    Check multiple localhost ports concurrently.

    HTTP responses, including HTTP error responses, indicate an active local
    web server. Non-HTTP listeners are still shown as listening.
    """
    if not ports:
        return ports

    futures = {
        _executor.submit(_check_single_port, port_info.port): port_info
        for port_info in ports
    }

    for future in as_completed(futures):
        port_info = futures[future]
        try:
            status, http_code = future.result()
            port_info.status = status
            port_info.http_status_code = http_code
        except Exception as exc:
            logger.debug("Health check failed for port %s: %s", port_info.port, exc)
            port_info.status = PortStatus.LISTENING

    return ports


def _check_single_port(port: int) -> tuple[PortStatus, Optional[int]]:
    """Check whether a single localhost port responds to HTTP."""
    if not _is_port_open(port):
        return PortStatus.ZOMBIE, None

    connection: http.client.HTTPConnection | None = None
    try:
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            port,
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        connection.request(
            "HEAD",
            "/",
            headers={
                "User-Agent": f"EasyLocalhost/{APP_VERSION} HealthCheck",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        response.read()
        return PortStatus.ACTIVE, response.status
    except (http.client.HTTPException, OSError, socket.timeout):
        return PortStatus.LISTENING, None
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as exc:
                logger.debug("Failed to close health-check connection: %s", exc)


def _is_port_open(port: int) -> bool:
    """Quick TCP socket check against loopback."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", port))
            return result == 0
    except Exception:
        return False
