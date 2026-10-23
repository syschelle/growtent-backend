import asyncio
import time
import zipfile
import sys
import types

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request
import fastapi.staticfiles

class _DummyStaticFiles:
    def __init__(self, *args, **kwargs):
        pass
    async def __call__(self, scope, receive, send):
        await send({'type': 'http.response.start', 'status': 404, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})

fastapi.staticfiles.StaticFiles = _DummyStaticFiles

# The project test environment does not install PostgreSQL client bindings because
# these tests mock DB access. Provide the minimal import surface needed by app.py.
if 'pyotp' not in sys.modules:
    pyotp_stub = types.ModuleType('pyotp')
    class _DummyTOTP:
        def __init__(self, *args, **kwargs):
            pass
        def verify(self, *args, **kwargs):
            return False
        def provisioning_uri(self, *args, **kwargs):
            return 'otpauth://dummy'
    pyotp_stub.TOTP = _DummyTOTP
    pyotp_stub.random_base32 = lambda: 'DUMMY'
    sys.modules['pyotp'] = pyotp_stub

if 'qrcode' not in sys.modules:
    qrcode_stub = types.ModuleType('qrcode')
    class _DummyQr:
        def save(self, buf, format=None):
            buf.write(b'dummy')
    qrcode_stub.make = lambda *a, **k: _DummyQr()
    sys.modules['qrcode'] = qrcode_stub

if 'psycopg2' not in sys.modules:
    psycopg2_stub = types.ModuleType('psycopg2')
    class _PsycopgError(Exception):
        pass
    psycopg2_stub.Error = _PsycopgError
    psycopg2_stub.connect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('DB access not expected in security unit tests'))
    sys.modules['psycopg2'] = psycopg2_stub

import app


def _request(path='/', method='GET', cookie=None, client=('127.0.0.1', 12345), accept='application/json'):
    headers = [(b'accept', accept.encode())]
    if cookie:
        headers.append((b'cookie', cookie.encode()))
    scope = {
        'type': 'http',
        'http_version': '1.1',
        'method': method,
        'scheme': 'https',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': headers,
        'client': client,
        'server': ('testserver', 443),
    }
    return Request(scope)


def test_auth_disabled_login_still_requires_real_admin_credentials(monkeypatch):
    app.LOGIN_FAILURES.clear()
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'enabled': False,
        'username': 'admin',
        'password_hash': 'stored',
        'guest_enabled': False,
        'guest_username': '',
        'guest_password_hash': '',
    })
    monkeypatch.setattr(app, '_get_admin_user_by_username', lambda *a, **k: None)
    monkeypatch.setattr(app, '_find_active_guest_user', lambda *a, **k: None)
    monkeypatch.setattr(app, '_verify_secret', lambda stored, value: stored == 'stored' and value == 'correct')

    with pytest.raises(HTTPException) as exc:
        app.auth_login(app.LoginPayload(username='attacker', password='wrong'), _request('/auth/login', 'POST'))
    assert exc.value.status_code == 401


def test_auth_disabled_valid_admin_login_sets_secure_cookie(monkeypatch):
    app.LOGIN_FAILURES.clear()
    app.SESSIONS.clear()
    monkeypatch.setattr(app, 'SESSION_COOKIE_SECURE', True)
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'enabled': False,
        'username': 'admin',
        'password_hash': 'stored',
        'guest_enabled': False,
        'guest_username': '',
        'guest_password_hash': '',
        'twofa_enabled': False,
    })
    monkeypatch.setattr(app, '_get_admin_user_by_username', lambda username, include_disabled=True: {
        'id': 7, 'username': 'admin', 'password_hash': 'stored', 'enabled': True, 'twofa_enabled': False
    } if username == 'admin' else None)
    monkeypatch.setattr(app, '_find_active_guest_user', lambda *a, **k: None)
    monkeypatch.setattr(app, '_verify_secret', lambda stored, value: stored == 'stored' and value == 'correct')

    resp = app.auth_login(app.LoginPayload(username='admin', password='correct'), _request('/auth/login', 'POST'))
    cookie = resp.headers.get('set-cookie', '')
    assert 'caop_session=' in cookie
    assert 'HttpOnly' in cookie
    assert 'Secure' in cookie
    assert 'SameSite=lax' in cookie


def test_sensitive_config_get_is_admin_only_even_when_global_auth_disabled(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'get_session', lambda token: None)

    async def next_handler(_request):
        return JSONResponse({'ok': True})

    resp = asyncio.run(app.auth_middleware(_request('/config/auth', 'GET'), next_handler))
    assert resp.status_code == 403


