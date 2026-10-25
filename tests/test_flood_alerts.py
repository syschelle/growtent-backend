import ast
from pathlib import Path


def _load_functions():
    source_path = Path(__file__).resolve().parents[1] / "api" / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {
        "_boolish",
        "_flood_alarm_state",
        "_flood_alert_candidate",
        "_send_grouped_flood_alerts",
        "_flood_battery_alert_candidate",
        "_send_grouped_flood_battery_alerts",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    sent = []
    marked = []
    battery_marked = []

    def _to_float(value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    namespace = {
        "math": __import__("math"),
        "_to_float": _to_float,
        "_send_pushover": lambda title, message, priority=0: sent.append((title, message, priority)) or True,
        "_mark_flood_alerts_active": lambda alerts: marked.append(alerts),
        "_mark_flood_battery_alerts_sent": lambda alerts: battery_marked.append(alerts),
        "FLOOD_BATTERY_ALERT_THRESHOLD_PCT": 7,
        "FLOOD_BATTERY_ALERT_COOLDOWN": __import__("datetime").timedelta(days=7),
        "datetime": __import__("datetime").datetime,
        "timezone": __import__("datetime").timezone,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    namespace["_battery_marked"] = battery_marked
    return namespace, sent, marked


def test_flood_alarm_recognizes_alarm_and_ok():
    ns, _, _ = _load_functions()
    alarm = ns["_flood_alarm_state"]({
        "sensors.flood.configured": True,
        "sensors.flood.alarm": True,
        "sensors.flood.status": "alarm",
        "sensors.flood.batteryPct": 96,
    })
    assert alarm["configured"] is True
    assert alarm["alarm"] is True
    assert alarm["battery_pct"] == 96

    ok = ns["_flood_alarm_state"]({
        "sensors.flood.configured": True,
        "sensors.flood.alarm": False,
        "sensors.flood.status": "ok",
    })
    assert ok["alarm"] is False


def test_flood_alerts_once_per_alarm_episode_and_rearms_when_dry():
    ns, _, _ = _load_functions()
    payload_alarm = {
        "sensors.flood.configured": True,
        "sensors.flood.alarm": True,
        "sensors.flood.status": "alarm",
    }
    alert, reset = ns["_flood_alert_candidate"](payload_alarm, False)
    assert alert is not None
    assert reset is False

    alert2, reset2 = ns["_flood_alert_candidate"](payload_alarm, True)
    assert alert2 is None
    assert reset2 is False

    payload_ok = {
        "sensors.flood.configured": True,
        "sensors.flood.alarm": False,
        "sensors.flood.status": "ok",
    }
    alert3, reset3 = ns["_flood_alert_candidate"](payload_ok, True)
    assert alert3 is None
    assert reset3 is True


def test_grouped_flood_message_contains_tent_and_battery():
    ns, sent, marked = _load_functions()
    alerts = [
        {"tent_id": 1, "tent_label": "60x60", "battery_pct": 96},
        {"tent_id": 2, "tent_label": "80x80", "battery_pct": 81},
    ]
    assert ns["_send_grouped_flood_alerts"](alerts) is True
    assert len(sent) == 1
    assert sent[0][0] == "CanopyOps: Wasser erkannt"
    assert "60x60 – Flood: WASSER – Batterie 96 %" in sent[0][1]
    assert "80x80 – Flood: WASSER – Batterie 81 %" in sent[0][1]
    assert marked == [alerts]


def test_flood_battery_alert_at_or_below_seven_percent_and_weekly_cooldown():
    ns, _, _ = _load_functions()
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc)
    low = {
        "sensors.flood.configured": True,
        "sensors.flood.alarm": False,
        "sensors.flood.status": "ok",
        "sensors.flood.batteryPct": 7,
    }
    assert ns["_flood_battery_alert_candidate"](low, None, now) is not None
    assert ns["_flood_battery_alert_candidate"](low, now - timedelta(days=6, hours=23), now) is None
    assert ns["_flood_battery_alert_candidate"](low, now - timedelta(days=7), now) is not None
    high = dict(low)
    high["sensors.flood.batteryPct"] = 8
    assert ns["_flood_battery_alert_candidate"](high, None, now) is None


def test_grouped_flood_battery_message_contains_tent_and_low_battery():
    ns, sent, _ = _load_functions()
    alerts = [
        {"tent_id": 1, "tent_label": "60x60", "battery_pct": 7},
        {"tent_id": 2, "tent_label": "80x80", "battery_pct": 4},
    ]
    assert ns["_send_grouped_flood_battery_alerts"](alerts) is True
    assert len(sent) == 1
    assert sent[0][0] == "CanopyOps: Flood-Batterie niedrig"
    assert "60x60 – Flood: Batterie 7 %" in sent[0][1]
    assert "80x80 – Flood: Batterie 4 %" in sent[0][1]
    assert ns["_battery_marked"] == [alerts]


def test_flood_dashboard_marks_low_battery_yellow_with_water_alarm_priority():
    text = (Path(__file__).parents[1] / "api" / "app.py").read_text(encoding="utf-8")
    assert ".flood-status.battery-low" in text
    assert "const batteryLow = Number.isFinite(battery) && battery <= 7;" in text
    assert "state = batteryLow ? 'battery-low' : 'ok';" in text
    # Water alarm is evaluated first and therefore keeps the red alarm state.
    assert text.index("if (alarm) {") < text.index("state = batteryLow ? 'battery-low' : 'ok';")
