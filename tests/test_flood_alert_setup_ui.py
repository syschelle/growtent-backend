from pathlib import Path


def test_setup_exposes_flood_alert_toggle_and_load_save_logic():
    text = (Path(__file__).parents[1] / "api" / "app.py").read_text(encoding="utf-8")
    assert 'id=\\"floodAlertEnabled\\"' in text
    assert "fetch('/config/flood-alert'" in text
    assert 'loadFloodAlertConfigUi();' in text
    assert 'saveFloodAlertConfig();' in text
    assert "floodAlertEnabled: 'Wasseralarm (Flood)'" in text
