import ast
from datetime import date, datetime, timedelta
from pathlib import Path


def _load_functions():
    source_path = Path(__file__).resolve().parents[1] / "api" / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {
        "_grow_phase_is_drying",
        "_soil_measurement_is_fresh",
        "_low_soil_moisture_candidates",
        "_soil_alerts_not_notified_today",
        "_send_grouped_soil_moisture_alerts",
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
        "datetime": datetime,
        "date": date,
        "SOIL_MOISTURE_ALERT_THRESHOLD_PCT": 25.0,
        "SOIL_MOISTURE_ALERT_MAX_AGE_SECONDS": 300,
        "_to_float": _to_float,
        "_send_pushover": lambda title, message, priority=0: sent.append((title, message, priority)) or True,
        "_mark_soil_alerts_notified": lambda alerts, day: marked.append((alerts, day)),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace, sent, marked


def test_drying_phase_suppresses_low_moisture_alerts():
    ns, _, _ = _load_functions()
    now = datetime.now()
    payload = {
        "settings.grow.currentPhase": 3,
        "soil.sensors": [{
            "pot_index": 1,
            "moisture_percent": 10,
            "sensor_plausible": True,
            "sensor_status": "ok",
            "last_measurement_at": now.isoformat(timespec="seconds"),
        }],
    }
    assert ns["_low_soil_moisture_candidates"](payload) == []


def test_only_valid_fresh_values_below_25_percent_trigger():
    ns, _, _ = _load_functions()
    now = datetime.now()
    fresh = now.isoformat(timespec="seconds")
    stale = (now - timedelta(minutes=6)).isoformat(timespec="seconds")
    payload = {
        "settings.grow.currentPhase": 2,
        "soil.sensors": [
            {"pot_index": 1, "moisture_percent": 24.9, "sensor_plausible": True, "sensor_status": "ok", "last_measurement_at": fresh},
            {"pot_index": 2, "moisture_percent": 10, "sensor_plausible": False, "sensor_status": "not_connected", "last_measurement_at": fresh},
            {"pot_index": 3, "moisture_percent": 20, "sensor_plausible": True, "sensor_status": "ok", "last_measurement_at": stale},
        ],
    }
    candidates = ns["_low_soil_moisture_candidates"](payload)
    assert len(candidates) == 1
    assert candidates[0]["pot_index"] == 1
    assert candidates[0]["moisture_percent"] == 24.9


def test_daily_cooldown_is_per_sensor():
    ns, _, _ = _load_functions()
    today = date(2026, 10, 10)
    candidates = [
        {"pot_index": 1, "moisture_percent": 20.0},
        {"pot_index": 2, "moisture_percent": 21.0},
    ]
    remaining = ns["_soil_alerts_not_notified_today"](candidates, {1: today}, today)
    assert [item["pot_index"] for item in remaining] == [2]


def test_grouped_push_contains_multiple_sensors_and_marks_after_success():
    ns, sent, marked = _load_functions()
    today = date(2026, 10, 10)
    alerts = [
        {"tent_id": 1, "tent_label": "Tent A", "pot_index": 1, "moisture_percent": 20.0},
        {"tent_id": 1, "tent_label": "Tent A", "pot_index": 2, "moisture_percent": 22.5},
        {"tent_id": 2, "tent_label": "Tent B", "pot_index": 3, "moisture_percent": 19.0},
    ]
    assert ns["_send_grouped_soil_moisture_alerts"](alerts, today) is True
    assert len(sent) == 1
    assert "Tent A – Topf 1: 20.0 %" in sent[0][1]
    assert "Tent A – Topf 2: 22.5 %" in sent[0][1]
    assert "Tent B – Topf 3: 19.0 %" in sent[0][1]
    assert marked == [(alerts, today)]
