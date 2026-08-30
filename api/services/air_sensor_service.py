from __future__ import annotations

import ipaddress
import math
import socket
import time
from datetime import datetime, timezone
from typing import Callable, Mapping
from urllib.parse import urlsplit

import httpx

from models.schemas import AirSensorCurrent, AirSensorSettings

SUCCESS_CACHE_SECONDS = 180.0
ERROR_RETRY_SECONDS = 30.0
HTTP_TIMEOUT_SECONDS = 2.5
AIR_SENSOR_PATH = "/data.json"


Resolver = Callable[[str], list[str]]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_float(value: object) -> float | None:
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def parse_int(value: object) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return int(parsed)


def normalize_air_sensor_host(raw_host: str | None) -> str | None:
    value = str(raw_host or "").strip()
    if not value:
        return None
    probe = value if "://" in value else f"http://{value}"
    parts = urlsplit(probe)
    if parts.scheme not in {"http", ""}:
        raise ValueError("Only http sensor hosts are supported")
    if parts.username or parts.password:
        raise ValueError("Sensor host must not contain credentials")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise ValueError("Configure only the sensor host, not a path")
    host = parts.hostname
    if not host:
        raise ValueError("Sensor host is required")
    port = parts.port
    normalized_host = host.strip("[]").lower()
    if not normalized_host:
        raise ValueError("Sensor host is required")
    if port is not None:
        if port < 1 or port > 65535:
            raise ValueError("Sensor port is invalid")
        return f"{normalized_host}:{port}"
    return normalized_host


def default_resolver(hostname: str) -> list[str]:
    return sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})


def is_safe_lan_ip(value: str) -> bool:
    ip = ipaddress.ip_address(value)
    if not ip.is_private:
        return False
    blocked = (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )
    if blocked:
        return False
    if ip.version == 4 and ip == ipaddress.ip_address("169.254.169.254"):
        return False
    return True


def validate_safe_sensor_host(host: str, resolver: Resolver = default_resolver) -> str:
    normalized = normalize_air_sensor_host(host)
    if not normalized:
        raise ValueError("Sensor host is required")
    hostname = normalized.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(hostname.strip("[]"))
        addresses = [hostname.strip("[]")]
    except ValueError:
        addresses = resolver(hostname)
    if not addresses:
        raise ValueError("Sensor host could not be resolved")
    unsafe = [ip for ip in addresses if not is_safe_lan_ip(ip)]
    if unsafe:
        raise ValueError("Sensor host resolves to an unsafe address")
    return normalized


def parse_air_sensor_payload(payload: Mapping[str, object]) -> dict[str, object]:
    values: dict[str, object] = {
        "temperature_c": None,
        "humidity_percent": None,
        "sds_p1": None,
        "sds_p2": None,
        "age_seconds": parse_int(payload.get("age")),
        "software_version": str(payload.get("software_version") or "").strip() or None,
    }
    raw_values = payload.get("sensordatavalues")
    if not isinstance(raw_values, list):
        raw_values = []
    mapped_any = False
    value_by_type: dict[str, object] = {}
    for item in raw_values:
        if not isinstance(item, Mapping):
            continue
        value_type = str(item.get("value_type") or "").strip()
        if value_type:
            value_by_type[value_type] = item.get("value")

    mapping = {
        "sds_p1": ("SDS_P1",),
        "sds_p2": ("SDS_P2",),
        "temperature_c": ("BME280_temperature", "BMP280_temperature", "temperature"),
        "humidity_percent": ("BME280_humidity", "humidity"),
    }
    for field, keys in mapping.items():
        for key in keys:
            parsed = parse_float(value_by_type.get(key))
            if parsed is not None:
                values[field] = parsed
                mapped_any = True
                break
    if not mapped_any:
        raise ValueError("Sensor payload contained no usable measured values")
    return values


class AirSensorService:
    def __init__(
        self,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now_iso: Callable[[], str] = utc_now_iso,
        resolver: Resolver = default_resolver,
        client_factory: Callable[[], httpx.Client] | None = None,
    ):
        self._monotonic = monotonic
        self._now_iso = now_iso
        self._resolver = resolver
        self._client_factory = client_factory
        self._last_poll_at: float | None = None
        self._last_poll_ok: bool | None = None
        self._last_host: str | None = None
        self._current = AirSensorCurrent(
            enabled=False,
            configured=False,
            ok=False,
            cached=False,
        )

    def reset(self) -> None:
        self._last_poll_at = None
        self._last_poll_ok = None
        self._last_host = None
        self._current = AirSensorCurrent(
            enabled=False,
            configured=False,
            ok=False,
            cached=False,
        )

    def current(self, settings: AirSensorSettings) -> AirSensorCurrent:
        enabled = bool(settings.enabled)
        configured = bool(settings.host)
        if not enabled or not configured:
            return self._current.model_copy(
                update={
                    "enabled": enabled,
                    "configured": configured,
                    "ok": False,
                    "cached": False,
                    "last_error": None if not enabled else "Air sensor host is not configured",
                }
            )

        try:
            host = validate_safe_sensor_host(settings.host, self._resolver)
        except ValueError as exc:
            return self._with_error(enabled, configured, str(exc), cached=True)

        now = self._monotonic()
        if host != self._last_host:
            self._last_poll_at = None
            self._last_poll_ok = None
            self._last_host = host

        if self._last_poll_at is not None:
            wait = SUCCESS_CACHE_SECONDS if self._last_poll_ok else ERROR_RETRY_SECONDS
            if now - self._last_poll_at < wait:
                return self._current.model_copy(
                    update={"enabled": enabled, "configured": configured, "cached": True}
                )

        self._last_poll_at = now
        url = f"http://{host}{AIR_SENSOR_PATH}"
        try:
            with self._make_client() as client:
                response = client.get(url)
            if 300 <= response.status_code < 400:
                raise ValueError("Sensor redirects are not allowed")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, Mapping):
                raise ValueError("Sensor response is not a JSON object")
            parsed = parse_air_sensor_payload(payload)
        except Exception as exc:
            self._last_poll_ok = False
            return self._with_error(enabled, configured, self._clean_error(exc), cached=False)

        self._last_poll_ok = True
        merged = self._merge_values(parsed)
        self._current = self._current.model_copy(
            update={
                **merged,
                "enabled": enabled,
                "configured": configured,
                "ok": True,
                "cached": False,
                "last_success_at": self._now_iso(),
                "last_error": None,
            }
        )
        return self._current

    def _make_client(self) -> httpx.Client:
        if self._client_factory:
            return self._client_factory()
        return httpx.Client(
            timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS),
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json"},
        )

    def _merge_values(self, parsed: Mapping[str, object]) -> dict[str, object]:
        merged: dict[str, object] = {}
        for field in ("temperature_c", "humidity_percent", "sds_p1", "sds_p2", "age_seconds", "software_version"):
            value = parsed.get(field)
            if value is not None:
                merged[field] = value
            else:
                merged[field] = getattr(self._current, field)
        return merged

    def _with_error(self, enabled: bool, configured: bool, error: str, *, cached: bool) -> AirSensorCurrent:
        self._current = self._current.model_copy(
            update={
                "enabled": enabled,
                "configured": configured,
                "ok": False,
                "cached": cached,
                "last_error": error,
            }
        )
        return self._current

    @staticmethod
    def _clean_error(exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            return f"Sensor returned HTTP {exc.response.status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "Sensor request timed out"
        if isinstance(exc, httpx.RequestError):
            return "Sensor request failed"
        return str(exc) or "Sensor read failed"
