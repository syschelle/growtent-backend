import json
import logging

import httpx
import pytest
from pydantic import ValidationError

from models.schemas import GrowProfilePatch
from services.grow_write_service import (
    GrowTentWriteClient,
    GrowWriteError,
    body_sha256_hex,
    serialize_request_body,
    signature_hex,
    validate_patch_values,
    validate_resulting_profile,
)

SECRET = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"
TEST_TIMESTAMP = 1793530800
TEST_NONCE = "00112233445566778899aabbccddeeff"


class FakeClock:
    def __init__(self, value=TEST_TIMESTAMP):
        self.value = float(value)

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.value += max(float(seconds), 1.0)


def _state(temp=22.0, vpd=0.8, phase=1, flowering="", drying=""):
    return {
        "targetTemperature": temp,
        "targetVPD": vpd,
        "currentPhase": phase,
        "floweringStart": flowering,
        "dryingStart": drying,
    }


def _transport_for_state(state, *, patch_handler=None):
    def handler(request: httpx.Request):
        path = request.url.path
        if request.method == "GET" and path == "/api/settings/grow-targets":
            payload = {
                "stored": {"targetTemperature": state["targetTemperature"], "targetVPD": state["targetVPD"]},
                "runtime": {"targetTemperature": state["targetTemperature"], "targetVPD": state["targetVPD"]},
            }
            return httpx.Response(200, json=payload)
        if request.method == "GET" and path == "/api/settings/run-profile":
            payload = {
                "stored": {
                    "floweringStart": state["floweringStart"],
                    "dryingStart": state["dryingStart"],
                    "currentPhase": state["currentPhase"],
                },
                "runtime": {
                    "floweringStart": state["floweringStart"],
                    "dryingStart": state["dryingStart"],
                    "currentPhase": state["currentPhase"],
                },
            }
            return httpx.Response(200, json=payload)
        if request.method == "PATCH" and path == "/api/backend/grow-profile":
            if patch_handler:
                response = patch_handler(request, state)
                if response is not None:
                    return response
            patch = json.loads(request.content.decode("utf-8"))
            for key, value in patch.items():
                state[key] = "" if key in {"floweringStart", "dryingStart"} and value is None else value
            return httpx.Response(202, json={"ok": True, "requestId": 47, "applyQueued": True, "applyContext": "main-loop"})
        return httpx.Response(404, json={"error": "not_found"})

    return httpx.MockTransport(handler)


def _client(state, *, patch_handler=None, clock=None, nonce_fn=None, verification_timeout=4.0, max_attempts=3):
    transport = _transport_for_state(state, patch_handler=patch_handler)
    clock = clock or FakeClock()
    return GrowTentWriteClient(
        "http://192.0.2.10:8080",
        SECRET,
        client_factory=lambda: httpx.Client(transport=transport, timeout=4.0),
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        nonce_fn=nonce_fn,
        verification_timeout=verification_timeout,
        verification_interval=0.3,
        max_attempts=max_attempts,
    )


def test_hmac_required_test_vector_matches_exactly():
    payload = {
        "targetTemperature": 22.5,
        "targetVPD": 0.8,
        "currentPhase": 2,
        "floweringStart": "2026-11-01",
    }
    body = serialize_request_body(payload)
    assert body == b'{"targetTemperature":22.5,"targetVPD":0.8,"currentPhase":2,"floweringStart":"2026-11-01"}'
    assert body_sha256_hex(body) == "46074f3052a1b48a26d3b71211937536cb24f99016f85566b6ff4a445ca3014d"
    assert signature_hex(SECRET, TEST_TIMESTAMP, TEST_NONCE, body) == "a9487688764f8b09fb2ccc49db29667f7ff9fe1831e3147e502e3eeec32edc4c"


def test_valid_partial_patch_is_signed_sent_and_verified():
    state = _state()
    seen = {}

    def patch_handler(request, state_obj):
        seen["body"] = request.content
        seen["timestamp"] = request.headers["X-GrowTent-Timestamp"]
        seen["nonce"] = request.headers["X-GrowTent-Nonce"]
        seen["signature"] = request.headers["X-GrowTent-Signature"]
        patch = json.loads(request.content)
        state_obj.update(patch)
        return httpx.Response(202, json={"ok": True, "requestId": 99, "applyQueued": True})

    client = _client(state, patch_handler=patch_handler, nonce_fn=lambda: TEST_NONCE)
    result = client.apply_patch({"targetTemperature": 22.5})
    assert result["ok"] is True
    assert result["verified"] is True
    assert result["requestId"] == 99
    assert seen["body"] == b'{"targetTemperature":22.5}'
    assert seen["nonce"] == TEST_NONCE
    assert seen["signature"] == signature_hex(SECRET, int(seen["timestamp"]), TEST_NONCE, seen["body"])


