from pathlib import Path


def _app_source() -> str:
    return Path("api/app.py").read_text(encoding="utf-8")


def test_air_sensor_header_does_not_fake_enabled_state_on_fetch_failure():
    text = _app_source()
    assert "renderAirSensorWidget({ enabled:true, configured:true" not in text
    assert "catch {\n              hideAirSensorWidget();\n            }" in text


def test_air_sensor_header_hides_on_non_ok_or_missing_payload():
    text = _app_source()
    assert "if (!res.ok) {\n                hideAirSensorWidget();" in text
    assert "if (!data) {\n                hideAirSensorWidget();" in text
    assert "if (!data?.enabled || !data?.configured) {\n              hideAirSensorWidget();" in text


def test_real_configured_air_sensor_can_still_render_offline_state():
    text = _app_source()
    assert "widget.classList.toggle('offline', !data.ok);" in text
    assert "widget.style.display = 'inline-flex';" in text
