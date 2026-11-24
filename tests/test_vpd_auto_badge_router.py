"""Production modular route: authenticated guest may read minimal VPD badge status."""
import time

from fastapi.testclient import TestClient

import test_security_hardening  # Optional import stubs for lightweight local tests.
import app as legacy
import main
from services import vpd_auto_store


def test_vpd_badge_modular_router_guest_can_read_but_anonymous_cannot(monkeypatch):
    monkeypatch.setattr(legacy, 'load_auth_config', lambda: {'enabled': True})
    monkeypatch.setattr(legacy, 'is_initial_install_available', lambda: False)
    calls=[]
    def fake_get_badge_status(tent_id):
        calls.append(tent_id)
        return {'tentId': tent_id, 'enabled': True, 'lastSyncFailed': True}
    monkeypatch.setattr(vpd_auto_store, 'get_badge_status', fake_get_badge_status)
    token='badge-test-guest'
    legacy.SESSIONS[token] = {
        'authenticated': True, 'role': 'guest', 'username': 'read-only',
        'expires_at': time.time() + 3600,
    }
    try:
        guest = TestClient(main.app, cookies={'caop_session': token})
        result = guest.get('/tents/8/vpd-auto/status')
        assert result.status_code == 200
        assert result.json() == {'tentId': 8, 'enabled': True, 'lastSyncFailed': True}
        assert calls == [8]
        assert TestClient(main.app).get('/tents/8/vpd-auto/status').status_code == 401
        assert calls == [8], 'Anonymous caller must not query the database'
        assert guest.get('/tents/8/vpd-auto').status_code == 403
    finally:
        legacy.SESSIONS.pop(token,None)