def test_bad_signature_error_is_not_retried():
    state = _state()
    calls = 0

    def patch_handler(request, _state):
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"ok": False, "error": "bad_signature"})

    with pytest.raises(GrowWriteError) as exc:
        _client(state, patch_handler=patch_handler).apply_patch({"targetTemperature": 22.5})
    assert exc.value.code == "bad_signature"
    assert calls == 1


def test_expired_timestamp_error_is_not_retried():
    state = _state()
    calls = 0

    def patch_handler(request, _state):
        nonlocal calls
        calls += 1
        assert int(request.headers["X-GrowTent-Timestamp"]) == TEST_TIMESTAMP
        return httpx.Response(401, json={"ok": False, "error": "timestamp_out_of_window"})

    with pytest.raises(GrowWriteError) as exc:
        _client(state, patch_handler=patch_handler, clock=FakeClock(TEST_TIMESTAMP)).apply_patch({"targetVPD": 0.9})
    assert exc.value.code == "timestamp_out_of_window"
    assert calls == 1


def test_nonce_replay_is_reported_without_endless_retry():
    state = _state()
    seen = set()

    def patch_handler(request, state_obj):
        nonce = request.headers["X-GrowTent-Nonce"]
        if nonce in seen:
            return httpx.Response(409, json={"ok": False, "error": "replayed_nonce"})
        seen.add(nonce)
        patch = json.loads(request.content)
        state_obj.update(patch)
        return httpx.Response(202, json={"ok": True, "requestId": 1})

    client = _client(state, patch_handler=patch_handler, nonce_fn=lambda: TEST_NONCE)
    assert client.apply_patch({"targetTemperature": 22.5})["verified"] is True
    with pytest.raises(GrowWriteError) as exc:
        client.apply_patch({"targetTemperature": 22.6})
    assert exc.value.code == "replayed_nonce"


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        GrowProfilePatch(targetTemperature=22.0, growStart="2026-01-01")


@pytest.mark.parametrize(
    "patch",
    [
        {"targetTemperature": 17.9},
        {"targetTemperature": 30.1},
        {"targetVPD": 0.49},
        {"targetVPD": 3.51},
        {"currentPhase": 0},
        {"currentPhase": 4},
    ],
)
def test_out_of_range_values_are_rejected(patch):
    with pytest.raises(ValueError):
        validate_patch_values(patch)


def test_phase_2_without_flowering_start_is_rejected():
    with pytest.raises(ValueError, match="floweringStart is required"):
        validate_resulting_profile({"currentPhase": 2}, {"runtime": _state(phase=1, flowering="", drying="")})


def test_phase_3_without_drying_start_is_rejected():
    current = _state(phase=2, flowering="2026-11-01", drying="")
    with pytest.raises(ValueError, match="dryingStart is required"):
        validate_resulting_profile({"currentPhase": 3}, {"runtime": current})


@pytest.mark.parametrize("phase", [2, 3])
def test_flowering_null_is_rejected_for_phase_2_or_3(phase):
    current = _state(phase=phase, flowering="2026-11-01", drying="2026-11-10" if phase == 3 else "")
    with pytest.raises(ValueError, match="floweringStart may only be deleted"):
        validate_resulting_profile({"floweringStart": None}, {"runtime": current})


def test_flowering_null_in_phase_1_requires_drying_to_be_empty_too():
    current = _state(phase=1, flowering="2026-11-01", drying="2026-11-10")
    with pytest.raises(ValueError, match="dryingStart must be cleared together"):
        validate_resulting_profile({"floweringStart": None}, {"runtime": current})


def test_both_dates_can_be_cleared_together_in_phase_1():
    current = _state(phase=3, flowering="2026-11-01", drying="2026-11-10")
    validate_resulting_profile(
        {"currentPhase": 1, "floweringStart": None, "dryingStart": None},
        {"runtime": current},
    )


def test_drying_null_is_rejected_in_phase_3():
    current = _state(phase=3, flowering="2026-11-01", drying="2026-11-10")
    with pytest.raises(ValueError, match="dryingStart may not be deleted"):
        validate_resulting_profile({"dryingStart": None}, {"runtime": current})


def test_empty_string_is_never_a_delete_operation():
    with pytest.raises(ValueError, match="JSON null"):
        validate_patch_values({"floweringStart": ""})


def test_invalid_date_order_is_rejected():
    current = _state(phase=3, flowering="2026-11-10", drying="2026-11-11")
    with pytest.raises(ValueError, match="floweringStart must be on or before dryingStart"):
        validate_resulting_profile({"dryingStart": "2026-11-01"}, {"runtime": current})


