"""v0.414 – login limiter proxy isolation and one-time 2FA consumption."""
from types import SimpleNamespace
from fastapi import HTTPException
import pytest

import test_security_hardening  # optional lightweight PostgreSQL/pyotp test stubs
from test_security_hardening import _request
import app


def _req(ip='192.0.2.12', forwarded=None):
    r = _request('/auth/login', 'POST', client=(ip, 9999))
    if forwarded is not None:
        headers = list(r.scope['headers'])
        headers.append((b'x-forwarded-for', forwarded.encode()))
        r.scope['headers'] = headers
    return r


def test_spoofed_forwarded_headers_not_trusted_without_allowlist(monkeypatch):
    monkeypatch.setattr(app, 'GT_TRUSTED_PROXY_CIDRS', '')
    a = _req('172.18.0.5', '203.0.113.3')
    assert app._login_client_address(a) == '172.18.0.5'
    b = _req('172.18.0.5', '203.0.113.4')
    assert app._login_rate_keys('admin', a) == app._login_rate_keys('admin', b)


def test_proxy_header_trust_ends_at_first_untrusted_hop(monkeypatch):
    monkeypatch.setattr(app, 'GT_TRUSTED_PROXY_CIDRS', '172.18.0.5/32,127.0.0.1/32')
    req = _req('172.18.0.5', '198.51.100.99, 203.0.113.27, 127.0.0.1')
    assert app._login_client_address(req) == '203.0.113.27'
    assert app._login_client_address(_req('192.0.2.4', '203.0.113.9')) == '192.0.2.4'
    assert app._login_client_address(_req('172.18.0.5', 'invalid-ip')) == '172.18.0.5'


def test_login_limits_only_username_and_client_pair(monkeypatch):
    monkeypatch.setattr(app, 'GT_TRUSTED_PROXY_CIDRS', '')
    monkeypatch.setattr(app, 'LOGIN_RATE_LIMIT_ATTEMPTS', 3)
    app.LOGIN_FAILURES.clear()
    a = _req('172.18.0.5')
    b = _req('172.18.0.6')
    try:
        for _ in range(3):
            app._record_login_failure('admin', a)
        with pytest.raises(HTTPException) as exc:
            app._check_login_rate_limit('admin', a)
        assert exc.value.status_code == 429
        # Other accounts sharing the same proxy/IP, and same user from another
        # client, are never locked by the attacker's login attempts.
        app._check_login_rate_limit('guest', a)
        app._check_login_rate_limit('admin', b)
    finally:
        app.LOGIN_FAILURES.clear()


def test_missing_account_runs_dummy_password_verification(monkeypatch):
    app.LOGIN_FAILURES.clear()
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'username':'admin', 'password_hash':'valid-argon',
                                                         'guest_enabled':False,'guest_username':''})
    monkeypatch.setattr(app, '_get_admin_user_by_username', lambda *a, **k: None)
    monkeypatch.setattr(app, '_find_active_guest_user', lambda *a, **k: None)
    seen = []
    monkeypatch.setattr(app, '_verify_secret', lambda stored, password: seen.append((stored,password)) or False)
    try:
        with pytest.raises(HTTPException) as exc:
            app.auth_login(app.LoginPayload(username='nonexistent',password='wrong'), _req())
        assert exc.value.status_code == 401
        assert seen == [(app._DUMMY_LOGIN_PASSWORD_HASH, 'wrong')]
    finally:
        app.LOGIN_FAILURES.clear()


def test_explicit_totp_counter_and_adjacent_window(monkeypatch):
    class FakeTOTP:
        interval = 30
        def __init__(self, secret): self.secret = secret
        def at(self, timestamp):
            return f'{int(timestamp)//30:06d}'
    monkeypatch.setattr(app, 'pyotp', SimpleNamespace(TOTP=FakeTOTP))
    assert app._matching_totp_step('secret', '000100', now=3000) == 100
    assert app._matching_totp_step('secret', '000099', now=3000) == 99
    assert app._matching_totp_step('secret', '000101', now=3000) == 101
    assert app._matching_totp_step('secret', '000098', now=3000) is None
    assert app._matching_totp_step('secret', '100<script>', now=3000) is None


def test_totp_replay_guard_is_per_account_and_resets_on_key_rotation():
    class Cursor:
        def __init__(self): self.store={};self.ok=False
        def execute(self,sql, params):
            assert 'ON CONFLICT' in sql and 'RETURNING last_step' in sql
            key, finger, step = params
            old = self.store.get(key)
            self.ok = old is None or old[0] != finger or old[1] < step
            if self.ok:self.store[key]=(finger,step)
        def fetchone(self): return (1,) if self.ok else None
    c=Cursor()
    assert app._record_totp_step(c,account_key='admin:1',secret='first',step=100)
    assert not app._record_totp_step(c,account_key='admin:1',secret='first',step=100)
    assert not app._record_totp_step(c,account_key='admin:1',secret='first',step=99)
    assert app._record_totp_step(c,account_key='admin:2',secret='first',step=100)
    assert app._record_totp_step(c,account_key='admin:1',secret='first',step=101)
    assert app._record_totp_step(c,account_key='admin:1',secret='rotated',step=100)


def test_api_docker_disables_automatic_untrusted_forward_headers():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    assert '--no-proxy-headers' in (root/'api/Dockerfile').read_text()
    for file in ('docker-compose.yml','docker-compose.images.yml'):
        assert 'GT_TRUSTED_PROXY_CIDRS:' in (root/file).read_text()


def test_second_preauth_cannot_reuse_already_consumed_totp(monkeypatch):
    import time
    app.SESSIONS.clear()
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda *_args, **_kwargs: {
        'id': 12, 'username': 'admin', 'enabled': True,
        'twofa_enabled': True, 'totp_secret': 'test-secret', 'recovery_codes_json': '[]'
    })
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'twofa_enabled': True})
    spent = set()
    def consume(**kwargs):
        key = (kwargs['admin_id'], kwargs['code'])
        if key in spent: return False
        spent.add(key)
        return True
    monkeypatch.setattr(app, '_consume_totp_code', consume)
    for pretoken, expected in [('first-token', 200), ('second-token', 401)]:
        app.SESSIONS[pretoken] = {
            'preauth': True, 'role': 'admin', 'username': 'admin',
            'admin_id': 12, 'expires_at': time.time()+300,
            'attempts': 0,
        }
        payload = app.Login2FAPayload(preauth_token=pretoken, code='123456')
        if expected == 200:
            response = app.auth_login_2fa(payload, _req())
            assert response.status_code == 200
        else:
            with pytest.raises(HTTPException) as exc:
                app.auth_login_2fa(payload, _req())
            assert exc.value.status_code == 401
    app.SESSIONS.clear()
