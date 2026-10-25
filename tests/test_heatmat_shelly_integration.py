from pathlib import Path


def _app_text():
    return (Path(__file__).parents[1] / 'api' / 'app.py').read_text(encoding='utf-8')


def test_heatmat_is_known_read_only_shelly_device():
    text = _app_text()
    assert 'keys = ["main", "light", "humidifier", "heater", "heatmat", "fan", "exhaust"]' in text
    assert 'base = ["main", "light", "humidifier", "heater", "heatmat", "fan", "exhaust"]' in text
    assert "const base = ['main', 'light', 'humidifier', 'heater', 'heatmat', 'fan', 'exhaust'];" in text
    # Heat mat must remain monitoring-only: it is intentionally absent from toggle allow-lists.
    assert "const allowed = ['main', 'light', 'humidifier', 'heater', 'fan', 'exhaust'];" in text
    assert 'allowed = {"main", "light", "humidifier", "heater", "fan", "exhaust"}' in text


def test_heatmat_has_localized_name_and_icon():
    text = _app_text()
    assert "shellyHeatmat: 'Heat mat'" in text
    assert "shellyHeatmat: 'Heizmatte'" in text
    assert "case 'heatmat': return '♨️';" in text
    assert "heatmat: tr('shellyHeatmat')" in text
