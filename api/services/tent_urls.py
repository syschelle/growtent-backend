"""Validation of administrator-configured controller and camera source URLs.

A syntactically safe URL is necessary but not sufficient for network isolation:
DNS is rechecked before outbound calls, redirects are forbidden, and deployments
should restrict the API/go2rtc containers' egress to the trusted device LAN.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from services.air_sensor_service import is_safe_lan_ip

_DENIED_HOSTS = frozenset({
    "localhost", "db", "gt_db", "postgres", "postgresql",
    "go2rtc", "gt_go2rtc", "api", "gt_api", "host.docker.internal",
    "gateway.docker.internal", "metadata.google.internal",
})


def _validate_host(host: str, *, resolve: bool) -> None:
    hostname = host.lower().rstrip('.')
    if (hostname in _DENIED_HOSTS or hostname.endswith('.docker.internal')
            or hostname.endswith('.localhost') or hostname.endswith('.internal')):
        raise ValueError('Internal service hosts are not allowed as device targets')
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        if not hostname or '.' not in hostname or hostname.startswith('.'):
            raise ValueError('Device host must be an IP address or a qualified hostname')
        if not resolve:
            return
        try:
            addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(hostname, None)}
        except (socket.gaierror, ValueError, OSError):
            raise ValueError('Device hostname cannot be resolved') from None
        if not addresses or not all(is_safe_lan_ip(str(ip)) for ip in addresses):
            raise ValueError('Device hostname resolves to an unsafe IP address')
    else:
        if not is_safe_lan_ip(str(address)):
            raise ValueError('Device IP address must be a private, non-reserved LAN address')


def _validate_url(raw: str, schemes: set[str], *, resolve: bool, allow_credentials: bool) -> str:
    value = str(raw or '').strip()
    if not value or len(value) > 2048 or any(ord(ch) < 32 or ch == '\\' for ch in value):
        raise ValueError('Invalid device URL')
    try:
        url = urlsplit(value)
        port = url.port  # Forces invalid port validation.
        hostname = url.hostname
    except ValueError:
        raise ValueError('Invalid device URL') from None
    if url.scheme.lower() not in schemes or not hostname or (port is not None and port == 0):
        raise ValueError('Unsupported device URL scheme or host')
    if not allow_credentials and (url.username is not None or url.password is not None):
        raise ValueError('Controller URL must not embed credentials')
    if url.fragment:
        raise ValueError('Device URL fragments are not supported')
    _validate_host(hostname, resolve=resolve)
    return value


def validate_source_url(raw: str, *, resolve: bool = False) -> str:
    """Only HTTP(S) device sources, never Docker-local or public targets."""
    return _validate_url(raw, {'http', 'https'}, resolve=resolve, allow_credentials=False)


def validate_rtsp_url(raw: str | None, *, resolve: bool = False) -> str | None:
    """Go2rtc receives only genuine RTSP(S) sources, never exec/ffmpeg/etc."""
    if not raw:
        return None
    return _validate_url(raw, {'rtsp', 'rtsps'}, resolve=resolve, allow_credentials=True)
