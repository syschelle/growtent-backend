from pathlib import Path


def test_modular_system_router_exposes_admin_routes():
    text = (Path(__file__).parents[1] / "api" / "routes" / "system.py").read_text(encoding="utf-8")
    assert "@router.get('/config/admins')" in text
    assert "@router.post('/config/admins')" in text
    assert "@router.put('/config/admins/{admin_id}')" in text
    assert "@router.delete('/config/admins/{admin_id}')" in text
    assert "@router.post('/config/admins/{admin_id}/2fa')" in text


def test_modular_system_router_exposes_flood_alert_routes():
    text = (Path(__file__).parents[1] / "api" / "routes" / "system.py").read_text(encoding="utf-8")
    assert "@router.get('/config/flood-alert')" in text
    assert "@router.post('/config/flood-alert')" in text