def test_anonymous_write_remains_blocked_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'enabled': False})
    monkeypatch.setattr(app, 'is_initial_install_available', lambda: False)
    monkeypatch.setattr(app, 'get_session', lambda token: None)

    async def next_handler(_request):
        return JSONResponse({'ok': True})

    resp = asyncio.run(app.auth_middleware(_request('/tents', 'POST'), next_handler))
    assert resp.status_code == 401


def test_project_zip_disabled_by_default(monkeypatch):
    token = 'admin-token'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'admin_id': 1, 'username': 'admin', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', False)
    with pytest.raises(HTTPException) as exc:
        app.download_project_zip(_request('/download/project.zip', cookie=f'caop_session={token}'))
    assert exc.value.status_code == 404
    app.SESSIONS.pop(token, None)


def test_project_zip_never_contains_env_or_private_keys(tmp_path, monkeypatch):
    (tmp_path / 'README.md').write_text('safe', encoding='utf-8')
    (tmp_path / '.env').write_text('SECRET=bad', encoding='utf-8')
    (tmp_path / '.env.production').write_text('SECRET=bad2', encoding='utf-8')
    (tmp_path / 'server.key').write_text('private', encoding='utf-8')
    token = 'admin-token'
    app.SESSIONS[token] = {'authenticated': True, 'role': 'admin', 'admin_id': 1, 'username': 'admin', 'expires_at': time.time() + 60}
    monkeypatch.setattr(app, 'PROJECT_ROOT', str(tmp_path))
    monkeypatch.setattr(app, 'PROJECT_DOWNLOAD_ENABLED', True)
    resp = app.download_project_zip(_request('/download/project.zip', cookie=f'caop_session={token}'))
    with zipfile.ZipFile(resp.path) as zf:
        names = set(zf.namelist())
    assert 'README.md' in names
    assert '.env' not in names
    assert '.env.production' not in names
    assert 'server.key' not in names
    app.SESSIONS.pop(token, None)


def test_history_api_disable_flag_is_enforced(monkeypatch):
    monkeypatch.setattr(app, 'load_auth_config', lambda: {'history_api_enabled': False})
    resp = app.api_history_for_device('anything')
    assert resp.status_code == 403


def test_revoke_admin_sessions_removes_existing_sessions():
    app.SESSIONS.clear()
    now = time.time() + 60
    app.SESSIONS['a'] = {'authenticated': True, 'role': 'admin', 'admin_id': 5, 'username': 'alice', 'expires_at': now}
    app.SESSIONS['b'] = {'authenticated': True, 'role': 'admin', 'admin_id': 6, 'username': 'bob', 'expires_at': now}
    assert app._revoke_admin_sessions(5, 'alice') == 1
    assert 'a' not in app.SESSIONS
    assert 'b' in app.SESSIONS
    app.SESSIONS.clear()


def test_login_rate_limit_trips(monkeypatch):
    app.LOGIN_FAILURES.clear()
    monkeypatch.setattr(app, 'LOGIN_RATE_LIMIT_ATTEMPTS', 3)
    monkeypatch.setattr(app, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 900)
    req = _request('/auth/login', 'POST', client=('192.0.2.10', 1234))
    for _ in range(3):
        app._record_login_failure('admin', req)
    with pytest.raises(HTTPException) as exc:
        app._check_login_rate_limit('admin', req)
    assert exc.value.status_code == 429
    app.LOGIN_FAILURES.clear()


def test_compose_binds_api_to_loopback_by_default():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for filename in ('docker-compose.yml', 'docker-compose.images.yml'):
        text = (root / filename).read_text(encoding='utf-8')
        assert '${GT_API_BIND_ADDRESS:-127.0.0.1}:8088:8080' in text


def test_twofa_preauth_is_revoked_after_too_many_failures(monkeypatch):
    app.SESSIONS.clear()
    monkeypatch.setattr(app, 'TWOFA_MAX_ATTEMPTS', 3)
    monkeypatch.setattr(app, '_get_admin_user_by_id', lambda *a, **k: None)
    monkeypatch.setattr(app, 'load_auth_config', lambda: {
        'twofa_enabled': True,
        'totp_secret': 'DUMMY',
        'recovery_codes_json': '[]',
    })
    token = 'preauth-test'
    app.SESSIONS[token] = {
        'preauth': True,
        'role': 'admin',
        'username': 'admin',
        'admin_id': None,
        'expires_at': time.time() + 300,
        'attempts': 0,
    }
    req = _request('/auth/login/2fa', 'POST')
    payload = app.Login2FAPayload(preauth_token=token, code='000000', recoveryCode='')
    for expected in (401, 401, 429):
        with pytest.raises(HTTPException) as exc:
            app.auth_login_2fa(payload, req)
        assert exc.value.status_code == expected
    assert token not in app.SESSIONS
