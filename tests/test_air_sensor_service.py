import sys
import unittest
from pathlib import Path

import httpx

API_DIR = Path(__file__).resolve().parents[1] / "api"
sys.path.insert(0, str(API_DIR))

from models.schemas import AirSensorSettings
from services.air_sensor_service import (  # noqa: E402
    AirSensorService,
    normalize_air_sensor_host,
    parse_air_sensor_payload,
    validate_safe_sensor_host,
)


SAMPLE_PAYLOAD = {
    "software_version": "NRZ-2024-136-B1",
    "age": "95",
    "sensordatavalues": [
        {"value_type": "SDS_P1", "value": "1.83"},
        {"value_type": "SDS_P2", "value": "0.40"},
        {"value_type": "BME280_temperature", "value": "24.17"},
        {"value_type": "BME280_humidity", "value": "30.21"},
    ],
}


class Clock:
    def __init__(self):
        self.value = 1000.0

    def monotonic(self):
        return self.value

    def iso(self):
        return f"2026-08-20T18:{int(self.value) % 60:02d}:00+00:00"

    def advance(self, seconds):
        self.value += seconds


def service_with_responses(responses, clock=None):
    clock = clock or Clock()
    calls = {"count": 0, "urls": []}
    queue = list(responses)

    def handler(request):
        calls["count"] += 1
        calls["urls"].append(str(request.url))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def client_factory():
        return httpx.Client(
            transport=httpx.MockTransport(handler),
            follow_redirects=False,
            timeout=1.0,
        )

    svc = AirSensorService(
        monotonic=clock.monotonic,
        now_iso=clock.iso,
        resolver=lambda host: ["192.168.178.50"],
        client_factory=client_factory,
    )
    return svc, calls, clock


def settings(enabled=True, host="192.168.178.50"):
    return AirSensorSettings(enabled=enabled, host=host)


def json_response(payload, status_code=200):
    return httpx.Response(status_code, json=payload)


class AirSensorServiceTests(unittest.TestCase):
    def test_maps_sensor_data_values(self):
        parsed = parse_air_sensor_payload(SAMPLE_PAYLOAD)

        self.assertEqual(parsed["sds_p1"], 1.83)
        self.assertEqual(parsed["sds_p2"], 0.40)
        self.assertEqual(parsed["temperature_c"], 24.17)
        self.assertEqual(parsed["humidity_percent"], 30.21)
        self.assertEqual(parsed["age_seconds"], 95)
        self.assertEqual(parsed["software_version"], "NRZ-2024-136-B1")


    def test_temperature_and_humidity_fallbacks(self):
        parsed = parse_air_sensor_payload(
            {
                "sensordatavalues": [
                    {"value_type": "BMP280_temperature", "value": "21.5"},
                    {"value_type": "humidity", "value": "44.2"},
                ]
            }
        )
        self.assertEqual(parsed["temperature_c"], 21.5)
        self.assertEqual(parsed["humidity_percent"], 44.2)

        parsed = parse_air_sensor_payload(
            {
                "sensordatavalues": [
                    {"value_type": "temperature", "value": "20.1"},
                    {"value_type": "humidity", "value": "40.0"},
                ]
            }
        )
        self.assertEqual(parsed["temperature_c"], 20.1)
        self.assertEqual(parsed["humidity_percent"], 40.0)


    def test_success_cache_prevents_frequent_polling(self):
        svc, calls, clock = service_with_responses([json_response(SAMPLE_PAYLOAD), json_response(SAMPLE_PAYLOAD)])

        first = svc.current(settings())
        second = svc.current(settings())
        clock.advance(179)
        third = svc.current(settings())
        clock.advance(2)
        fourth = svc.current(settings())

        self.assertIs(first.ok, True)
        self.assertIs(second.cached, True)
        self.assertIs(third.cached, True)
        self.assertIs(fourth.cached, False)
        self.assertEqual(calls["count"], 2)
        self.assertEqual(calls["urls"], ["http://192.168.178.50/data.json", "http://192.168.178.50/data.json"])


    def test_error_retry_throttle(self):
        svc, calls, clock = service_with_responses(
            [
                httpx.ConnectError("offline"),
                json_response(SAMPLE_PAYLOAD),
            ]
        )

        first = svc.current(settings())
        second = svc.current(settings())
        clock.advance(29)
        third = svc.current(settings())
        clock.advance(2)
        fourth = svc.current(settings())

        self.assertIs(first.ok, False)
        self.assertIs(second.cached, True)
        self.assertIs(third.cached, True)
        self.assertIs(fourth.ok, True)
        self.assertEqual(calls["count"], 2)


    def test_keeps_last_valid_values_when_fields_temporarily_missing(self):
        partial = {
            "sensordatavalues": [
                {"value_type": "BME280_temperature", "value": "25.00"},
            ]
        }
        svc, calls, clock = service_with_responses([json_response(SAMPLE_PAYLOAD), json_response(partial)])

        first = svc.current(settings())
        clock.advance(181)
        second = svc.current(settings())

        self.assertEqual(calls["count"], 2)
        self.assertEqual(first.humidity_percent, 30.21)
        self.assertEqual(second.temperature_c, 25.00)
        self.assertEqual(second.humidity_percent, 30.21)
        self.assertEqual(second.sds_p1, 1.83)
        self.assertEqual(second.sds_p2, 0.40)


    def test_disabled_or_unconfigured_sensor_does_not_poll(self):
        svc, calls, _clock = service_with_responses([json_response(SAMPLE_PAYLOAD)])

        disabled = svc.current(settings(enabled=False))
        unconfigured = svc.current(settings(enabled=True, host=None))

        self.assertIs(disabled.enabled, False)
        self.assertIs(disabled.configured, True)
        self.assertIs(disabled.ok, False)
        self.assertIs(unconfigured.enabled, True)
        self.assertIs(unconfigured.configured, False)
        self.assertIs(unconfigured.ok, False)
        self.assertEqual(calls["count"], 0)


    def test_blocks_unsafe_hosts_and_redirects(self):
        self.assertEqual(normalize_air_sensor_host("http://192.168.178.50/"), "192.168.178.50")
        with self.assertRaises(ValueError):
            validate_safe_sensor_host("8.8.8.8")
        with self.assertRaises(ValueError):
            validate_safe_sensor_host("127.0.0.1")
        with self.assertRaises(ValueError):
            validate_safe_sensor_host("169.254.169.254")
        with self.assertRaises(ValueError):
            validate_safe_sensor_host("example.test", resolver=lambda _host: ["1.2.3.4"])

        svc, _calls, _clock = service_with_responses([httpx.Response(302, headers={"Location": "http://192.168.178.51/data.json"})])
        current = svc.current(settings())
        self.assertIs(current.ok, False)
        self.assertIn("redirect", (current.last_error or "").lower())


if __name__ == "__main__":
    unittest.main()
