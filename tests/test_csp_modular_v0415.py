"""Real production ASGI wrapper – header coverage on login, denied and app."""
import time

from fastapi.testclient import TestClient

import test_security_hardening  # Only supplies optional-driver stubs in local unit test environments.
import app as legacy
import main
from services.security_headers import CONTENT_SECURITY_POLICY


def test_modular_routes_security_headers_cover_public_denied_and_app(monkeypatch):
    monkeypatch.setattr(legacy, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(legacy, 'load_auth_config', lambda: {'enabled': True})
    unauth = TestClient(main.app)
    login = unauth.get('/auth/login', follow_redirects=False)
    denied = unauth.get('/tents', follow_redirects=False)
    assert login.status_code == 200
    assert denied.status_code == 401
    for result in [login, denied]:
        assert result.headers['content-security-policy'] == CONTENT_SECURITY_POLICY
        assert result.headers['x-content-type-options'] == 'nosniff'
    token = 'csp-modular-test-admin'
    legacy.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'username': 'csp-test',
                               'expires_at': time.time() + 3600}
    try:
        page = TestClient(main.app, cookies={'caop_session': token}).get('/app?page=dashboard')
        assert page.status_code == 200
        assert 'Content-Security-Policy' in page.headers
        assert page.headers['content-security-policy'] == CONTENT_SECURITY_POLICY
    finally:
        legacy.SESSIONS.pop(token, None)
