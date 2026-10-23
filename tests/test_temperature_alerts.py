import ast
from pathlib import Path


def _load_functions():
    source_path = Path(__file__).resolve().parents[1] / "api" / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {
        "_normalize_temperature_unit",
        "_temperature_display_value",
        "_temperature_readings",
        "_temperature_alert_candidates",
        "_send_grouped_temperature_alerts",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    sent = []
    marked = []

    def _to_float(value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    namespace = {
        "TEMP_MIN_C": -20.0,
        "TEMP_MAX_C": 80.0,
        "_to_float": _to_float,
        "_send_pushover": lambda title, message, priority=0: sent.append((title, message, priority)) or True,
        "_mark_temperature_alerts_active": lambda alerts: marked.append(alerts),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace, sent, marked


def test_reads_bme280_and_ds18b20_temperatures():
    ns, _, _ = _load_functions()
    readings = ns["_temperature_readings"]({
        "sensors.cur.temperatureC": 31.2,
        "sensors.cur.extTempC": 29.4,
    })
    assert readings == [
        {"sensor_key": "bme280", "sensor_label": "BME280", "temperature_c": 31.2},
        {"sensor_key": "ds18b20", "sensor_label": "DS18B20", "temperature_c": 29.4},
    ]


def test_alerts_only_on_new_over_threshold_episode_and_rearms_below_threshold():
    ns, _, _ = _load_functions()
    payload = {
        "sensors.cur.temperatureC": 31.2,
        "sensors.cur.extTempC": 29.4,
    }
    alerts, resets = ns["_temperature_alert_candidates"](payload, 30.0, {"bme280": False, "ds18b20": True})
    assert [item["sensor_key"] for item in alerts] == ["bme280"]
    assert resets == ["ds18b20"]

    alerts2, resets2 = ns["_temperature_alert_candidates"](payload, 30.0, {"bme280": True, "ds18b20": False})
    assert alerts2 == []
    assert resets2 == []


def test_equal_to_threshold_does_not_alert():
    ns, _, _ = _load_functions()
    alerts, resets = ns["_temperature_alert_candidates"]({
        "sensors.cur.temperatureC": 30.0,
        "sensors.cur.extTempC": 30.0,
    }, 30.0, {})
    assert alerts == []
    assert resets == []


def test_grouped_message_contains_tent_sensor_and_temperature():
    ns, sent, marked = _load_functions()
    alerts = [
        {"tent_id": 1, "tent_label": "60x60", "sensor_key": "bme280", "sensor_label": "BME280", "temperature_c": 31.2},
        {"tent_id": 2, "tent_label": "80x80", "sensor_key": "ds18b20", "sensor_label": "DS18B20", "temperature_c": 32.4},
    ]
    assert ns["_send_grouped_temperature_alerts"](alerts, 30.0) is True
    assert len(sent) == 1
    assert sent[0][0] == "CanopyOps: Temperatur zu hoch"
    assert "Temperatur über 30.0 °C" in sent[0][1]
    assert "60x60 – BME280: 31.2 °C" in sent[0][1]
    assert "80x80 – DS18B20: 32.4 °C" in sent[0][1]
    assert marked == [alerts]


def test_grouped_message_can_use_fahrenheit_display_unit():
    ns, sent, marked = _load_functions()
    alerts = [
        {"tent_id": 1, "tent_label": "60x60", "sensor_key": "bme280", "sensor_label": "BME280", "temperature_c": 31.2},
    ]
    assert ns["_send_grouped_temperature_alerts"](alerts, 30.0, "F") is True
    assert len(sent) == 1
    assert "Temperatur über 86.0 °F" in sent[0][1]
    assert "60x60 – BME280: 88.2 °F" in sent[0][1]
    assert marked == [alerts]


def test_temperature_display_value_converts_celsius_to_fahrenheit():
    ns, _, _ = _load_functions()
    assert ns["_temperature_display_value"](30.0, "F") == 86.0
    assert ns["_temperature_display_value"](30.0, "C") == 30.0