def test_successful_verification_reads_both_stored_and_runtime_endpoints():
    state = _state()
    paths = []
    base_transport = _transport_for_state(state)

    def handler(request):
        paths.append((request.method, request.url.path))
        return base_transport.handle_request(request)

    transport = httpx.MockTransport(handler)
    clock = FakeClock()
    client = GrowTentWriteClient(
        "192.0.2.10",
        SECRET,
        client_factory=lambda: httpx.Client(transport=transport),
        sleep_fn=clock.sleep,
        now_fn=clock.now,
        nonce_fn=lambda: TEST_NONCE,
    )
    result = client.apply_patch({"targetVPD": 0.9})
    assert result["verified"] is True
    assert ("GET", "/api/settings/grow-targets") in paths
    assert ("GET", "/api/settings/run-profile") in paths


def test_verification_timeout_is_reported_when_controller_never_confirms():
    state = _state()
    clock = FakeClock()

    def patch_handler(_request, _state):
        return httpx.Response(202, json={"ok": True, "requestId": 77})

    with pytest.raises(GrowWriteError) as exc:
        _client(state, patch_handler=patch_handler, clock=clock, verification_timeout=2.0).apply_patch({"targetTemperature": 22.5})
    assert exc.value.code == "verification_timeout"
    assert exc.value.request_id == 77


def test_temporary_409_retry_uses_new_timestamp_nonce_and_signature():
    state = _state()
    clock = FakeClock()
    nonces = iter(["00" * 16, "11" * 16])
    attempts = []

    def patch_handler(request, state_obj):
        attempts.append({
            "timestamp": request.headers["X-GrowTent-Timestamp"],
            "nonce": request.headers["X-GrowTent-Nonce"],
            "signature": request.headers["X-GrowTent-Signature"],
            "body": bytes(request.content),
        })
        if len(attempts) == 1:
            return httpx.Response(409, json={"ok": False, "error": "grow_settings_busy"})
        patch = json.loads(request.content)
        state_obj.update(patch)
        return httpx.Response(202, json={"ok": True, "requestId": 88})

    result = _client(state, patch_handler=patch_handler, clock=clock, nonce_fn=lambda: next(nonces)).apply_patch({"targetVPD": 0.95})
    assert result["verified"] is True
    assert result["attempts"] == 2
    assert attempts[0]["timestamp"] != attempts[1]["timestamp"]
    assert attempts[0]["nonce"] != attempts[1]["nonce"]
    assert attempts[0]["signature"] != attempts[1]["signature"]
    # The body bytes remain identical and are not reserialized after signing.
    assert attempts[0]["body"] == attempts[1]["body"] == b'{"targetVPD":0.95}'



def test_temporary_409_retry_forces_fresh_timestamp_even_within_same_second():
    state = _state()
    nonces = iter(["22" * 16, "33" * 16])
    attempts = []

    def patch_handler(request, state_obj):
        attempts.append({
            "timestamp": request.headers["X-GrowTent-Timestamp"],
            "nonce": request.headers["X-GrowTent-Nonce"],
            "signature": request.headers["X-GrowTent-Signature"],
        })
        if len(attempts) == 1:
            return httpx.Response(409, json={"ok": False, "error": "backend_write_pending"})
        patch = json.loads(request.content)
        state_obj.update(patch)
        return httpx.Response(202, json={"ok": True, "requestId": 89})

    transport = _transport_for_state(state, patch_handler=patch_handler)
    client = GrowTentWriteClient(
        "192.0.2.10",
        SECRET,
        client_factory=lambda: httpx.Client(transport=transport),
        sleep_fn=lambda _seconds: None,
        now_fn=lambda: float(TEST_TIMESTAMP),
        nonce_fn=lambda: next(nonces),
    )
    result = client.apply_patch({"targetVPD": 0.96})
    assert result["verified"] is True
    assert attempts[0]["timestamp"] == str(TEST_TIMESTAMP)
    assert attempts[1]["timestamp"] == str(TEST_TIMESTAMP + 1)
    assert attempts[0]["nonce"] != attempts[1]["nonce"]
    assert attempts[0]["signature"] != attempts[1]["signature"]

def test_secret_and_signatures_do_not_appear_in_logs(caplog):
    state = _state()
    captured_signature = None

    def patch_handler(request, _state):
        nonlocal captured_signature
        captured_signature = request.headers["X-GrowTent-Signature"]
        return httpx.Response(401, json={"ok": False, "error": "bad_signature"})

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(GrowWriteError):
            _client(state, patch_handler=patch_handler, nonce_fn=lambda: TEST_NONCE).apply_patch({"targetTemperature": 22.5})
    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert SECRET not in log_text
    assert captured_signature
    assert captured_signature not in log_text


def test_tent_payload_secret_is_write_only_by_contract_source_text():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    crud_text = (root / "api" / "db" / "crud.py").read_text(encoding="utf-8")
    app_text = (root / "api" / "app.py").read_text(encoding="utf-8")
    assert '"has_backend_hmac_secret"' in crud_text
    assert '"_backend_hmac_secret"' in crud_text
    assert '"backend_hmac_secret": None' in app_text
    assert "X-GrowTent-Signature" not in crud_text
