from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import date
from typing import Callable
from urllib.parse import urlsplit

import httpx

WRITE_PATH = "/api/backend/grow-profile"
GROW_TARGETS_PATH = "/api/settings/grow-targets"
RUN_PROFILE_PATH = "/api/settings/run-profile"
TRANSIENT_CONFLICTS = {"grow_settings_busy", "backend_write_pending", "runtime_handoff_busy"}
AUTH_ERRORS = {
    "source_ip_not_allowed",
    "bad_signature",
    "timestamp_out_of_window",
    "missing_auth_headers",
    "invalid_auth_headers",
    "replayed_nonce",
    "backend_secret_not_configured",
    "time_not_synchronized",
}

FIELD_LABELS = {
    "targetTemperature": "target temperature",
    "targetVPD": "target VPD",
    "floweringStart": "flowering start",
    "dryingStart": "drying start",
    "currentPhase": "current phase",
}


@dataclass
class GrowWriteError(Exception):
    code: str
    message: str
    backend_status: int = 502
    controller_status: int | None = None
    request_id: int | str | None = None
    verification_ok: bool = False

    def __str__(self) -> str:
        return self.message


def normalize_controller_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("controller URL is required")
    if "://" not in raw:
        raw = f"http://{raw}"
    parts = urlsplit(raw)
    if parts.scheme.lower() != "http":
        raise ValueError("controller URL must use http")
    if not parts.hostname or parts.username or parts.password:
        raise ValueError("controller URL must contain a host and no credentials")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("controller URL contains an invalid port") from exc
    if port not in (None, 8080):
        raise ValueError("GrowTent write API uses TCP port 8080")
    host = parts.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    return f"http://{host}:8080"


def validate_secret_hex(secret_hex: str) -> str:
    secret = str(secret_hex or "").strip()
    if len(secret) != 64 or any(ch not in "0123456789abcdef" for ch in secret):
        raise ValueError("HMAC secret must be exactly 64 lowercase hexadecimal characters")
    return secret


