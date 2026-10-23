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
        "math": __import__("math"),
        "_to_float": _to_float,
        "_send_pushover": lambda title, message, priority=0: sent.append((title, message, priority)) or True,
        "_mark_flood_alerts_active": lambda alerts: marked.append(alerts),
    }
    exec(compile(module, str(source_path), "exec"), namespace)
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
