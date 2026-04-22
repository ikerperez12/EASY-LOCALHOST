"""
Health Checker for Easy Localhost.
Probes localhost ports to determine if they are serving HTTP responses.

SECURITY: Only connects to 127.0.0.1. Never makes external network requests.
"""

import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from models import PortInfo, PortStatus
from utils import HEALTH_CHECK_TIMEOUT, MAX_CONCURRENT_CHECKS

logger = logging.getLogger(__name__)

# Reusable thread pool for health checks
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CHECKS, thread_name_prefix="health")


def check_ports_health(ports: list[PortInfo]) -> list[PortInfo]:
    """
    Check the health of multiple ports concurrently.
    Updates the status and http_status_code fields of each PortInfo.
    
    Uses a thread pool for parallel HTTP probes to keep total check time low.
    """
    if not ports:
        return ports
    
    futures = {}
    for port_info in ports:
        future = _executor.submit(_check_single_port, port_info.port)
        futures[future] = port_info
    
    for future in as_completed(futures):
        port_info = futures[future]
        try:
            status, http_code = future.result()
            port_info.status = status
            port_info.http_status_code = http_code
        except Exception as e:
            logger.debug(f"Health check failed for port {port_info.port}: {e}")
            port_info.status = PortStatus.LISTENING
    
    return ports


def _check_single_port(port: int) -> tuple[PortStatus, Optional[int]]:
    """
    Check if a single localhost port is responding to HTTP requests.
    
    Returns:
        Tuple of (PortStatus, HTTP status code or None)
    """
    # First, do a quick socket check
    if not _is_port_open(port):
        return PortStatus.ZOMBIE, None
    
    # Try HTTP probe
    url = f"http://127.0.0.1:{port}/"
    try:
        req = Request(url, method='HEAD')
        req.add_header('User-Agent', 'EasyLocalhost/1.0 HealthCheck')
        req.add_header('Connection', 'close')
        
        with urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as response:
            return PortStatus.ACTIVE, response.status
    except HTTPError as e:
        # HTTP error responses still mean the server is active
        return PortStatus.ACTIVE, e.code
    except URLError:
        # Server is listening but not responding to HTTP (could be WebSocket, gRPC, etc.)
        return PortStatus.LISTENING, None
    except Exception:
        return PortStatus.LISTENING, None


def _is_port_open(port: int) -> bool:
    """Quick TCP socket check to verify if a port is accepting connections."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            result = sock.connect_ex(('127.0.0.1', port))
            return result == 0
    except Exception:
        return False