def serialize_request_body(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")


def body_sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_string(timestamp: int | str, nonce: str, body_hash: str) -> str:
    return f"PATCH\n{WRITE_PATH}\n{timestamp}\n{nonce}\n{body_hash}"


def signature_hex(secret_hex: str, timestamp: int | str, nonce: str, body: bytes) -> str:
    key = bytes.fromhex(validate_secret_hex(secret_hex))
    body_hash = body_sha256_hex(body)
    canonical = canonical_string(timestamp, nonce, body_hash).encode("utf-8")
    return hmac.new(key, canonical, hashlib.sha256).hexdigest()


def signed_headers(secret_hex: str, body: bytes, *, timestamp: int | None = None, nonce: str | None = None) -> dict[str, str]:
    ts = int(time.time()) if timestamp is None else int(timestamp)
    request_nonce = secrets.token_hex(16) if nonce is None else str(nonce)
    if len(request_nonce) != 32 or any(ch not in "0123456789abcdef" for ch in request_nonce):
        raise ValueError("nonce must be exactly 32 lowercase hexadecimal characters")
    return {
        "Content-Type": "application/json",
        "X-GrowTent-Timestamp": str(ts),
        "X-GrowTent-Nonce": request_nonce,
        "X-GrowTent-Signature": signature_hex(secret_hex, ts, request_nonce, body),
    }


def _coerce_profile_section(payload: dict, section: str) -> dict:
    obj = payload.get(section)
    return obj if isinstance(obj, dict) else {}


def combine_read_state(grow_targets: dict, run_profile: dict) -> dict:
    stored_targets = _coerce_profile_section(grow_targets, "stored")
    runtime_targets = _coerce_profile_section(grow_targets, "runtime")
    stored_run = _coerce_profile_section(run_profile, "stored")
    runtime_run = _coerce_profile_section(run_profile, "runtime")
    return {
        "stored": {
            "targetTemperature": stored_targets.get("targetTemperature"),
            "targetVPD": stored_targets.get("targetVPD"),
            "floweringStart": stored_run.get("floweringStart", ""),
            "dryingStart": stored_run.get("dryingStart", ""),
            "currentPhase": stored_run.get("currentPhase"),
        },
        "runtime": {
            "targetTemperature": runtime_targets.get("targetTemperature"),
            "targetVPD": runtime_targets.get("targetVPD"),
            "floweringStart": runtime_run.get("floweringStart", ""),
            "dryingStart": runtime_run.get("dryingStart", ""),
            "currentPhase": runtime_run.get("currentPhase"),
        },
    }


def _date_or_none(value) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError("date values must use YYYY-MM-DD")
    if not value or value.strip() != value:
        raise ValueError("date values must use YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date values must be real calendar dates in YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise ValueError("date values must use YYYY-MM-DD")
    return parsed


def validate_patch_values(patch: dict) -> None:
    allowed = {"targetTemperature", "targetVPD", "floweringStart", "dryingStart", "currentPhase"}
    unknown = set(patch) - allowed
    if unknown:
        raise ValueError(f"unknown field: {sorted(unknown)[0]}")
    if not patch:
        raise ValueError("empty patch")
    if "targetTemperature" in patch:
        value = patch["targetTemperature"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("targetTemperature must be numeric")
        if not 18.0 <= float(value) <= 30.0:
            raise ValueError("targetTemperature must be between 18.0 and 30.0 °C")
    if "targetVPD" in patch:
        value = patch["targetVPD"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("targetVPD must be numeric")
        if not 0.50 <= float(value) <= 3.50:
            raise ValueError("targetVPD must be between 0.50 and 3.50 kPa")
    if "currentPhase" in patch:
        value = patch["currentPhase"]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("currentPhase must be an integer")
        if value not in (1, 2, 3):
            raise ValueError("currentPhase must be 1, 2 or 3")
    for key in ("floweringStart", "dryingStart"):
        if key in patch:
            value = patch[key]
            if value == "":
                raise ValueError(f"{key} must be deleted with JSON null, not an empty string")
            if value is not None:
                _date_or_none(value)


def validate_resulting_profile(patch: dict, current: dict | None = None, grow_start: str | None = None) -> None:
    validate_patch_values(patch)
    base = dict((current or {}).get("runtime") or (current or {}).get("stored") or {})
    resulting = {
        "currentPhase": base.get("currentPhase"),
        "floweringStart": base.get("floweringStart", ""),
        "dryingStart": base.get("dryingStart", ""),
    }
    for key in ("currentPhase", "floweringStart", "dryingStart"):
        if key in patch:
            resulting[key] = patch[key]

    phase = resulting.get("currentPhase")
    flowering = resulting.get("floweringStart")
    drying = resulting.get("dryingStart")
    if phase is not None:
        phase = int(phase)
        flowering_delete = "floweringStart" in patch and patch.get("floweringStart") is None
        drying_delete = "dryingStart" in patch and patch.get("dryingStart") is None
        if flowering_delete and phase != 1:
            raise ValueError("floweringStart may only be deleted when the resulting phase is 1")
        if flowering_delete and drying:
            raise ValueError("dryingStart must be cleared together with floweringStart")
        if drying_delete and phase == 3:
            raise ValueError("dryingStart may not be deleted in phase 3")
        if phase == 2 and not flowering:
            raise ValueError("floweringStart is required for phase 2")
        if phase == 3 and not flowering:
            raise ValueError("floweringStart is required for phase 3")
        if phase == 3 and not drying:
            raise ValueError("dryingStart is required for phase 3")

    flowering_date = _date_or_none(flowering)
    drying_date = _date_or_none(drying)
    grow_date = _date_or_none(grow_start) if grow_start else None
    if flowering_date and drying_date and flowering_date > drying_date:
        raise ValueError("floweringStart must be on or before dryingStart")
    if grow_date and flowering_date and grow_date > flowering_date:
        raise ValueError("grow start must be on or before floweringStart")


def _value_matches(actual, expected) -> bool:
    if expected is None:
        return actual in (None, "")
    if isinstance(expected, float):
        try:
            return abs(float(actual) - expected) <= 1e-6
        except (TypeError, ValueError):
            return False
    if isinstance(expected, int) and not isinstance(expected, bool):
        try:
            return int(actual) == expected
        except (TypeError, ValueError):
            return False
    return actual == expected


def verification_matches(state: dict, patch: dict) -> bool:
    for section_name in ("stored", "runtime"):
        section = state.get(section_name)
        if not isinstance(section, dict):
            return False
        for key, expected in patch.items():
            if not _value_matches(section.get(key), expected):
                return False
    return True


def controller_error_message(code: str, fallback: str | None = None) -> str:
    messages = {
        "backend_write_disabled": "Backend Write API is disabled on the controller.",
        "source_ip_not_allowed": "The controller rejected the backend TCP source IP. Check the allowed backend IP in GrowTent firmware.",
        "backend_secret_not_configured": "No backend HMAC secret is configured on the controller.",
        "missing_body": "The controller received no request body.",
        "body_too_large": "The controller rejected the request body as too large.",
        "content_type_must_be_application_json": "The controller requires Content-Type application/json.",
        "missing_auth_headers": "The controller reported missing authentication headers.",
        "invalid_auth_headers": "The controller reported invalid authentication headers.",
        "time_not_synchronized": "The controller time is not synchronized.",
        "timestamp_out_of_window": "The controller rejected the request timestamp. Check time synchronization on backend and controller.",
        "hash_failed": "The controller could not hash the request body.",
        "bad_signature": "The controller rejected the HMAC signature. Check that both sides use the same 64-character secret.",
        "invalid_json": "The controller rejected the JSON body.",
        "unknown_field": "The controller rejected an unknown field.",
        "empty_patch": "The controller rejected an empty PATCH request.",
        "invalid_target_temperature": "The controller rejected targetTemperature.",
        "invalid_target_vpd": "The controller rejected targetVPD.",
        "invalid_flowering_start": "The controller rejected floweringStart.",
        "invalid_drying_start": "The controller rejected dryingStart.",
        "invalid_current_phase": "The controller rejected currentPhase.",
        "target_temperature_out_of_range": "Target temperature must be between 18.0 and 30.0 °C.",
        "target_vpd_out_of_range": "Target VPD must be between 0.50 and 3.50 kPa.",
        "current_phase_out_of_range": "Current phase must be 1, 2 or 3.",
        "invalid_grow_start_state": "The controller grow start state is invalid for this change.",
        "flowering_start_required_for_phase": "Flowering start is required for the resulting phase.",
        "drying_start_required_for_phase": "Drying start is required for phase 3.",
        "flowering_start_delete_not_allowed_for_phase": "Flowering start may only be deleted in resulting phase 1.",
        "drying_start_must_be_cleared_with_flowering_start": "Drying start must be cleared together with flowering start.",
        "drying_start_delete_not_allowed_for_phase": "Drying start may not be deleted in phase 3.",
        "date_delete_requires_null": "Dates must be deleted explicitly with JSON null.",
        "invalid_date_order": "The controller rejected the date order.",
        "grow_settings_busy": "Grow settings are temporarily busy on the controller.",
        "backend_write_pending": "A previous backend write is still pending on the controller.",
        "runtime_handoff_busy": "The controller runtime handoff is temporarily busy.",
        "replayed_nonce": "The controller rejected a replayed nonce.",
    }
    return messages.get(code) or fallback or f"Controller rejected the request: {code or 'unknown error'}"


class GrowTentWriteClient:
    def __init__(
        self,
        controller_url: str,
        secret_hex: str,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        now_fn: Callable[[], float] = time.time,
        nonce_fn: Callable[[], str] | None = None,
        verification_timeout: float = 4.0,
        verification_interval: float = 0.3,
        max_attempts: int = 3,
    ):
        self.base_url = normalize_controller_url(controller_url)
        self.secret_hex = validate_secret_hex(secret_hex)
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=httpx.Timeout(4.0)))
        self.sleep_fn = sleep_fn
        self.now_fn = now_fn
        self.nonce_fn = nonce_fn or (lambda: secrets.token_hex(16))
        self.verification_timeout = max(0.0, float(verification_timeout))
        self.verification_interval = max(0.05, float(verification_interval))
        self.max_attempts = max(1, int(max_attempts))

    def _read_json(self, client: httpx.Client, path: str) -> dict:
        try:
            response = client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            data = response.json()
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            raise GrowWriteError("controller_unreachable", "GrowTent controller could not be reached.", 502) from exc
        except httpx.HTTPStatusError as exc:
            raise GrowWriteError("controller_read_failed", f"Controller read endpoint returned HTTP {exc.response.status_code}.", 502, exc.response.status_code) from exc
        except (ValueError, TypeError) as exc:
            raise GrowWriteError("controller_invalid_response", "Controller returned an invalid JSON response.", 502) from exc
        if not isinstance(data, dict):
            raise GrowWriteError("controller_invalid_response", "Controller returned an invalid JSON response.", 502)
        return data

    def read_profile(self, client: httpx.Client | None = None) -> dict:
        if client is None:
            with self.client_factory() as owned_client:
                return self.read_profile(owned_client)
        targets = self._read_json(client, GROW_TARGETS_PATH)
        run = self._read_json(client, RUN_PROFILE_PATH)
        return combine_read_state(targets, run)

    def _verify(self, client: httpx.Client, patch: dict) -> dict:
        deadline = self.now_fn() + self.verification_timeout
        last_state: dict | None = None
        while True:
            last_state = self.read_profile(client)
            if verification_matches(last_state, patch):
                return last_state
            if self.now_fn() >= deadline:
                break
            self.sleep_fn(self.verification_interval)
        raise GrowWriteError(
            "verification_timeout",
            "Controller accepted the request but did not confirm the requested values in stored and runtime state.",
            504,
            controller_status=202,
            verification_ok=False,
        )

    @staticmethod
    def _error_code(response: httpx.Response) -> tuple[str, str | None]:
        try:
            data = response.json()
        except ValueError:
            return "controller_error", None
        if not isinstance(data, dict):
            return "controller_error", None
        code = str(data.get("error") or data.get("code") or data.get("detail") or "controller_error")
        message = data.get("message")
        return code, str(message) if message else None

    def apply_patch(self, patch: dict) -> dict:
        validate_patch_values(patch)
        body = serialize_request_body(patch)
        last_error: GrowWriteError | None = None
        with self.client_factory() as client:
            # Pre-read provides better local validation of phase/date partial updates.
            # A controller still remains authoritative and performs the same validation itself.
            current = self.read_profile(client)
            validate_resulting_profile(patch, current=current)

            last_timestamp: int | None = None
            for attempt in range(1, self.max_attempts + 1):
                timestamp = int(self.now_fn())
                if last_timestamp is not None and timestamp <= last_timestamp:
                    # A retry must be a completely fresh signed request. The firmware accepts
                    # a +/-60 s window, so advancing by one second is safe even when the
                    # backoff happens within the same Unix second.
                    timestamp = last_timestamp + 1
                last_timestamp = timestamp
                nonce = self.nonce_fn()
                headers = signed_headers(self.secret_hex, body, timestamp=timestamp, nonce=nonce)
                try:
                    response = client.patch(f"{self.base_url}{WRITE_PATH}", content=body, headers=headers)
                except (httpx.RequestError, httpx.TimeoutException) as exc:
                    raise GrowWriteError("controller_unreachable", "GrowTent controller could not be reached.", 502) from exc

                if response.status_code == 202:
                    try:
                        data = response.json()
                    except ValueError as exc:
                        raise GrowWriteError("controller_invalid_response", "Controller returned an invalid 202 response.", 502, 202) from exc
                    request_id = data.get("requestId") if isinstance(data, dict) else None
                    try:
                        verified_state = self._verify(client, patch)
                    except GrowWriteError as exc:
                        exc.request_id = request_id
                        raise
                    return {
                        "ok": True,
                        "requestId": request_id,
                        "httpStatus": 202,
                        "attempts": attempt,
                        "verified": True,
                        "changedFields": list(patch.keys()),
                        "state": verified_state,
                    }

                code, firmware_message = self._error_code(response)
                if response.status_code == 409 and code in TRANSIENT_CONFLICTS and attempt < self.max_attempts:
                    last_error = GrowWriteError(code, controller_error_message(code, firmware_message), 409, response.status_code)
                    self.sleep_fn(min(0.25 * attempt, 0.75))
                    continue

                backend_status = 502 if code in AUTH_ERRORS else (response.status_code if 400 <= response.status_code < 500 else 502)
                raise GrowWriteError(
                    code,
                    controller_error_message(code, firmware_message),
                    backend_status,
                    response.status_code,
                )

        if last_error:
            raise last_error
        raise GrowWriteError("controller_error", "Controller write failed.", 502)
