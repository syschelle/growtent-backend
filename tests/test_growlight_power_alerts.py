import ast
import math
from pathlib import Path


def _load_functions():
    source_path = Path(__file__).resolve().parents[1] / "api" / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    wanted = {
        "_growlight_power_sample",
        "_growlight_power_drop_candidate",
        "_send_growlight_power_drop_alert",
    }
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    module = ast.Module(body=nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    sent = []

    def _to_float(value):
        try:
            if value is None or value == "":
                return None
            return float(value)
        except Exception:
            return None

    def _boolish(value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    namespace = {
        "math": math,
        "_to_float": _to_float,
        "_boolish": _boolish,
        "_send_pushover": lambda title, message, priority=0: sent.append((title, message, priority)) or True,
    }
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace, sent


def _payload(on: bool, watt):
    return {
        "cur.shelly.light.isOn": on,
        "cur.shelly.light.Watt": watt,
    }


def test_first_on_sample_establishes_baseline_without_alert():
    ns, _ = _load_functions()
    alert, state = ns["_growlight_power_drop_candidate"](_payload(True, 150.0), 20.0, {})
    assert alert is None
    assert state["growlight_power_last_on"] is True
    assert state["growlight_power_last_watt"] == 150.0


def test_alerts_only_when_consecutive_on_samples_drop_by_more_than_threshold():
    ns, _ = _load_functions()
    _, state = ns["_growlight_power_drop_candidate"](_payload(True, 150.0), 20.0, {})

    alert_equal, state_equal = ns["_growlight_power_drop_candidate"](_payload(True, 130.0), 20.0, state)
    assert alert_equal is None
    assert state_equal["growlight_power_last_watt"] == 130.0

    # Establish a fresh 150 W baseline, then exceed the 20 W threshold.
    _, state = ns["_growlight_power_drop_candidate"](_payload(True, 150.0), 20.0, {})
    alert, retry_state = ns["_growlight_power_drop_candidate"](_payload(True, 129.9), 20.0, state)
    assert alert is not None
    assert round(alert["drop_w"], 1) == 20.1
    assert alert["before_w"] == 150.0
    assert alert["after_w"] == 129.9
    # Keep the high baseline until Pushover delivery succeeds, allowing a retry.
    assert retry_state["growlight_power_last_watt"] == 150.0


def test_normal_light_switch_off_never_triggers_power_drop_warning():
    ns, _ = _load_functions()
    state = {
        "growlight_power_last_on": True,
        "growlight_power_last_watt": 150.0,
        "growlight_power_alert_active": False,
        "growlight_power_reference_watt": None,
    }
    alert, next_state = ns["_growlight_power_drop_candidate"](_payload(False, 0.0), 20.0, state)
    assert alert is None
    assert next_state["growlight_power_last_on"] is False
    assert next_state["growlight_power_last_watt"] is None
    assert next_state["growlight_power_alert_active"] is False


def test_active_alert_suppresses_repeat_until_recovery_or_light_off():
    ns, _ = _load_functions()
    active = {
        "growlight_power_last_on": True,
        "growlight_power_last_watt": 129.0,
        "growlight_power_alert_active": True,
        "growlight_power_reference_watt": 150.0,
    }
    alert, still_active = ns["_growlight_power_drop_candidate"](_payload(True, 120.0), 20.0, active)
    assert alert is None
    assert still_active["growlight_power_alert_active"] is True

    # Recovery to within half the configured threshold of the pre-drop level rearms.
    alert2, recovered = ns["_growlight_power_drop_candidate"](_payload(True, 141.0), 20.0, still_active)
    assert alert2 is None
    assert recovered["growlight_power_alert_active"] is False
    assert recovered["growlight_power_reference_watt"] is None


def test_missing_watt_breaks_comparison_chain_instead_of_false_alerting():
    ns, _ = _load_functions()
    state = {
        "growlight_power_last_on": True,
        "growlight_power_last_watt": 150.0,
        "growlight_power_alert_active": False,
    }
    alert, next_state = ns["_growlight_power_drop_candidate"](_payload(True, None), 20.0, state)
    assert alert is None
    assert next_state["growlight_power_last_watt"] is None


def test_pushover_message_contains_before_after_drop_and_threshold():
    ns, sent = _load_functions()
    candidate = {"before_w": 155.0, "after_w": 121.0, "drop_w": 34.0, "threshold_w": 20.0}
    assert ns["_send_growlight_power_drop_alert"]("Stecklingsbox", candidate) is True
    assert sent[0][0] == "CanopyOps: Growlight-Leistungsabfall"
    assert "Stecklingsbox" in sent[0][1]
    assert "155.0 W" in sent[0][1]
    assert "121.0 W" in sent[0][1]
    assert "-34.0 W" in sent[0][1]
    assert "Warnschwelle > 20 W" in sent[0][1]


def test_setup_exposes_per_tent_optional_power_drop_warning_and_threshold():
    source = (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")
    assert 'id=\\"tentGrowlightPowerAlertEnabled\\"' in source
    assert 'id=\\"tentGrowlightPowerDropW\\" type=\\"number\\" min=\\"1\\" max=\\"1000\\" step=\\"1\\" value=\\"20\\"' in source
    assert "growlightPowerAlertEnabled: 'Warnung bei schnellem Growlight-Leistungsabfall aktivieren'" in source
    assert "growlightPowerAlertEnabled: 'Enable Growlight power-drop warning'" in source
    assert "growlight_power_alert_enabled: effectiveGrowlightPowerAlertEnabled" in source
    assert "growlight_power_drop_w: effectiveGrowlightPowerDropW" in source


def test_database_and_backup_include_power_drop_configuration():
    root = Path(__file__).resolve().parents[1]
    app_source = (root / "api" / "app.py").read_text(encoding="utf-8")
    crud_source = (root / "api" / "db" / "crud.py").read_text(encoding="utf-8")
    schema_source = (root / "api" / "models" / "schemas.py").read_text(encoding="utf-8")
    assert "growlight_power_alert_enabled BOOLEAN NOT NULL DEFAULT FALSE" in app_source
    assert "growlight_power_drop_w DOUBLE PRECISION NOT NULL DEFAULT 20.0" in app_source
    assert '"schema_version": 13' in app_source
    assert "growlight_power_alert_enabled" in crud_source
    assert "growlight_power_drop_w" in crud_source
    assert "growlight_power_alert_enabled: bool = False" in schema_source
    assert "growlight_power_drop_w: float = Field(default=20.0, ge=1.0, le=1000.0)" in schema_source


def test_poller_uses_existing_controller_payload_and_resets_baseline_after_failed_poll():
    source = (Path(__file__).resolve().parents[1] / "api" / "app.py").read_text(encoding="utf-8")
    assert 'data.get("cur.shelly.light.Watt")' in source
    assert 'data.get("cur.shelly.light.isOn")' in source
    assert "it adds no extra Shelly/controller request" in source
    assert "Break the Growlight comparison chain across failed polls/offline time." in source
